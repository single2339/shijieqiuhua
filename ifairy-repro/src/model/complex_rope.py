from __future__ import annotations

import torch
import torch.nn as nn


class ComplexRoPE(nn.Module):
    def __init__(self, head_dim: int, max_seq_len: int = 4096, base: float = 10000.0):
        super().__init__()
        self.head_dim = head_dim
        rope_dim = head_dim * 2
        inv_freq = 1.0 / (base ** (torch.arange(0, rope_dim, 2, dtype=torch.float32) / rope_dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        self._build_cos_sin(max_seq_len, rope_dim)

    def _build_cos_sin(self, max_seq_len: int, rope_dim: int):
        t = torch.arange(max_seq_len, dtype=torch.float32, device=self.inv_freq.device)
        freqs = torch.outer(t, self.inv_freq)
        emb = torch.cat([freqs, freqs], dim=-1)
        self.register_buffer("cos_cached", emb.cos(), persistent=False)
        self.register_buffer("sin_cached", emb.sin(), persistent=False)

    def forward(self, x_re: torch.Tensor, x_im: torch.Tensor, position_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        seq_len = position_ids.max().item() + 1
        if seq_len > self.cos_cached.shape[0]:
            self._build_cos_sin(seq_len * 2, self.cos_cached.shape[-1])
        cos = self.cos_cached[position_ids].unsqueeze(1).to(x_re.dtype)
        sin = self.sin_cached[position_ids].unsqueeze(1).to(x_re.dtype)
        x_concat = torch.cat([x_re, x_im], dim=-1)
        x_rot = x_concat * cos + self._rotate_half(x_concat) * sin
        return x_rot[..., :self.head_dim], x_rot[..., self.head_dim:]

    @staticmethod
    def _rotate_half(x: torch.Tensor) -> torch.Tensor:
        x1, x2 = x.chunk(2, dim=-1)
        return torch.cat([-x2, x1], dim=-1)
