#!/usr/bin/env bash
set -euo pipefail

echo "=== Downloading Llama-2-7B ==="
echo ""
echo "NOTE: Llama-2 requires approval from Meta."
echo "1. Visit: https://huggingface.co/meta-llama/Llama-2-7b-hf"
echo "2. Click 'Agree and access repository'"
echo "3. Run: huggingface-cli login"
echo "4. Then run this script again."
echo ""

if [ -z "${HF_TOKEN:-}" ]; then
  echo "HF_TOKEN not set. Trying huggingface-cli..."
  huggingface-cli whoami 2>/dev/null || {
    echo "Not logged in. Run: huggingface-cli login"
    exit 1
  }
fi

MODEL_DIR="models/llama2-7b"
mkdir -p "$MODEL_DIR"

echo "Downloading Llama-2-7B-HF to $MODEL_DIR..."
python3 -c "
from transformers import LlamaForCausalLM, LlamaTokenizer
import os
model = LlamaForCausalLM.from_pretrained('meta-llama/Llama-2-7b-hf', token=os.environ.get('HF_TOKEN'))
tokenizer = LlamaTokenizer.from_pretrained('meta-llama/Llama-2-7b-hf', token=os.environ.get('HF_TOKEN'))
model.save_pretrained('$MODEL_DIR')
tokenizer.save_pretrained('$MODEL_DIR')
print('Done!')
"

echo ""
echo "Model saved to $MODEL_DIR"
echo "To load: model = LlamaForCausalLM.from_pretrained('$MODEL_DIR')"
