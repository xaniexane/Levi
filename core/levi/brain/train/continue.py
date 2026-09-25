"""Continued training: resume the native brain from tiny-gpt.pt on a mix of
the original corpus and the new dialogue corpus.

- NEVER overwrites ``weights/tiny-gpt.pt`` — the candidate goes to a
  staging path for the eval gate to judge.
- 50/50 mix by batch (configurable): half of every batch comes from the
  original corpus (no catastrophic forgetting), half from the dialogue
  corpus (conversational quality + both registers).
- Lower LR than the original run (1e-4 vs 3e-4): continued training, not
  a restart.
- Honest cost estimate logged BEFORE the full run (times 20 warmup steps,
  extrapolates).
- Stops on NaN or loss explosion; reports instead of promoting garbage.

Requires torch (CPU or CUDA — --device auto steps up to a GPU when present).
The core runtime stays stdlib-only — torch lives only in train/.

Usage:
    python3 continue.py [--steps 600] [--lr 1e-4] [--dialog-ratio 0.5]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train import TinyGPT, cpu_state_dict, get_batch, load_corpus, resolve_device  # noqa: E402

WEIGHTS = HERE.parent / "weights"
CKPT = WEIGHTS / "tiny-gpt.pt"
STAGING = WEIGHTS / "staging"


def load_dialogue_text(path: Path) -> str:
    texts = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            t = rec.get("text", "")
            if t:
                texts.append(t)
    return "\n\n".join(texts)


def get_batch_mixed(orig_data, dlg_data, batch_size, block_size, dlg_ratio=0.5):
    n_dlg = int(batch_size * dlg_ratio)
    n_orig = batch_size - n_dlg
    batches = []
    if n_orig > 0:
        batches.append(get_batch(orig_data, n_orig, block_size))
    if n_dlg > 0:
        batches.append(get_batch(dlg_data, n_dlg, block_size))
    x = torch.cat([b[0] for b in batches], dim=0)
    y = torch.cat([b[1] for b in batches], dim=0)
    perm = torch.randperm(x.size(0))
    return x[perm], y[perm]


def _latest_ckpt(staging: Path):
    """Newest persistent training checkpoint, or None."""
    ckpts = sorted(staging.glob("tiny-gpt-continued-ckpt-*.pt"))
    return ckpts[-1] if ckpts else None


def _save_ckpt(staging: Path, step: int, model, opt, chars, config, args, loss_first):
    """Persistent crash-recovery checkpoint. Never in /tmp."""
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"tiny-gpt-continued-ckpt-{step:06d}.pt"
    torch.save(
        {
            "model_state": cpu_state_dict(model),
            "optim_state": opt.state_dict(),
            "rng_state": torch.get_rng_state(),
            "cuda_rng_state": (
                torch.cuda.get_rng_state_all()
                if torch.cuda.is_available()
                else None
            ),
            "step": step,
            "loss_first": loss_first,
            "chars": chars,
            "config": {
                **config,
                "continued_steps": args.steps,
                "continued_lr": args.lr,
                "continued_seed": args.seed,
                "dialog_ratio": args.dialog_ratio,
            },
        },
        path,
    )
    # keep only the two newest checkpoints (each ~13MB)
    for old in sorted(staging.glob("tiny-gpt-continued-ckpt-*.pt"))[:-2]:
        old.unlink()
    print(f"  checkpoint saved: {path}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--dialog-ratio", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--dialogue-corpus", default="corpus_dialogue.jsonl",
                    help="dialogue corpus filename under train/ (a carved train split "
                         "keeps the held-out set genuinely unseen)")
    ap.add_argument("--out", default=str(STAGING / "tiny-gpt-continued.pt"))
    ap.add_argument(
        "--resume",
        action="store_true",
        help="resume from the latest persistent checkpoint in the staging dir",
    )
    ap.add_argument("--ckpt-every", type=int, default=50,
                    help="save a persistent checkpoint every N steps")
    ap.add_argument("--device", default="auto",
                    help="auto (cuda if present, else cpu), cpu, or cuda")
    args = ap.parse_args(argv)

    torch.manual_seed(args.seed)
    dev = resolve_device(args.device)
    if dev.type == "cuda":
        torch.cuda.manual_seed_all(args.seed)
    print(f"device: {dev}", flush=True)

    print("loading checkpoint (never modified):", CKPT, flush=True)
    ckpt = torch.load(CKPT, map_location=dev, weights_only=False)
    config = ckpt["config"]
    chars = ckpt["chars"]
    stoi = {c: i for i, c in enumerate(chars)}
    vocab_size = len(chars)

    print("loading corpora ...", flush=True)
    orig_text = load_corpus(HERE / "corpus.jsonl")
    dlg_path = Path(args.dialogue_corpus)
    if not dlg_path.is_absolute():
        dlg_path = HERE / dlg_path
    dlg_text = load_dialogue_text(dlg_path)
    print(f"  original: {len(orig_text):,} chars", flush=True)
    print(f"  dialogue: {len(dlg_text):,} chars ({dlg_path.name})", flush=True)

    # sanity: dialogue must fit the checkpoint vocab
    missing = sorted(set(dlg_text) - set(stoi))
    if missing:
        print(
            f"ABORT: dialogue corpus has {len(missing)} chars outside the checkpoint vocab: "
            f"{missing[:10]}"
        )
        return 2

    orig_data = torch.tensor([stoi[c] for c in orig_text], dtype=torch.long)
    dlg_data = torch.tensor([stoi[c] for c in dlg_text], dtype=torch.long)

    model = TinyGPT(
        vocab_size,
        n_layer=config["n_layer"],
        n_head=config["n_head"],
        n_embd=config["n_embd"],
        block_size=config["block_size"],
    )
    model.load_state_dict(ckpt["model_state"])
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    block_size = model.block_size
    model.train()

    LOG_JSONL = STAGING / "continue_loss.jsonl"
    STAGING.mkdir(parents=True, exist_ok=True)

    # ---- crash recovery: resume from the latest persistent checkpoint
    start_step = 1
    loss_first = None
    if args.resume:
        latest = _latest_ckpt(STAGING)
        if latest is not None:
            print("resuming from persistent checkpoint:", latest, flush=True)
            rckpt = torch.load(latest, map_location=dev, weights_only=False)
            model.load_state_dict(rckpt["model_state"])
            opt.load_state_dict(rckpt["optim_state"])
            if rckpt.get("rng_state") is not None:
                torch.set_rng_state(rckpt["rng_state"])
            if rckpt.get("cuda_rng_state") is not None and torch.cuda.is_available():
                torch.cuda.set_rng_state_all(rckpt["cuda_rng_state"])
            start_step = rckpt["step"] + 1
            loss_first = rckpt.get("loss_first")
        else:
            print("no persistent checkpoint found — starting fresh", flush=True)

    # ---- honest cost estimate: time 20 warmup steps, extrapolate
    # (skipped on resume: weights are already warm)
    if start_step == 1:
        WARMUP = 20
        t0 = time.time()
        for _ in range(WARMUP):
            x, y = get_batch_mixed(
                orig_data, dlg_data, args.batch_size, block_size, args.dialog_ratio
            )
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            loss = F.cross_entropy(model(x).view(-1, vocab_size), y.view(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
        warm_s = time.time() - t0
        est_total = warm_s / WARMUP * args.steps
        print(
            f"cost estimate: {warm_s:.1f}s for {WARMUP} steps -> "
            f"~{est_total:.0f}s (~{est_total / 60:.1f} min) for {args.steps} steps",
            flush=True,
        )
        # reload clean weights after warmup so the estimate doesn't pollute training
        model.load_state_dict(ckpt["model_state"])
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    else:
        est_total = 0.0
        print(f"warmup skipped (resumed at step {start_step})", flush=True)

    losses = []
    t0 = time.time()
    for step in range(start_step, args.steps + 1):
        x, y = get_batch_mixed(
            orig_data, dlg_data, args.batch_size, block_size, args.dialog_ratio
        )
        x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, vocab_size), y.view(-1))
        lv = loss.item()
        if lv != lv:  # NaN
            print(
                f"  step {step}: loss is NaN — STOPPING, not promoting garbage",
                flush=True,
            )
            return 3
        if loss_first is None:
            loss_first = lv
        if step > 50 and lv > 3 * loss_first:
            print(
                f"  step {step}: loss exploded ({lv:.4f} > 3x first {loss_first:.4f}) — STOPPING",
                flush=True,
            )
            return 3
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(lv)
        with open(LOG_JSONL, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"step": step, "loss": round(lv, 6),
                     "elapsed_s": round(time.time() - t0, 1)}
                )
                + "\n"
            )
        if step % args.ckpt_every == 0:
            _save_ckpt(STAGING, step, model, opt, chars, config, args, loss_first)
        if step % max(1, args.steps // 10) == 0 or step == 1:
            print(f"  step {step}/{args.steps}  loss {lv:.4f}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": cpu_state_dict(model),
            "chars": chars,
            "config": {
                **config,
                "continued_steps": args.steps,
                "continued_lr": args.lr,
                "continued_seed": args.seed,
                "dialog_ratio": args.dialog_ratio,
                "orig_corpus_chars": len(orig_text),
                "dialog_corpus_chars": len(dlg_text),
                "dialog_corpus_file": dlg_path.name,
                "parent": str(CKPT),
            },
        },
        out,
    )
    first_loss = losses[0] if losses else loss_first
    last_loss = losses[-1] if losses else loss_first
    min_loss = min(losses) if losses else loss_first
    log = {
        "loss_first": first_loss,
        "loss_last": last_loss,
        "loss_min": min_loss,
        "steps": args.steps,
        "resumed_from_step": start_step,
        "seconds": round(time.time() - t0, 1),
        "est_seconds": round(est_total, 1),
        "params": sum(p.numel() for p in model.parameters()),
        "vocab_size": vocab_size,
        "out": str(out),
    }
    (out.parent / "continue_log.json").write_text(json.dumps(log, indent=1))
    if first_loss is None:
        print("continued: no training steps run", flush=True)
    else:
        print(
            f"continued: loss {first_loss:.4f} -> {last_loss:.4f} (min {min_loss:.4f}) "
            f"in {log['seconds']}s",
            flush=True,
        )
    print("candidate (NOT promoted):", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
