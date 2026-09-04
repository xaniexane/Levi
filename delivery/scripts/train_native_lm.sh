#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/tools"
# Prefer knowledge/corpus.txt
if [[ -f "$ROOT/knowledge/corpus.txt" ]]; then
  cp -f "$ROOT/knowledge/corpus.txt" ./corpus.txt
fi
python3 train_native.py
echo "Model written beside train_native.py if training succeeded."
