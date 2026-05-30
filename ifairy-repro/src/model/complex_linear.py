from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .fairy_quantizer import FairyQuantizer


class ComplexLinear(nn.Module):
    """
    Full-precision complex-valued linear layer.
    Weight: W = W_re + i*W_im,  Bias: b = b_re + i*b_im
    Output: y = W @ x + b (complex matrix multiply)
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        scale = 1 / (in_features ** 0.5)
        self.w_re = nn.Parameter(torch.randn(out_features, in_features) * scale)
        self.w_im = nn.Parameter(torch.randn(out_features, in_features) * scale)
        if bias:
            self.b_re = nn.Parameter(torch.zeros(out_features))
            self.b_im = nn.Parameter(torch.zeros(out_features))
        else:
            self.b_re = None
            self.b_im = None

    def forward(self, x_re: torch.Tensor, x_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        out_re = F.linear(x_re, self.w_re) - F.linear(x_im, self.w_im)
        out_im = F.linear(x_re, self.w_im) + F.linear(x_im, self.w_re)
        if self.b_re is not None:
            out_re = out_re + self.b_re
            out_im = out_im + self.b_im
        return out_re, out_im


class ComplexLinearQuant(nn.Module):
    """
    Quantized complex linear layer with {±1, ±i} weights.
    Uses FairyQuantizer + STE during training.
    Multiplication-free: weights in {±1, ±i} → only additions and swaps.
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        scale = 1 / (in_features ** 0.5)
        self.w_re = nn.Parameter(torch.randn(out_features, in_features) * scale)
        self.w_im = nn.Parameter(torch.randn(out_features, in_features) * scale)
        self.quantizer = FairyQuantizer()
        if bias:
            self.b_re = nn.Parameter(torch.zeros(out_features))
            self.b_im = nn.Parameter(torch.zeros(out_features))
        else:
            self.b_re = None
            self.b_im = None

    def forward(self, x_re: torch.Tensor, x_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        w_q_re, w_q_im = self.quantizer(self.w_re, self.w_im)
        out_re = F.linear(x_re, w_q_re) - F.linear(x_im, w_q_im)
        out_im = F.linear(x_re, w_q_im) + F.linear(x_im, w_q_re)
        if self.b_re is not None:
            out_re = out_re + self.b_re
            out_im = out_im + self.b_im
        return out_re, out_im

    @torch.no_grad()
    def inference(self, x_re: torch.Tensor, x_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        w_q_re, w_q_im = self.quantizer.quantize(self.w_re, self.w_im)
        scale_re = self.quantizer.scale_re
        scale_im = self.quantizer.scale_im
        w_q_re = w_q_re * scale_re
        w_q_im = w_q_im * scale_im
        w_q_re = w_q_re.to_sparse()
        w_q_im = w_q_im.to_sparse()
        out_re = F.linear(x_re, w_q_re.to_dense()) - F.linear(x_im, w_q_im.to_dense())
        out_im = F.linear(x_re, w_q_im.to_dense()) + F.linear(x_im, w_q_re.to_dense())
        if self.b_re is not None:
            out_re = out_re + self.b_re
            out_im = out_im + self.b_im
        return out_re, out_im
