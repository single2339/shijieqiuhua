#!/usr/bin/env bash
set -euo pipefail

echo "=== iFairy Reproduction - Server Setup ==="

# 1. System packages
echo "[1/5] Installing system packages..."
sudo apt-get update -qq && sudo apt-get install -y -qq \
  build-essential \
  python3-dev \
  python3-pip \
  python3-venv \
  git \
  wget \
  curl \
  nvtop 2>/dev/null || true

# 2. Check CUDA
echo "[2/5] Checking CUDA..."
if command -v nvidia-smi &>/dev/null; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
  echo "WARNING: nvidia-smi not found. CUDA may not be installed."
fi

# 3. Create virtualenv
echo "[3/5] Creating Python virtual environment..."
python3 -m venv ifairy-env
source ifairy-env/bin/activate

# 4. Install PyTorch (CUDA 12.1)
echo "[4/5] Installing PyTorch + CUDA..."
pip install --quiet torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 5. Install project dependencies
echo "[5/5] Installing project dependencies..."
pip install --quiet \
  transformers>=4.36.0 \
  datasets>=2.14.0 \
  accelerate>=0.25.0 \
  sentencepiece \
  wandb \
  "numpy<2.0"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  source ifairy-env/bin/activate"
echo "  cd ifairy-repro"
echo "  python scripts/train.py --model_type tiny"
echo ""
echo "For Llama-2-7B, you also need:"
echo "  huggingface-cli login  (with your HuggingFace token)"
echo "  python scripts/train.py --model_type llama2_7b"
