"""PTQ: Post-Training Quantization of any HF model with {±1, ±i} FairyQuantizer."""
import os, sys, time, math
sys.path.insert(0, 'src')

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from model.fairy_quantizer import FairyQuantizer

torch.set_grad_enabled(False)

MODEL_ID = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3.6-27B"
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "quantized_model"

print(f"Loading {MODEL_ID}...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto"
)
tok = AutoTokenizer.from_pretrained(MODEL_ID)
orig_params = sum(p.numel() for p in model.parameters())
print(f"Original params: {orig_params/1e9:.1f}B")

print("Converting Linear layers to ComplexLinearQuant...")
linear_count = 0
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Linear):
        parent = model
        path = name.split(".")
        for p in path[:-1]:
            parent = getattr(parent, p)
        setattr(parent, path[-1], QuantizedLinearWrapper(module))
        linear_count += 1

print(f"Converted {linear_count} Linear layers")

total_quant_params = 0
quant_stats = {"+1": 0, "-1": 0, "+i": 0, "-i": 0}

for name, module in model.named_modules():
    if hasattr(module, "quantize_weights") and hasattr(module, "get_quant_stats"):
        module.quantize_weights()
        s = module.get_quant_stats()
        total_quant_params += sum(s.values())
        for k, v in s.items():
            quant_stats[k] += v

print(f"\n=== Quantization Stats ===")
print(f"  Quantized params: {total_quant_params/1e9:.2f}B / {orig_params/1e9:.1f}B")
for k, v in sorted(quant_stats.items()):
    print(f"  {k:>5}: {v:>12,} ({v/total_quant_params*100:.1f}%)")
storage_bits = 2
orig_bits = 32
print(f"  Storage: {total_quant_params * storage_bits / 8 / 1e9:.2f} GB ({storage_bits}-bit)")
print(f"  vs fp32: {orig_params * orig_bits / 8 / 1e9:.2f} GB")

print(f"\nSaving quantized model to {OUTPUT}/")
model.save_pretrained(OUTPUT)
tok.save_pretrained(OUTPUT)
print("Done!")


class QuantizedLinearWrapper(torch.nn.Module):
    """Wraps an nn.Linear, replacing its weight with quantized {±1, ±i}."""

    def __init__(self, linear: torch.nn.Linear):
        super().__init__()
        self.in_features = linear.in_features
        self.out_features = linear.out_features
        self.bias = linear.bias
        self._original_weight = linear.weight.data.clone()
        self.quantizer = FairyQuantizer()
        self._quantized = False

    def quantize_weights(self):
        if self._quantized:
            return
        w = self._original_weight.float()
        dim = min(self.in_features, self.out_features)
        half = self.in_features // 2
        w_re = w[:, :half]
        w_im = w[:, half:]
        self.quantizer.w_re = torch.nn.Parameter(w_re.to(self.quantizer.scale_re.device))
        self.quantizer.w_im = torch.nn.Parameter(w_im.to(self.quantizer.scale_im.device))
        self.quantizer.scale_re.data = w_re.abs().mean()
        self.quantizer.scale_im.data = w_im.abs().mean()
        self._quantized = True

    def get_quant_stats(self):
        if not self._quantized:
            return {}
        qr, qi = self.quantizer.quantize(
            self.quantizer.w_re, self.quantizer.w_im
        )
        stats = {"+1": 0, "-1": 0, "+i": 0, "-i": 0}
        s = qr.flatten().cpu().sign().int()
        stats["+1"] += (s == 1).sum().item()
        stats["-1"] += (s == -1).sum().item()
        s = qi.flatten().cpu().sign().int()
        stats["+i"] += (s == 1).sum().item()
        stats["-i"] += (s == -1).sum().item()
        return stats

    def forward(self, x):
        if not self._quantized:
            return torch.nn.functional.linear(x, self._original_weight.to(x.dtype), self.bias)
        w_q_re, w_q_im = self.quantizer(self.quantizer.w_re, self.quantizer.w_im)
        x_re, x_im = x[:, :self.in_features // 2], x[:, self.in_features // 2:]
        x_re = x_re.to(w_q_re.dtype)
        x_im = x_im.to(w_q_im.dtype)
        out_re = torch.nn.functional.linear(x_re, w_q_re) - torch.nn.functional.linear(x_im, w_q_im)
        out_im = torch.nn.functional.linear(x_re, w_q_im) + torch.nn.functional.linear(x_im, w_q_re)
        out = out_re + out_im
        if self.bias is not None:
            out = out + self.bias.to(out.dtype)
        return out.to(x.dtype)
