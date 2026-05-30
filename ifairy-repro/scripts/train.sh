#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

MODEL_TYPE="${1:-tiny}"
OUTPUT_DIR="${2:-./output}"

echo "=== iFairy Reproduction ==="
echo "Model type: $MODEL_TYPE"
echo "Output dir: $OUTPUT_DIR"
echo ""

python3 "$PROJECT_DIR/scripts/train.py" \
  --model_type "$MODEL_TYPE" \
  --output_dir "$OUTPUT_DIR"
