import os, sys, time
sys.path.insert(0, 'src')
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch
from model.complex_llama import ComplexLlamaConfig, ComplexLlamaForCausalLM

torch.set_grad_enabled(False)
config = ComplexLlamaConfig(
    vocab_size=50257, hidden_size=1024, intermediate_size=2752,
    num_hidden_layers=8, num_attention_heads=8, num_key_value_heads=8,
    max_seq_len=2048, use_quantized=True,
)
print('Loading model to CPU...')
model = ComplexLlamaForCausalLM(config)
ckpt = torch.load('./output_full/checkpoint-final/pytorch_model.bin',
                   map_location='cpu', weights_only=False)
model.load_state_dict(ckpt['model_state_dict'], strict=False)
model.eval()
params = sum(p.numel() for p in model.parameters())
print(f'Model: {params/1e6:.0f}M params, CPU cores: {os.cpu_count()}')
print()

for bs in [1, 4, 8]:
    for sl in [64, 128, 256]:
        inp = torch.randint(0, 1000, (bs, sl))
        model(input_ids=inp)
        t0 = time.time()
        n = 5
        for _ in range(n):
            model(input_ids=inp)
        t = (time.time() - t0) / n * 1000
        tok_s = bs * sl / t * 1000
        print(f'  batch {bs}x{sl:>3}: {t:>6.0f}ms, {tok_s:>6.0f} tok/s')
    print()
