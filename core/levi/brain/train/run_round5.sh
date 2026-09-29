#!/usr/bin/env bash
# Round 5 launcher: trains on the enlarged corpus (102,546 records), then runs
# the head-to-head benchmark at completion and writes EVAL_HEADTOHEAD.md.
#
# Run:  cd core/levi/brain/train && bash run_round5.sh
# Logs: weights/staging_bpe/round-05.log
# Glyph: 📊
set -euo pipefail

TRAIN_DIR="$(cd "$(dirname "$0")" && pwd)"
STAGING="$TRAIN_DIR/../weights/staging_bpe"
LOG="$STAGING/round-05.log"
HEADTOHEAD_VENV="$HOME/workspace/.headtohead-venv"

mkdir -p "$STAGING"
{
  echo "=== round 5 start: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  python3 "$TRAIN_DIR/continue_bpe.py" \
    --resume --steps 2000 --n-embd 96 --block-size 48
  echo "=== round 5 training done: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "=== head-to-head benchmark ==="
  if [ -x "$HEADTOHEAD_VENV/bin/python" ]; then
    "$HEADTOHEAD_VENV/bin/python" "$TRAIN_DIR/eval_headtohead.py" \
      --staging "$STAGING"
  else
    python3 "$TRAIN_DIR/eval_headtohead.py" --staging "$STAGING" \
      --skip-baselines
    echo "NOTE: headtohead venv missing; baselines skipped (LEVI leg only)."
  fi
  echo "=== done: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
} 2>&1 | tee -a "$LOG"
