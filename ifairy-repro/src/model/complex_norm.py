from __future__ import annotations

import torch
import torch.nn as nn


class ComplexRMSNorm(nn.Module):
    """
    RMS Norm applied independently to real and imaginary components.
    """

    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x_re: torch.Tensor, x_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        norm_re = x_re * torch.rsqrt(x_re.pow(2).mean(-1, keepdim=True) + self.eps)
        norm_im = x_im * torch.rsqrt(x_im.pow(2).mean(-1, keepdim=True) + self.eps)
        return norm_re * self.weight, norm_im * self.weight
