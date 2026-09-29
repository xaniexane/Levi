"""Honest eval of the BPE brain checkpoint: held-out loss + generation samples.

No cherry-picking: fixed prompts, fixed seeds, full output shown.
"""
import json
import math
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tok import ByteBPETokenizer
from train import TinyGPT

STAGING = Path("/home/hatch/workspace/levi/core/levi/brain/weights/staging_bpe")
TRAIN_DIR = Path("/home/hatch/workspace/levi/core/levi/brain/train")
TEMPERATURE = 0.8

PROMPTS = [    "What does local-first mean for a tool like you?",
    "The user asked: write a shopping list.",
    "Chauncey Logan is building",
]


def load_latest():
    ckpts = sorted(STAGING.glob("tiny-gpt-bpe-ckpt-*.pt"))
    assert ckpts, "no checkpoints"
    latest = ckpts[-1]
    ckpt = torch.load(latest, map_location="cpu", weights_only=False)
    return latest, ckpt


def main():
    t0 = time.time()
    latest, ckpt = load_latest()
    cfg = ckpt["config"]
    print(f"checkpoint: {latest.name}  step={ckpt['step']} round={ckpt['round']}")

    tok = ByteBPETokenizer.load(str(TRAIN_DIR / "tokenizer.json"))

    model = TinyGPT(
        vocab_size=cfg["vocab_size"], n_layer=cfg["n_layer"],
        n_head=cfg["n_head"], n_embd=cfg["n_embd"],
        block_size=cfg["block_size"],
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    # --- held-out loss (fixed heldout corpus, no training) ---
    heldout_ids = []
    with open(TRAIN_DIR / "corpus_dialogue_heldout.jsonl") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get("text") or rec.get("prompt", "") + " " + rec.get("response", "")
            heldout_ids.extend(tok.encode(text))
    print(f"heldout tokens: {len(heldout_ids)}")
    bs = cfg["block_size"]
    losses = []
    with torch.no_grad():
        for i in range(0, len(heldout_ids) - bs - 1, bs):
            x = torch.tensor([heldout_ids[i:i + bs]])
            y = torch.tensor([heldout_ids[i + 1:i + bs + 1]])
            logits = model(x)
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)), y.view(-1))
            losses.append(loss.item())
    hl = sum(losses) / len(losses)
    print(f"HELD-OUT LOSS: {hl:.4f}  (perplexity {math.exp(hl):.2f})")
    print(f"random baseline ln(8192) = {math.log(8192):.4f}")

    # --- generation samples (fixed seeds, temperature 0.8) ---
    print("\n--- samples ---")
    for pi, prompt in enumerate(PROMPTS):
        torch.manual_seed(20260926 + pi)
        ids = tok.encode(prompt)[-bs:]
        x = torch.tensor([ids])
        with torch.no_grad():
            for _ in range(60):
                logits = model(x[:, -bs:])
                probs = F.softmax(logits[0, -1] / TEMPERATURE, dim=-1)
                nxt = torch.multinomial(probs, 1).item()
                ids.append(nxt)
                x = torch.tensor([ids])
        print(f"\nPROMPT: {prompt}")
        print("OUTPUT:", tok.decode(ids[len(tok.encode(prompt)):])[:400])
    print(f"\neval took {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
