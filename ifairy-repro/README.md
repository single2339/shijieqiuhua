# iFairy Reproduction

Reproduction of ["iFairy: the First 2-bit Complex LLM with All Parameters in {±1, ±i}"](https://arxiv.org/abs/2508.05571).

## Quick Start (Tiny Model for Testing)

```bash
pip install -r requirements.txt
python scripts/train.py --model_type tiny --output_dir ./output
```

## Full Reproduction (Llama-2-7B)

### 1. Server Setup

```bash
bash setup_server.sh
source ifairy-env/bin/activate
```

### 2. Get Llama-2-7B weights

```bash
huggingface-cli login  # with your HF token
bash scripts/download_llama.sh
```

### 3. Train

```bash
python scripts/train.py \
  --model_type llama2_7b \
  --output_dir ./output \
  --max_steps 10000 \
  --batch_size 4
```

## Architecture

| Module | File | Description |
|--------|------|-------------|
| `FairyQuantizer` | `src/model/fairy_quantizer.py` | Project weights to {±1, ±i} with STE |
| `ComplexLinearQuant` | `src/model/complex_linear.py` | Quantized complex linear layer |
| `ComplexRoPE` | `src/model/complex_rope.py` | Rotary position via complex rotation |
| `ComplexRMSNorm` | `src/model/complex_norm.py` | RMS norm on complex components |
| `ComplexLlamaForCausalLM` | `src/model/complex_llama.py` | Full Llama with complex weights |
| `QATTrainer` | `src/training/qat_trainer.py` | QAT training loop with STE |

## Key Implementation Details

- **Weight quantizer**: maps to {±1, ±i} based on phase (argmax of |Re|, |Im|)
- **STE**: Straight-Through Estimator for gradient flow through quantizer
- **Scaling factors**: per-tensor γ_re, γ_im learned jointly
- **Complex linear**: (W_re + iW_im)(x_re + ix_im) = (W_re x_re - W_im x_im) + i(W_re x_im + W_im x_re)
- **Multiplication-free**: each quantized weight has one zero component → addition + swap only
- **Complex RoPE**: rotation as complex multiplication z·e^(iθ)
- **SwiGLU**: SiLU activation applied to complex magnitude, then gating on complex output

## Citation

```bibtex
@article{wang2025ifairy,
  title={iFairy: the First 2-bit Complex LLM with All Parameters in {±1, ±i}},
  author={Wang, Feiyu and Wang, Guoan and Zhang, Yihao and others},
  journal={arXiv preprint arXiv:2508.05571},
  year={2025}
}
```
