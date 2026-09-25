"""v2 checkpoint sampler — honest side-by-side generation evidence.

Loads a v2 ``.npz`` checkpoint (via :func:`levi.brain.train.model_v2.load_v2_checkpoint`)
and the byte-BPE tokenizer, then generates greedy / temperature samples from
fixed prompts. Optionally also loads a v1 ``.pt`` checkpoint (char-level
``train.TinyGPT``) for side-by-side comparison across runs.

Requires torch (CPU). Training/sandbox-only dependency: the core runtime
never imports this module. Never fabricates weights — missing files are
errors, plainly stated.

Usage (repo root)::

    PYTHONPATH=core /path/to/venv/python -m levi.brain.train.v2.sample \\
        --ckpt runs/tiny-gpt-v2-20260916/checkpoints/ckpt-005400.npz \\
        --v1-ckpt core/levi/brain/weights/tiny-gpt.pt \\
        --out runs/tiny-gpt-v2-20260916/samples.md

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_PROMPTS = [
    "Operating systems manage",
    "Machine learning is",
    "Register: LEVI",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ckpt", required=True, help="v2 .npz checkpoint path")
    ap.add_argument(
        "--v1-ckpt",
        default="",
        help="optional v1 .pt checkpoint (char-level TinyGPT) for comparison",
    )
    ap.add_argument("--out", required=True, help="output markdown path")
    ap.add_argument(
        "--prompts",
        nargs="*",
        default=DEFAULT_PROMPTS,
        help="prompts to sample from (default: fixed identity/knowledge prompts)",
    )
    ap.add_argument("--max-new", type=int, default=160)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=7)
    return ap.parse_args(argv)


def sample_v2(ckpt_path: str | Path, prompts: list[str], max_new: int,
              temperature: float, seed: int) -> list[tuple[str, str, str]]:
    """Return (model_label, prompt, generation) rows for the v2 checkpoint."""
    import torch

    here = Path(__file__).resolve()
    core_dir = str(here.parents[4])  # sample.py -> v2 -> train -> brain -> levi -> core
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from levi.brain.train import model_v2

    tok = model_v2.build_tokenizer()
    model = model_v2.build_model()
    ckpt = model_v2.load_v2_checkpoint(ckpt_path, model)
    label = f"v2 {Path(ckpt_path).name} (step {ckpt.get('step', '?')})"
    torch.manual_seed(seed)
    rows = []
    with torch.no_grad():
        for p in prompts:
            ids = tok.encode(p)
            idx = torch.tensor([ids], dtype=torch.long)
            out = model.generate(idx, max_new=max_new, temperature=temperature)
            rows.append((label, p, tok.decode(out[0].tolist())))
    return rows


def sample_v1(ckpt_path: str | Path, prompts: list[str], max_new: int, seed: int):
    """Return (model_label, prompt, generation) rows for the v1 char checkpoint."""
    import torch
    import torch.nn.functional as F

    here = Path(__file__).resolve()
    train_dir = here.parent.parent  # core/levi/brain/train
    if str(train_dir) not in sys.path:
        sys.path.insert(0, str(train_dir))
    from train import TinyGPT

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
    label = (
        f"v1 tiny-gpt.pt (run 1, {ckpt.get('config', {}).get('steps', '?')} steps, "
        f"char vocab {len(chars)})"
    )
    torch.manual_seed(seed)
    rows = []
    with torch.no_grad():
        for p in prompts:
            idx = torch.tensor([[stoi.get(c, 0) for c in p]], dtype=torch.long)
            for _ in range(max_new):
                logits = model(idx[:, -model.block_size :])
                probs = F.softmax(logits[:, -1, :] / 0.8, dim=-1)
                idx = torch.cat([idx, torch.multinomial(probs, 1)], dim=1)
            rows.append((label, p, "".join(chars[i] for i in idx[0].tolist())))
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ckpt_path = Path(args.ckpt)
    if not ckpt_path.is_file():
        print(f"sample: no v2 checkpoint at {ckpt_path} — nothing to load.")
        return 2
    rows = sample_v2(ckpt_path, args.prompts, args.max_new, args.temperature,
                     args.seed)
    if args.v1_ckpt:
        v1_path = Path(args.v1_ckpt)
        if not v1_path.is_file():
            print(f"sample: v1 checkpoint {v1_path} missing — skipping v1 side.")
        else:
            rows.extend(sample_v1(v1_path, args.prompts, args.max_new, args.seed))

    lines = ["# native-brain sampling evidence", ""]
    lines.append(
        "_Greedy/temperature generations from fixed prompts. Both models are "
        "tiny proof-of-learning nets; gibberish with topic texture is the "
        "expected baseline — the comparison is about texture, not fluency._"
    )
    lines.append("")
    current_label = None
    for label, prompt, gen in rows:
        if label != current_label:
            lines += [f"## {label}", ""]
            current_label = label
        lines += [f"### prompt: {prompt!r}", "", "```", gen, "```", ""]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"sample: wrote {args.out} ({len(rows)} generations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
