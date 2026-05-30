from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
from model.complex_llama import ComplexLlamaConfig, ComplexLlamaForCausalLM
from training.qat_trainer import QATTrainer, QATConfig
from torch.utils.data import Dataset

config = ComplexLlamaConfig(
    vocab_size=50257,
    hidden_size=1024,
    intermediate_size=2752,
    num_hidden_layers=8,
    num_attention_heads=8,
    num_key_value_heads=8,
    max_seq_len=2048,
    use_quantized=True,
    initializer_range=0.01,
)

print(f"Building ComplexLlama (L{config.num_hidden_layers} H{config.hidden_size})...")
model = ComplexLlamaForCausalLM(config)
params = sum(p.numel() for p in model.parameters())
print(f"Total params: {params:,} (~{params * 2 / 1e9:.1f}GB bf16)")

print("Moving to GPU...")
model = model.cuda()
mem = torch.cuda.memory_allocated(0)
print(f"GPU memory: {mem/1e9:.1f}GB / {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")

print("Loading dataset...")
from transformers import AutoTokenizer
import sys

tokenizer_path = "/home/ubuntu/ifairy-repro/gpt2-tokenizer"
tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print(f"Tokenizer vocab: {tokenizer.vocab_size}")

data_file = "/home/ubuntu/ifairy-repro/data/wikitext_train.txt"
with open(data_file, "r") as f:
    raw_text = f.read()

encoded = tokenizer.encode(raw_text)
print(f"Tokens: {len(encoded):,}")

seq_len = 2048
chunk = seq_len + 1
total_len = (len(encoded) // chunk) * chunk
encoded = encoded[:total_len]
data = torch.tensor(encoded, dtype=torch.long).view(-1, chunk)
num_samples = data.size(0)
print(f"Dataset: {num_samples} samples of {seq_len} tokens")

class TokenDataset(Dataset):
    def __init__(self, data):
        self.data = data
    def __len__(self):
        return len(self.data)
    def __getitem__(self, idx):
        chunk = self.data[idx]
        return {"input_ids": chunk[:-1], "labels": chunk[1:]}

train_dataset = TokenDataset(data[:num_samples * 9 // 10])
eval_dataset = TokenDataset(data[num_samples * 9 // 10:])
print(f"Train: {len(train_dataset)}, Eval: {len(eval_dataset)}")

train_cfg = QATConfig()
train_cfg.batch_size = 4
train_cfg.gradient_accumulation_steps = 2
train_cfg.learning_rate = 2e-4
train_cfg.max_steps = 10000
train_cfg.warmup_steps = 500
train_cfg.logging_steps = 5
train_cfg.save_steps = 500
train_cfg.output_dir = "./output_full"
train_cfg.fp16 = False
train_cfg.bf16 = False
train_cfg.weight_decay = 0.1
train_cfg.max_grad_norm = 1.0

trainer = QATTrainer(model, train_dataset, train_cfg)
trainer.train()
