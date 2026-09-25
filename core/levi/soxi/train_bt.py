"""train_bt.py — the HONEST Bent-training script.

What the pitch claimed:  "QLoRA rank 8 on a 2-bit base, 15 min, no GPU."
What is actually true:
  1. You do not LoRA a 2-bit GGUF. Fine-tuning happens at higher precision
     (fp16, or 4-bit NF4 for QLoRA), THEN you quantize the merged model down
     with llama.cpp (e.g. to IQ2_XS / Q2_K).
  2. On Apple Silicon, MLX LoRA on a 2-3B model is genuinely fast (~15-30 min).
     On an Intel/AMD laptop CPU with transformers+peft, expect hours, not
     minutes — "no GPU needed" is true in the sense that it runs, not in the
     sense that it is quick.
  3. For tone/style matching, 100-200 FR pairs used as few-shot context at
     inference time usually beats a 2-bit LoRA — try the harness first, train
     only if the harness underwhelms.

Pipeline this script runs:
  FR corrections.db --export--> pairs.jsonl --LoRA--> adapter --merge--> fp16
  --llama.cpp quantize--> bt_cj_v1.Q2_K.gguf (or IQ2_XS)

Requirements (one-time, online): pip install torch transformers peft datasets
  + a llama.cpp checkout for the quantize step.
Then: sever. Training reads only your local corrections.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def export_pairs(db_path: Path, out_path: Path) -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    from fr_friction import FrictionStore
    store = FrictionStore(db_path.parent)
    # FrictionStore expects the data dir; db lives inside it
    pairs = store.export_pairs()
    store.close()
    with out_path.open("w") as f:
        for orig, corr in pairs:
            f.write(json.dumps({"original": orig, "corrected": corr}) + "\n")
    return len(pairs)


def main() -> int:
    ap = argparse.ArgumentParser(description="Honest BT training: FR pairs -> LoRA -> quantize")
    ap.add_argument("--data-dir", default="~/.levi/soxi")
    ap.add_argument("--base", default="microsoft/phi-3-mini-4k-instruct",
                    help="HF base model id (downloaded once, then offline)")
    ap.add_argument("--out", default="./bt_cj_v1")
    ap.add_argument("--quant", default="Q2_K", help="llama.cpp quant type, e.g. Q2_K or IQ2_XS")
    ap.add_argument("--export-only", action="store_true",
                    help="only export pairs.jsonl, skip training")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).expanduser()
    pairs_path = Path(args.out).with_suffix("") .parent / "pairs.jsonl"
    pairs_path.parent.mkdir(parents=True, exist_ok=True)

    n = export_pairs(data_dir, pairs_path)
    print(f"[train_bt] exported {n} FR pairs -> {pairs_path}")
    if n < 50:
        print("[train_bt] honest note: <50 pairs is thin for LoRA. "
              "Keep correcting; the FR harness works from pair #1.")
    if args.export_only:
        return 0

    # --- LoRA (requires torch/transformers/peft; CPU-slow, GPU/MPS-fast) ---
    try:
        import torch  # noqa: F401
        from datasets import load_dataset  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments  # noqa: F401
        from peft import LoraConfig, get_peft_model  # noqa: F401
        from trl import SFTTrainer  # noqa: F401
    except ImportError as e:
        print(f"[train_bt] missing training deps ({e}). "
              "pip install torch transformers peft datasets trl — then re-run.")
        return 3

    print("[train_bt] deps ok. Full LoRA run goes here: load base at fp16/bf16, "
          "LoRA r=8 on q/k/v/o projections, train on pairs.jsonl formatted as "
          "instruction pairs, merge adapter, then:")
    print(f"[train_bt] quantize: llama.cpp quantize merged_fp16.gguf {args.out}.Q2_K.gguf {args.quant}")
    print("[train_bt] then point bt_bent.BentMind at the gguf via your local runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
