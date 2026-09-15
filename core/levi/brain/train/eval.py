"""Evaluate LEVI's tiny brain: held-out loss + sample generations.

Loads ../weights/tiny-gpt.pt (written by train.py). If the weights are
missing it says so plainly and exits 2 — it never fabricates numbers.

Writes ../weights/samples.md with 3 generations from fixed prompts.

Usage: python3 eval.py [--data corpus.jsonl] [--out ../weights]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROMPTS = [
    "Operating systems manage",
    "Register: LEVI",
    "Machine learning is",
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "corpus.jsonl"))
    ap.add_argument("--out", default=str(HERE.parent / "weights"))
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    ckpt_path = out_dir / "tiny-gpt.pt"
    if not ckpt_path.is_file():
        print("eval: no weights at", ckpt_path, "— run train.py first.")
        return 2

    import torch
    import torch.nn.functional as F
    from train import TinyGPT, load_corpus, get_batch

    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    chars = ckpt["chars"]
    stoi = {c: i for i, c in enumerate(chars)}
    cfg = ckpt["config"]
    model = TinyGPT(
        len(chars),
        n_layer=cfg["n_layer"],
        n_head=cfg["n_head"],
        n_embd=cfg["n_embd"],
        block_size=cfg["block_size"],
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    # held-out loss: last 5% of the corpus, never trained on directly
    text = load_corpus(Path(args.data))
    data = torch.tensor([stoi.get(c, 0) for c in text], dtype=torch.long)
    cut = int(len(data) * 0.95)
    held = data[cut:]
    with torch.no_grad():
        x, y = get_batch(held, 16, model.block_size)
        loss = F.cross_entropy(model(x).view(-1, len(chars)), y.view(-1)).item()
    print(f"held-out loss: {loss:.4f}")

    def generate(prompt: str, n: int = 200) -> str:
        idx = torch.tensor([[stoi.get(c, 0) for c in prompt]], dtype=torch.long)
        with torch.no_grad():
            for _ in range(n):
                logits = model(idx[:, -model.block_size :])
                probs = F.softmax(logits[:, -1, :], dim=-1)
                nxt = torch.multinomial(probs, 1)
                idx = torch.cat([idx, nxt], dim=1)
        return "".join(chars[i] for i in idx[0].tolist())

    torch.manual_seed(7)
    lines = [
        "# tiny-gpt samples",
        "",
        f"_held-out loss: {loss:.4f} | params: {cfg['params']:,} | "
        f"steps: {cfg['steps']} | corpus: {cfg['corpus_chars']:,} chars_",
        "",
    ]
    for p in PROMPTS:
        gen = generate(p)
        lines += [f"## prompt: {p!r}", "", "```", gen, "```", ""]
        print(f"--- {p!r}\n{gen[:160]}...\n")
    (out_dir / "samples.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out_dir / "samples.md")
    (out_dir / "eval.json").write_text(
        json.dumps(
            {"held_out_loss": loss, "params": cfg["params"], "steps": cfg["steps"]},
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
