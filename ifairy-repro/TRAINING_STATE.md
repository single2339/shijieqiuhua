# Training State — iFairy Reproduction

**Server**: ubuntu@10.13.45.20  
**SSH**: `sshpass -p 'zhangnanxin' ssh -o BindInterface=en0 ubuntu@10.13.45.20`  
**Model**: ComplexLlama L8 H1024, ~408M params, fp32, **`use_quantized=True` (量化已开启)**  
**Quantizer**: FairyQuantizer {±1, ±i} + STE  
**Dataset**: synthetic random tokens  
**Training**: 10000 steps, LR peak 2e-4, warmup 500, grad_accum 2  
**Session**: tmux `ifairy`  
**Log**: `/tmp/train.log`  
**Output**: `~/ifairy-repro/output_full/`

## Quick Recovery

```bash
# SSH (网卡可能变化: en0=en6=WiFi)
sshpass -p 'zhangnanxin' ssh -o BindInterface=en0 ubuntu@10.13.45.20 "tail -5 /tmp/train.log"

# 进入训练会话
sshpass -p 'zhangnanxin' ssh -o BindInterface=en0 ubuntu@10.13.45.20 "tmux attach -t ifairy"
```

## Project Files

- 模型代码: `src/model/complex_llama.py`, `complex_linear.py`, `fairy_quantizer.py`, `complex_rope.py`, `complex_norm.py`
- 训练: `src/training/qat_trainer.py`, `scripts/run_full.py`
- 配置: `scripts/run_full.py` (内嵌配置)

## Issues

1. bf16 + STE → NaN (需修复)
2. 服务器无外网 → tokenizer 和数据集需本地提供
3. 网卡可能从 en6 变 en0（WiFi vs 有线切换），需检查 `ifconfig | grep "inet"` 确定
