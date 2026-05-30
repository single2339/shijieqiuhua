from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .complex_linear import ComplexLinear, ComplexLinearQuant
from .complex_norm import ComplexRMSNorm
from .complex_rope import ComplexRoPE
from .fairy_quantizer import FairyQuantizer


@dataclass
class ComplexLlamaConfig:
    vocab_size: int = 32000
    hidden_size: int = 4096
    intermediate_size: int = 11008
    num_hidden_layers: int = 32
    num_attention_heads: int = 32
    num_key_value_heads: int = 32
    max_seq_len: int = 4096
    rms_norm_eps: float = 1e-6
    rope_base: float = 10000.0
    rope_dim: Optional[int] = None
    use_quantized: bool = True
    initializer_range: float = 0.02

    @classmethod
    def from_llama2_7b(cls) -> ComplexLlamaConfig:
        return cls(
            vocab_size=32000,
            hidden_size=4096,
            intermediate_size=11008,
            num_hidden_layers=32,
            num_attention_heads=32,
            num_key_value_heads=32,
            max_seq_len=4096,
        )

    @classmethod
    def tiny(cls) -> ComplexLlamaConfig:
        return cls(
            vocab_size=32000,
            hidden_size=512,
            intermediate_size=1376,
            num_hidden_layers=8,
            num_attention_heads=8,
            num_key_value_heads=8,
            max_seq_len=2048,
            use_quantized=True,
        )


class ComplexAttention(nn.Module):
    def __init__(self, config: ComplexLlamaConfig, layer_idx: int):
        super().__init__()
        self.config = config
        self.layer_idx = layer_idx
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.head_dim = config.hidden_size // config.num_attention_heads
        self.num_kv_heads = config.num_key_value_heads
        self.num_key_value_groups = self.num_heads // self.num_kv_heads

        linear_cls = ComplexLinearQuant if config.use_quantized else ComplexLinear
        self.q_proj = linear_cls(config.hidden_size, config.num_attention_heads * self.head_dim, bias=False)
        self.k_proj = linear_cls(config.hidden_size, self.num_kv_heads * self.head_dim, bias=False)
        self.v_proj = linear_cls(config.hidden_size, self.num_kv_heads * self.head_dim, bias=False)
        self.o_proj = linear_cls(config.num_attention_heads * self.head_dim, config.hidden_size, bias=False)

        rope_dim = config.rope_dim or self.head_dim
        self.rotary_emb = ComplexRoPE(rope_dim, config.max_seq_len, config.rope_base)

    def forward(
        self,
        h_re: torch.Tensor, h_im: torch.Tensor,
        position_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        bsz, seq_len, _ = h_re.shape
        q_re, q_im = self.q_proj(h_re, h_im)
        k_re, k_im = self.k_proj(h_re, h_im)
        v_re, v_im = self.v_proj(h_re, h_im)

        q_re = q_re.view(bsz, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        q_im = q_im.view(bsz, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k_re = k_re.view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        k_im = k_im.view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v_re = v_re.view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v_im = v_im.view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)

        q_re, q_im = self._apply_rope(q_re, q_im, position_ids)
        k_re, k_im = self._apply_rope(k_re, k_im, position_ids)

        if self.num_key_value_groups > 1:
            k_re = k_re.repeat_interleave(self.num_key_value_groups, dim=1)
            k_im = k_im.repeat_interleave(self.num_key_value_groups, dim=1)
            v_re = v_re.repeat_interleave(self.num_key_value_groups, dim=1)
            v_im = v_im.repeat_interleave(self.num_key_value_groups, dim=1)

        attn_re = torch.matmul(q_re.float(), k_re.float().transpose(-2, -1)) + torch.matmul(q_im.float(), k_im.float().transpose(-2, -1))
        attn_im = torch.matmul(q_im.float(), k_re.float().transpose(-2, -1)) - torch.matmul(q_re.float(), k_im.float().transpose(-2, -1))
        attn_re = attn_re / (self.head_dim ** 0.5)
        attn_im = attn_im / (self.head_dim ** 0.5)

        if attention_mask is not None:
            attn_re = attn_re + attention_mask.float()
            attn_im = attn_im + attention_mask.float() * 0

        attn_abs = (attn_re ** 2 + attn_im ** 2).sqrt() + 1e-10
        attn_weights = F.softmax(attn_abs, dim=-1, dtype=torch.float32)

        out_re = torch.matmul(attn_weights, v_re.float())
        out_im = torch.matmul(attn_weights, v_im.float())
        out_re = out_re.to(h_re.dtype).transpose(1, 2).contiguous().reshape(bsz, seq_len, -1)
        out_im = out_im.to(h_im.dtype).transpose(1, 2).contiguous().reshape(bsz, seq_len, -1)

        out_re, out_im = self.o_proj(out_re, out_im)
        return out_re, out_im

    def _apply_rope(self, x_re: torch.Tensor, x_im: torch.Tensor, position_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.rotary_emb(x_re, x_im, position_ids)


class ComplexMLP(nn.Module):
    def __init__(self, config: ComplexLlamaConfig):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.intermediate_size = config.intermediate_size
        linear_cls = ComplexLinearQuant if config.use_quantized else ComplexLinear
        self.gate_proj = linear_cls(self.hidden_size, self.intermediate_size, bias=False)
        self.up_proj = linear_cls(self.hidden_size, self.intermediate_size, bias=False)
        self.down_proj = linear_cls(self.intermediate_size, self.hidden_size, bias=False)
        self.act_fn = F.silu

    def forward(self, x_re: torch.Tensor, x_im: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        g_re, g_im = self.gate_proj(x_re, x_im)
        u_re, u_im = self.up_proj(x_re, x_im)
        g_re = g_re.float(); g_im = g_im.float(); u_re = u_re.float(); u_im = u_im.float()
        g_mag = (g_re ** 2 + g_im ** 2).sqrt() + 1e-10
        gate_re = self.act_fn(g_mag) * (g_re / g_mag)
        gate_im = self.act_fn(g_mag) * (g_im / g_mag)
        out_re = (gate_re * u_re - gate_im * u_im).to(x_re.dtype)
        out_im = (gate_re * u_im + gate_im * u_re).to(x_re.dtype)
        out_re, out_im = self.down_proj(out_re, out_im)
        return out_re, out_im


class ComplexDecoderLayer(nn.Module):
    def __init__(self, config: ComplexLlamaConfig, layer_idx: int):
        super().__init__()
        self.self_attn = ComplexAttention(config, layer_idx)
        self.mlp = ComplexMLP(config)
        self.input_layernorm = ComplexRMSNorm(config.hidden_size, eps=config.rms_norm_eps)
        self.post_attention_layernorm = ComplexRMSNorm(config.hidden_size, eps=config.rms_norm_eps)

    def forward(
        self,
        h_re: torch.Tensor, h_im: torch.Tensor,
        position_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        residual_re, residual_im = h_re, h_im
        h_re, h_im = self.input_layernorm(h_re, h_im)
        attn_re, attn_im = self.self_attn(h_re, h_im, position_ids, attention_mask)
        h_re = residual_re + attn_re
        h_im = residual_im + attn_im
        residual_re, residual_im = h_re, h_im
        h_re, h_im = self.post_attention_layernorm(h_re, h_im)
        mlp_re, mlp_im = self.mlp(h_re, h_im)
        h_re = residual_re + mlp_re
        h_im = residual_im + mlp_im
        return h_re, h_im


class ComplexLlamaModel(nn.Module):
    def __init__(self, config: ComplexLlamaConfig):
        super().__init__()
        self.config = config
        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
        self.embed_imag = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = nn.ModuleList([
            ComplexDecoderLayer(config, i) for i in range(config.num_hidden_layers)
        ])
        self.norm = ComplexRMSNorm(config.hidden_size, eps=config.rms_norm_eps)

    def forward(
        self,
        input_ids: torch.Tensor,
        position_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if position_ids is None:
            position_ids = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
        if attention_mask is not None and attention_mask.dim() == 2:
            attention_mask = attention_mask[:, None, None, :]
        h_re = self.embed_tokens(input_ids)
        h_im = self.embed_imag(input_ids)
        for layer in self.layers:
            h_re, h_im = layer(h_re, h_im, position_ids, attention_mask)
        h_re, h_im = self.norm(h_re, h_im)
        return h_re, h_im


class ComplexLlamaForCausalLM(nn.Module):
    def __init__(self, config: ComplexLlamaConfig):
        super().__init__()
        self.config = config
        self.model = ComplexLlamaModel(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.lm_head_complex = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.loss_fn = nn.CrossEntropyLoss()

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.Tensor] = None,
    ) -> dict:
        h_re, h_im = self.model(input_ids, position_ids, attention_mask)
        logits = self.lm_head(h_re) + self.lm_head_complex(h_im)
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = self.loss_fn(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
        return {"loss": loss, "logits": logits}

    def init_weights(self):
        for module in self.modules():
            if isinstance(module, (nn.Linear, nn.Embedding)):
                module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)

    def get_num_params(self) -> int:
        return sum(p.numel() for p in self.parameters())
