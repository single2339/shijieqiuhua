from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR


@dataclass
class QATConfig:
    batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    min_lr_ratio: float = 0.1
    weight_decay: float = 0.1
    max_steps: int = 10000
    warmup_steps: int = 500
    logging_steps: int = 10
    save_steps: int = 1000
    eval_steps: int = 500
    output_dir: str = "output"
    save_total_limit: int = 3
    fp16: bool = True
    bf16: bool = False
    max_grad_norm: float = 1.0


class QATTrainer:
    def __init__(
        self,
        model: nn.Module,
        train_dataset,
        config: QATConfig,
        eval_dataset=None,
    ):
        self.model = model
        self.config = config
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=4,
            pin_memory=True,
            drop_last=True,
        )
        self.eval_loader = None
        if eval_dataset is not None:
            self.eval_loader = DataLoader(
                eval_dataset,
                batch_size=config.batch_size,
                shuffle=False,
                num_workers=2,
            )
        self.optimizer = self._create_optimizer()
        self.scheduler = self._create_scheduler()
        use_scaler = config.fp16 and not config.bf16
        self.scaler = torch.amp.GradScaler("cuda") if use_scaler else None
        self.global_step = 0
        self.epoch = 0

    def _create_optimizer(self):
        no_decay = ["bias", "layernorm", "scale_re", "scale_im"]
        decay_params = []
        no_decay_params = []
        for n, p in self.model.named_parameters():
            if any(nd in n for nd in no_decay):
                no_decay_params.append(p)
            else:
                decay_params.append(p)
        return AdamW([
            {"params": decay_params, "weight_decay": self.config.weight_decay},
            {"params": no_decay_params, "weight_decay": 0.0},
        ], lr=self.config.learning_rate, betas=(0.9, 0.95), eps=1e-8)

    def _create_scheduler(self):
        def lr_lambda(step):
            effective_step = step + 1
            if effective_step < self.config.warmup_steps:
                return float(effective_step) / float(max(1, self.config.warmup_steps))
            progress = float(effective_step - self.config.warmup_steps) / float(
                max(1, self.config.max_steps - self.config.warmup_steps)
            )
            return self.config.min_lr_ratio + 0.5 * (1 - self.config.min_lr_ratio) * (1 + math.cos(math.pi * progress))
        return torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)

    def train(self):
        self.model.train()
        if next(self.model.parameters()).device.type == "cpu":
            self.model = self.model.cuda()
        accum_loss = 0.0
        self.optimizer.zero_grad()
        data_iter = iter(self.train_loader)

        while self.global_step < self.config.max_steps:
            try:
                batch = next(data_iter)
            except StopIteration:
                data_iter = iter(self.train_loader)
                batch = next(data_iter)

            input_ids = batch["input_ids"].cuda()
            labels = batch["labels"].cuda()
            attention_mask = (input_ids != 0).long()

            dtype = torch.bfloat16 if self.config.bf16 else (torch.float16 if self.config.fp16 else None)
            with torch.amp.autocast("cuda", enabled=dtype is not None, dtype=dtype):
                outputs = self.model(input_ids=input_ids, labels=labels, attention_mask=attention_mask)
                loss = outputs["loss"] / self.config.gradient_accumulation_steps

            if torch.isnan(loss) or torch.isinf(loss):
                print(f"  WARNING: NaN/Inf loss at step {self.global_step}, skipping")
                self.optimizer.zero_grad()
                accum_loss = 0.0
                self.global_step += 1
                continue

            if self.scaler is not None:
                self.scaler.scale(loss).backward()
            else:
                loss.backward()

            accum_loss += loss.item()

            if (self.global_step + 1) % self.config.gradient_accumulation_steps == 0:
                if self.scaler is not None:
                    self.scaler.unscale_(self.optimizer)
                grad_norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                if torch.isnan(grad_norm) or torch.isinf(grad_norm):
                    print(f"  WARNING: NaN grad norm at step {self.global_step}, skipping step")
                    self.optimizer.zero_grad()
                    self.global_step += 1
                    continue
                if self.scaler is not None:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad()

            if self.global_step % self.config.logging_steps == 0 and self.global_step > 0:
                avg_loss = accum_loss / self.config.logging_steps
                lr = self.optimizer.param_groups[0]["lr"]
                print(f"Step {self.global_step}/{self.config.max_steps} | Loss: {avg_loss:.4f} | LR: {lr:.2e}")
                accum_loss = 0.0

            if self.global_step % self.config.save_steps == 0 and self.global_step > 0:
                self.save_checkpoint()

            if (
                self.eval_loader is not None
                and self.global_step % self.config.eval_steps == 0
                and self.global_step > 0
            ):
                self.evaluate()

            self.global_step += 1

        self.save_checkpoint(final=True)
        print("Training complete.")

    @torch.no_grad()
    def evaluate(self):
        self.model.eval()
        total_loss = 0.0
        num_batches = 0
        for batch in self.eval_loader:
            input_ids = batch["input_ids"].cuda()
            labels = batch["labels"].cuda()
            attention_mask = (input_ids != 0).long()
            outputs = self.model(input_ids=input_ids, labels=labels, attention_mask=attention_mask)
            total_loss += outputs["loss"].item()
            num_batches += 1
            if num_batches >= 20:
                break
        avg_loss = total_loss / num_batches
        perplexity = math.exp(avg_loss)
        print(f"  Eval | Step {self.global_step} | Loss: {avg_loss:.4f} | PPL: {perplexity:.2f}")
        self.model.train()

    def save_checkpoint(self, final: bool = False):
        output_dir = self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        step_str = "final" if final else f"step_{self.global_step}"
        path = os.path.join(output_dir, f"checkpoint-{step_str}")
        os.makedirs(path, exist_ok=True)
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.scheduler.state_dict(),
            "global_step": self.global_step,
            "config": self.config,
        }, os.path.join(path, "pytorch_model.bin"))
        print(f"  Saved checkpoint to {path}")
