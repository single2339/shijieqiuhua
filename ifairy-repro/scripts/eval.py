import os, sys, math, time
sys.path.insert(0, 'src')
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
import torch
from transformers import AutoTokenizer
from model.complex_llama import ComplexLlamaConfig, ComplexLlamaForCausalLM
from model.complex_linear import ComplexLinearQuant

torch.set_grad_enabled(False)
config = ComplexLlamaConfig(vocab_size=50257,hidden_size=1024,intermediate_size=2752,num_hidden_layers=8,num_attention_heads=8,num_key_value_heads=8,max_seq_len=2048,use_quantized=True)
print('Loading model...')
model = ComplexLlamaForCausalLM(config).cuda()
ckpt = torch.load('./output_full/checkpoint-final/pytorch_model.bin', map_location='cuda', weights_only=False)
model.load_state_dict(ckpt['model_state_dict'], strict=False)
model.eval()

stats = {'+1':0,'-1':0,'+i':0,'-i':0}
qs = [m for m in model.modules() if isinstance(m, ComplexLinearQuant)]
for m in qs:
    q = m.quantizer
    qr, qi = q.quantize(m.w_re, m.w_im)
    s = qr.flatten().cpu().sign().int()
    stats['+1'] += (s==1).sum().item()
    stats['-1'] += (s==-1).sum().item()
    s = qi.flatten().cpu().sign().int()
    stats['+i'] += (s==1).sum().item()
    stats['-i'] += (s==-1).sum().item()
t = sum(stats.values())
total_p = sum(p.numel() for p in model.parameters())
q_p = sum(p.numel() for m in model.modules() if isinstance(m, ComplexLinearQuant) for p in m.parameters())

print('\n=== Quantization Stats ===')
for k in ['+1','+i','-1','-i']:
    print(f'  {k:>5}: {stats[k]:>10,} ({stats[k]/t*100:.1f}%)')
print(f'  Quant params: {q_p/1e6:.1f}M / {total_p/1e6:.1f}M total ({q_p/total_p*100:.1f}%)')
print(f'  2-bit storage: ~{q_p*2/8/1e6:.1f} MB (vs fp32: {total_p*4/1e9:.2f} GB)')
sc = [(m.quantizer.scale_re.item(), m.quantizer.scale_im.item()) for m in qs[:5]]
print(f'  Scale factors (re,im): {[(round(s[0],4),round(s[1],4)) for s in sc]}')

print('\n=== Perplexity ===')
tok = AutoTokenizer.from_pretrained('./gpt2-tokenizer', pad_token='<|endoftext|>')
raw = open('./data/wikitext_train.txt').read()
enc = tok.encode(raw)
chunk = 2049
enc = enc[:(len(enc)//chunk)*chunk]
dt = torch.tensor(enc, dtype=torch.long).view(-1, chunk)
ev = dt[len(dt)*9//10:][:5]
loss = 0.0
for i in range(len(ev)):
    b = ev[i:i+1].cuda()
    o = model(input_ids=b[:,:-1], labels=b[:,1:])
    loss += o['loss'].item() * (chunk-1)
ppl = math.exp(loss/(len(ev)*(chunk-1)))
print(f'  Eval Loss: {loss/(len(ev)*(chunk-1)):.4f}')
print(f'  PPL: {ppl:.2f}')

print('\n=== Inference Speed ===')
for bs in [1,8,16]:
    inp = torch.randint(0,1000,(bs,256)).cuda()
    model(input_ids=inp)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(10):
        model(input_ids=inp)
    torch.cuda.synchronize()
    t_ms = (time.time()-t0)/10*1000
    print(f'  Batch {bs:>2}x256: {t_ms:.0f}ms, {bs*256/t_ms*1000:.0f} tok/s')
