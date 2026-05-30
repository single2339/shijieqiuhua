from __future__ import annotations

import argparse
import yaml
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from model.complex_llama import ComplexLlamaConfig, ComplexLlamaForCausalLM
from training.dataset import get_c4_dataset, get_wikitext_dataset
from training.qat_trainer import QATTrainer, QATConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="YAML config file")
    parser.add_argument("--model_type", type=str, default="tiny", help="tiny | llama2_7b")
    parser.add_argument("--output_dir", type=str, default="./output")
    parser.add_argument("--max_steps", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=None)
    parser.add_argument("--learning_rate", type=float, default=None)
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--tokenizer", type=str, default=None)
    parser.add_argument("--max_samples", type=int, default=None)
    args = parser.parse_args()

    config_dict = {}
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config_dict = yaml.safe_load(f)

    model_type = args.model_type or config_dict.get("model", {}).get("type", "tiny")
    use_quantized = config_dict.get("model", {}).get("use_quantized", True)

    if model_type == "tiny":
        model_config = ComplexLlamaConfig.tiny()
    elif model_type == "llama2_7b":
        model_config = ComplexLlamaConfig.from_llama2_7b()
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    model_config.use_quantized = use_quantized

    print(f"Building ComplexLlama model ({model_type})...")
    model = ComplexLlamaForCausalLM(model_config)
    print(f"Total parameters: {model.get_num_params():,}")

    train_cfg = QATConfig()
    train_cfg.output_dir = args.output_dir
    tc = config_dict.get("training", {})
    for attr in ["batch_size", "gradient_accumulation_steps", "learning_rate",
                 "max_steps", "warmup_steps", "logging_steps", "save_steps",
                 "eval_steps", "fp16", "bf16", "max_grad_norm", "weight_decay"]:
        val = tc.get(attr, getattr(train_cfg, attr, None))
        if val is not None:
            setattr(train_cfg, attr, val)

    if args.max_steps is not None:
        train_cfg.max_steps = args.max_steps
    if args.batch_size is not None:
        train_cfg.batch_size = args.batch_size
    if args.gradient_accumulation_steps is not None:
        train_cfg.gradient_accumulation_steps = args.gradient_accumulation_steps
    if args.learning_rate is not None:
        train_cfg.learning_rate = args.learning_rate

    dc = config_dict.get("dataset", {})
    dataset_name = args.dataset or dc.get("name", "wikitext")
    tokenizer_name = args.tokenizer or dc.get("tokenizer", "hf-internal-testing/llama-tokenizer")
    block_size = dc.get("block_size", 2048)
    max_samples = args.max_samples or dc.get("max_samples", None)

    print(f"Loading {dataset_name} dataset...")
    if dataset_name == "c4":
        train_dataset = get_c4_dataset(tokenizer_name, block_size, split="train", max_samples=max_samples)
    elif dataset_name == "wikitext":
        train_dataset = get_wikitext_dataset(tokenizer_name, block_size, split="train")
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    eval_dataset = None
    if dataset_name == "c4":
        eval_dataset = get_c4_dataset(tokenizer_name, block_size, split="validation", max_samples=500)
    elif dataset_name == "wikitext":
        eval_dataset = get_wikitext_dataset(tokenizer_name, block_size, split="test")

    trainer = QATTrainer(model, train_dataset, train_cfg, eval_dataset)
    trainer.train()


if __name__ == "__main__":
    main()
