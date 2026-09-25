"""BPE-mode training: the subword sibling of continue.py.

Trains a TinyGPT from scratch on BPE-tokenized text (levi-bpe-v1, 8k
vocab from tok.py) instead of the 162-char vocabulary. There is no BPE
parent checkpoint yet, so round 1 starts from random weights — the point
is to prove the machinery (tokenize -> batch -> loss down -> samples
decode), not to produce a fluent brain.

ROUNDS ARE THE DEFAULT. A killed session is not a failed run, it is the
end of a round: round N+1 resumes from the latest checkpoint in a fresh
session and continues, free forever. Every round is one invocation:

    round 1:  python3 continue_bpe.py --steps 80
    round 2:  python3 continue_bpe.py --resume --steps 80
    round 3:  python3 continue_bpe.py --resume --steps 80 ...

Bulletproof resume (zero manual repair):
- checkpoints are written atomically (temp file + os.replace); a kill
  mid-write can never leave a half-written checkpoint in place
- --resume loads the newest checkpoint, and falls back to the older one
  automatically if the newest fails to load
- --resume with NO checkpoint found ABORTS loudly (staging path wrong,
  e.g. Drive not mounted) instead of silently starting a fresh model
- resume validates architecture + tokenizer identity against the
  checkpoint; any mismatch aborts, never trains on silently wrong config
- optimizer + RNG state restore, so training continues bit-continuously

On Colab/Kaggle free tiers, point --staging at persistent storage
(a mounted Drive folder), never the ephemeral VM disk.

Conventions mirror continue.py on purpose:
- never touches weights/tiny-gpt.pt or the char staging dir; everything
  lands in weights/staging_bpe/ (or --staging)
- persistent crash-recovery checkpoints every N steps + --resume
- JSONL loss log (with round numbers), rounds manifest, NaN guards
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tok import ByteBPETokenizer  # noqa: E402
from train import TinyGPT, cpu_state_dict, get_batch, resolve_device  # noqa: E402

WEIGHTS = HERE.parent / "weights"
DEFAULT_STAGING = WEIGHTS / "staging_bpe"
TOKENIZER_PATH = HERE / "tokenizer.json"

# random-init baseline: ln(8192) ~= 9.01 — the prototype must beat this.


def load_bpe_texts(path: Path) -> list[str]:
    texts = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line).get("text", "")
            if t:
                texts.append(t)
    return texts


def encode_corpus(tok: ByteBPETokenizer, texts: list[str]) -> torch.Tensor:
    """Encode each record, joined by the pipeline-inserted <eod> marker."""
    ids: list[int] = []
    eod = tok.eod_id
    for t in texts:
        ids.extend(tok.encode(t))
        ids.append(eod)
    return torch.tensor(ids, dtype=torch.long)


def _ckpts(staging: Path):
    """All BPE checkpoints, oldest first."""
    return sorted(staging.glob("tiny-gpt-bpe-ckpt-*.pt"))


def _save_ckpt(
    staging, step, model, opt, config, args, loss_first, tok_format, round_no
):
    """Persistent crash-recovery checkpoint. Never in /tmp.

    Atomic: writes to a temp file then os.replace, so a kill mid-write
    can never leave a corrupt checkpoint behind.
    """
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"tiny-gpt-bpe-ckpt-{step:06d}.pt"
    tmp = staging / f"tiny-gpt-bpe-ckpt-{step:06d}.pt.tmp"
    torch.save(
        {
            "model_state": cpu_state_dict(model),
            "optim_state": opt.state_dict(),
            "rng_state": torch.get_rng_state(),
            "cuda_rng_state": (
                torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
            ),
            "step": step,
            "round": round_no,
            "loss_first": loss_first,
            "tokenizer": tok_format,
            "vocab_size": config["vocab_size"],
            "arch": {
                k: config[k] for k in ("n_layer", "n_head", "n_embd", "block_size")
            },
            "config": {
                **config,
                "bpe_steps": args.steps,
                "bpe_lr": args.lr,
                "bpe_seed": args.seed,
            },
        },
        tmp,
    )
    os.replace(tmp, path)  # atomic on POSIX
    # keep only the two newest checkpoints (each ~10MB at proto size)
    for old in _ckpts(staging)[:-2]:
        old.unlink()
    print(f"  checkpoint saved: {path}", flush=True)


def _load_resume_ckpt(staging: Path, dev):
    """Newest loadable checkpoint, or (None, error string).

    Falls back to the older checkpoint automatically when the newest
    fails to load — zero manual repair after a kill mid-write.
    """
    errors = []
    for path in reversed(_ckpts(staging)):
        try:
            return torch.load(path, map_location=dev, weights_only=False), None
        except Exception as exc:  # corrupt/partial file: try the older one
            errors.append(f"{path.name}: {exc}")
    return None, "; ".join(errors)


def _check_arch_match(rckpt, config) -> str | None:
    """Error string when the checkpoint disagrees with this run, else None."""
    if rckpt.get("tokenizer") != "levi-bpe-v1":
        return f"checkpoint tokenizer {rckpt.get('tokenizer')!r} != levi-bpe-v1"
    if rckpt.get("vocab_size") != config["vocab_size"]:
        return f"checkpoint vocab {rckpt.get('vocab_size')} != {config['vocab_size']}"
    arch = rckpt.get("arch") or {}
    for k in ("n_layer", "n_head", "n_embd", "block_size"):
        if arch.get(k) != config[k]:
            return f"checkpoint arch {k}={arch.get(k)} != {config[k]}"
    return None


def _last_round(staging: Path) -> int:
    """Highest round number in the rounds manifest (0 when none)."""
    manifest = staging / "rounds.jsonl"
    last = 0
    if manifest.is_file():
        with open(manifest, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        last = max(last, int(json.loads(line)["round"]))
                    except (KeyError, ValueError):
                        pass
    return last


@torch.no_grad()
def sample(
    model,
    tok: ByteBPETokenizer,
    prompt: str,
    dev,
    max_new=120,
    temperature=0.8,
    top_k=50,
    seed=7,
) -> str:
    g = torch.Generator(device=dev).manual_seed(seed)
    ids = tok.encode(prompt)
    x = torch.tensor([ids], dtype=torch.long, device=dev)
    model.eval()
    for _ in range(max_new):
        x_in = x[:, -model.block_size :]
        logits = model(x_in)[0, -1, :] / temperature
        if top_k:
            v, _ = torch.topk(logits, top_k)
            logits[logits < v[-1]] = float("-inf")
        probs = F.softmax(logits, dim=-1)
        nxt = torch.multinomial(probs, 1, generator=g)
        x = torch.cat([x, nxt.view(1, 1)], dim=1)
        if int(nxt) == tok.eod_id:
            break
    model.train()
    return tok.decode(x[0].tolist())


@torch.no_grad()
def heldout_loss(model, data, batch_size, block_size, dev, n_batches=20) -> float:
    model.eval()
    tot = 0.0
    for _ in range(n_batches):
        x, y = get_batch(data, batch_size, block_size)
        x, y = x.to(dev), y.to(dev)
        tot += F.cross_entropy(
            model(x).view(-1, model.head.out_features), y.view(-1)
        ).item()
    model.train()
    return tot / n_batches


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="BPE-mode prototype training. One invocation = one round; "
        "--resume starts the next round from the latest checkpoint."
    )
    ap.add_argument(
        "--steps", type=int, default=80, help="training steps to run THIS round"
    )
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--n-layer", type=int, default=2)
    ap.add_argument("--n-head", type=int, default=2)
    ap.add_argument("--n-embd", type=int, default=128)
    ap.add_argument("--block-size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--dialogue-corpus", default="corpus_dialogue_train.jsonl")
    ap.add_argument("--heldout-corpus", default="corpus_dialogue_heldout.jsonl")
    ap.add_argument("--tokenizer", default=str(TOKENIZER_PATH))
    ap.add_argument(
        "--staging",
        default=str(DEFAULT_STAGING),
        help="checkpoint/log dir - on Colab/Kaggle point this at "
        "persistent storage (mounted Drive), never the "
        "ephemeral VM disk",
    )
    ap.add_argument(
        "--out",
        default="",
        help="round candidate path (default: staging/tiny-gpt-bpe-round-NN.pt)",
    )
    ap.add_argument(
        "--round",
        type=int,
        default=0,
        help="explicit round number (default: auto = last + 1)",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="start this round from the latest checkpoint; "
        "ABORTS (no silent fresh start) when none exists",
    )
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="deliberately start from RANDOM weights even though checkpoints "
        "exist (without --resume/--fresh the run aborts rather than risk "
        "clobbering a lineage)",
    )
    ap.add_argument("--ckpt-every", type=int, default=40)
    ap.add_argument("--device", default="auto")
    ap.add_argument(
        "--threads",
        type=int,
        default=2,
        help="torch CPU threads (stay polite on a shared box)",
    )
    args = ap.parse_args(argv)

    staging = Path(args.staging)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    dev = resolve_device(args.device)
    print(f"device: {dev}  threads: {args.threads}", flush=True)
    print(f"staging: {staging}", flush=True)

    print("loading BPE tokenizer:", args.tokenizer, flush=True)
    tok = ByteBPETokenizer.load(args.tokenizer)
    print(f"  format=levi-bpe-v1 vocab_size={tok.vocab_size}", flush=True)

    print("loading + encoding corpora ...", flush=True)
    t0 = time.time()
    dlg_path = HERE / args.dialogue_corpus
    ho_path = HERE / args.heldout_corpus
    train_texts = load_bpe_texts(dlg_path)
    train_data = encode_corpus(tok, train_texts)
    ho_data = None
    if ho_path.is_file():
        ho_data = encode_corpus(tok, load_bpe_texts(ho_path))
    n_chars = sum(len(t) for t in train_texts)
    print(
        f"  train: {len(train_texts)} records, {n_chars:,} chars -> "
        f"{len(train_data):,} BPE tokens "
        f"({len(train_data) / max(0.001, time.time() - t0):,.0f} tok/s)",
        flush=True,
    )
    if ho_data is not None:
        print(f"  heldout: {len(ho_data):,} BPE tokens", flush=True)
    if len(train_data) < args.block_size + 2:
        print("ABORT: corpus too small for block_size", flush=True)
        return 2

    config = {
        "vocab_size": tok.vocab_size,
        "n_layer": args.n_layer,
        "n_head": args.n_head,
        "n_embd": args.n_embd,
        "block_size": args.block_size,
        "tokenizer": "levi-bpe-v1",
    }
    model = TinyGPT(
        tok.vocab_size,
        n_layer=args.n_layer,
        n_head=args.n_head,
        n_embd=args.n_embd,
        block_size=args.block_size,
    )
    params = sum(p.numel() for p in model.parameters())
    print(f"  params: {params:,}", flush=True)
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    model.train()

    staging.mkdir(parents=True, exist_ok=True)
    LOG_JSONL = staging / "bpe_loss.jsonl"
    MANIFEST = staging / "rounds.jsonl"

    # ---- round bookkeeping: rounds are the default, resume is the norm.
    # A resumed invocation is always the NEXT round number, even when the
    # previous round was killed before writing its manifest entry: the
    # checkpoint's own round counts, so "round 2 resumes round 1" holds.
    last_round = _last_round(staging)
    rckpt = None
    ckpt_err = ""
    if args.resume:
        rckpt, ckpt_err = _load_resume_ckpt(staging, dev)
        if rckpt is None:
            # Fail closed: a missing staging dir on a free-tier VM almost
            # always means persistent storage is not mounted. Silently
            # starting a fresh random model would burn the whole session.
            print(
                "ABORT: --resume given but no loadable BPE checkpoint in "
                f"{staging}" + (f" ({ckpt_err})" if ckpt_err else "") + "\n"
                "  -> check that persistent storage is mounted and "
                "--staging points at it. Round 1 (fresh) runs WITHOUT "
                "--resume.",
                flush=True,
            )
            return 2
        arch_err = _check_arch_match(rckpt, config)
        if arch_err:
            print(f"ABORT: {arch_err}", flush=True)
            return 2
    if args.round:
        if args.round <= last_round:
            print(
                f"ABORT: --round {args.round} <= last recorded round "
                f"{last_round} (refusing to rewrite history)",
                flush=True,
            )
            return 2
        round_no = args.round
    else:
        base = last_round
        if rckpt is not None:
            base = max(base, rckpt.get("round", 0) or 0)
        round_no = base + 1

    start_step = 1
    loss_first = None
    if rckpt is not None:
        print(
            f"round {round_no}: resuming from step {rckpt['step']} "
            f"(checkpoint round {rckpt.get('round', '?')})",
            flush=True,
        )
        model.load_state_dict(rckpt["model_state"])
        opt.load_state_dict(rckpt["optim_state"])
        if rckpt.get("rng_state") is not None:
            torch.set_rng_state(rckpt["rng_state"])
        if rckpt.get("cuda_rng_state") is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(rckpt["cuda_rng_state"])
        start_step = rckpt["step"] + 1
        loss_first = rckpt.get("loss_first")
    else:
        if _ckpts(staging) and not args.fresh:
            # Fail closed: a forgotten --resume must never silently start a
            # fresh random lineage next to (and eventually over) good
            # checkpoints. --fresh is the deliberate override.
            print(
                f"ABORT: checkpoints exist in {staging} but neither --resume "
                "nor --fresh given. Pass --resume to continue the lineage, "
                "or --fresh to deliberately restart from random weights.",
                flush=True,
            )
            return 2
        if _ckpts(staging):
            print(
                f"WARNING: --fresh: starting round {round_no} from RANDOM "
                "weights over existing checkpoints.",
                flush=True,
            )
        print(f"round {round_no}: fresh start (random weights)", flush=True)

    end_step = start_step + args.steps - 1
    print(
        f"round {round_no}: steps {start_step}..{end_step} "
        f"({args.steps} steps this round)",
        flush=True,
    )

    losses = []
    t0 = time.time()
    for step in range(start_step, end_step + 1):
        x, y = get_batch(train_data, args.batch_size, args.block_size)
        x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
        loss = F.cross_entropy(model(x).view(-1, tok.vocab_size), y.view(-1))
        lv = loss.item()
        if lv != lv:
            print(f"  step {step}: NaN - STOPPING", flush=True)
            return 3
        if loss_first is None:
            loss_first = lv
        if step > start_step + 10 and lv > 3 * loss_first:
            print(f"  step {step}: loss exploded ({lv:.4f}) - STOPPING", flush=True)
            return 3
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(lv)
        with open(LOG_JSONL, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "round": round_no,
                        "step": step,
                        "loss": round(lv, 6),
                        "elapsed_s": round(time.time() - t0, 1),
                    }
                )
                + "\n"
            )
        if step % args.ckpt_every == 0:
            _save_ckpt(
                staging,
                step,
                model,
                opt,
                config,
                args,
                loss_first,
                "levi-bpe-v1",
                round_no,
            )
        if step % max(1, args.steps // 8) == 0 or step == start_step:
            print(f"  step {step}/{end_step}  loss {lv:.4f}", flush=True)

    # final checkpoint of the round, so the next round resumes exactly here
    _save_ckpt(
        staging, end_step, model, opt, config, args, loss_first, "levi-bpe-v1", round_no
    )

    out = (
        Path(args.out)
        if args.out
        else (staging / f"tiny-gpt-bpe-round-{round_no:02d}.pt")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": cpu_state_dict(model),
            "tokenizer": "levi-bpe-v1",
            "vocab_size": tok.vocab_size,
            "round": round_no,
            "config": {
                **config,
                "bpe_steps": args.steps,
                "bpe_lr": args.lr,
                "bpe_seed": args.seed,
            },
        },
        out,
    )

    ho = None
    if ho_data is not None and len(ho_data) > args.block_size + 2:
        ho = heldout_loss(model, ho_data, args.batch_size, args.block_size, dev)
        print(f"  held-out loss: {ho:.4f}", flush=True)

    print("--- sample ---", flush=True)
    print(sample(model, tok, "User: Hey LEVI, what are you?\nLEVI:", dev), flush=True)
    print("--------------", flush=True)

    first = losses[0] if losses else loss_first
    last = losses[-1] if losses else loss_first
    secs = time.time() - t0
    n_tok = len(losses) * args.batch_size * args.block_size
    summary = {
        "round": round_no,
        "steps": [start_step, end_step],
        "steps_run": len(losses),
        "loss_first": first,
        "loss_last": last,
        "loss_min": min(losses) if losses else loss_first,
        "heldout_loss": ho,
        "seconds": round(secs, 1),
        "tokens_per_sec": round(n_tok / max(0.001, secs), 1),
        "params": params,
        "vocab_size": tok.vocab_size,
        "out": str(out),
    }
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    (staging / "bpe_log.json").write_text(json.dumps(summary, indent=1))
    print(
        f"round {round_no} done: loss {first:.4f} -> {last:.4f} "
        f"({summary['tokens_per_sec']:.0f} tok/s) in {secs:.0f}s",
        flush=True,
    )
    print("candidate (NOT promoted):", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
