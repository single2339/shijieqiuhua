from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FairyQuantizer(nn.Module):
    """
    iFairy quantization: project complex weights to {±1, ±i} (4th roots of unity).
    
    Each weight w = w_re + i*w_im is mapped to the nearest codeword:
      - argmax(|w_re|, |w_im|) determines axis
      - sign determines ±
    
    After quantization applies per-tensor scaling factors γ_re, γ_im.
    Uses Straight-Through Estimator (STE) for gradient flow.
    """

    def __init__(self):
        super().__init__()
        self.scale_re = nn.Parameter(torch.ones(1))
        self.scale_im = nn.Parameter(torch.ones(1))

    def quantize(self, w_re: torch.Tensor, w_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        abs_re, abs_im = w_re.abs(), w_im.abs()
        use_re = abs_re >= abs_im
        w_q_re = torch.where(use_re, w_re.sign(), torch.zeros_like(w_re))
        w_q_im = torch.where(~use_re, w_im.sign(), torch.zeros_like(w_im))
        return w_q_re, w_q_im

    def forward(self, w_re: torch.Tensor, w_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        with torch.no_grad():
            w_q_re, w_q_im = self.quantize(w_re, w_im)
        w_q_re = w_q_re * self.scale_re
        w_q_im = w_q_im * self.scale_im
        ste_re = (w_re - w_re.detach()) + w_q_re
        ste_im = (w_im - w_im.detach()) + w_q_im
        return ste_re, ste_im
