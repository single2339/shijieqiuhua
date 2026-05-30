from __future__ import annotations

from typing import Optional

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer


class TextDataset(Dataset):
    def __init__(self, texts: list[str], tokenizer, block_size: int = 2048):
        self.block_size = block_size
        self.tokenizer = tokenizer
        tokens = tokenizer(texts, return_tensors=None, truncation=False)["input_ids"]
        self.data = torch.cat([torch.tensor(t, dtype=torch.long) for t in tokens])
        self.num_blocks = len(self.data) // block_size

    def __len__(self) -> int:
        return self.num_blocks

    def __getitem__(self, idx: int) -> dict:
        start = idx * self.block_size
        chunk = self.data[start:start + self.block_size + 1]
        return {
            "input_ids": chunk[:-1],
            "labels": chunk[1:],
        }


def get_c4_dataset(
    tokenizer_name: str = "meta-llama/Llama-2-7b-hf",
    block_size: int = 2048,
    split: str = "train",
    max_samples: Optional[int] = None,
) -> Dataset:
    from datasets import load_dataset
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    ds = load_dataset("c4", "en", split=split, streaming=False)
    texts = []
    for i, example in enumerate(ds):
        if max_samples is not None and i >= max_samples:
            break
        texts.append(example["text"])
    return TextDataset(texts, tokenizer, block_size)


def get_wikitext_dataset(
    tokenizer_name: str = "meta-llama/Llama-2-7b-hf",
    block_size: int = 2048,
    split: str = "train",
) -> Dataset:
    from datasets import load_dataset
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    ds = load_dataset("wikitext", "wikitext-103-raw-v1", split=split)
    texts = [example["text"] for example in ds]
    return TextDataset(texts, tokenizer, block_size)
