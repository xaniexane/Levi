#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/tools"
# Prefer knowledge/corpus.txt (back up the existing corpus first — never clobber it)
if [[ -f "$ROOT/knowledge/corpus.txt" ]]; then
  if [[ -f ./corpus.txt ]]; then
    cp -f ./corpus.txt "./corpus.txt.bak.$(date +%Y%m%d%H%M%S)"
  fi
  cp -f "$ROOT/knowledge/corpus.txt" ./corpus.txt
fi
python3 train_native.py
echo "Model written beside train_native.py if training succeeded."
