"""Train one native brain: continued training from v1 tiny-gpt.pt on an
Echoverse-engine REIM/RIEM simulation corpus.

Part of the 4-component order (Chauncey, 2026-09-22):
  (1) corpus  - single software-knowledge corpus (retrieval side)
  (2) memory  - seeded-not-harvested retrieval over that corpus
  (3) brain   - THIS: 3 training runs @ 10,000 steps each (brains a/b/c)
  (4) collective - spec only, not built

TRAINING SOURCE LAW: the ONLY neural-training text is the Echoverse engine's
hypothesize -> simulate -> train corpora
(train/echoverse/corpus_echoverse_{a,b,c}.jsonl), built from the Grok-made
LEVI engine lineage (the_pack/echoverse.py REIM/RIEM). NO scraped/external
software text enters the neural path - that belongs to the corpus/memory
retrieval side only. The identity anchor is a small mix (default 5%) of
kind="identity" records from corpus.jsonl (LEVI's own voice/registers),
extracted by kind - never the course/scraped chunks.

Rules enforced by this script:
- NEVER modifies weights/tiny-gpt.pt (v1, 600 steps, 3,271,168 params). The
  base checkpoint checksum is verified before every run.
- Brain weights land in weights/brains/ (git-ignored, local only). Checkpoints
  every 500 steps are ALL kept - nothing is ever deleted (nothing-thrown-away
  law); the old draft's unlink() of older checkpoints is removed.
- Logs, metrics, and eval reports go to train/echoverse/reports/ (committed).
- Held-out eval every 1000 steps against the corpus's own
  heldout_echoverse_{a,b,c}.jsonl, which is NEVER trained on (proven disjoint,
  P7). v2 failure-mode guard: if held-out perplexity degrades >15% above the
  pre-training baseline at step >= 3000, the run STOPS, the weights are NOT
  promoted, and the report says so honestly.
- Stops on NaN or loss explosion; reports instead of promoting garbage.
- Honest cost estimate from 20 warmup steps BEFORE the full run.
- Crash recovery: --resume continues from the latest checkpoint.

Requires torch CPU (lives in train/ only; core stays stdlib-only).

Usage:
    python3 train_brain.py --name a --steps 10000 --seed 101
    # brain a trains on echoverse/corpus_echoverse_a.jsonl, held-out
    # echoverse/heldout_echoverse_a.jsonl. brains b/c likewise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from train import TinyGPT, cpu_state_dict, get_batch, resolve_device  # noqa: E402

WEIGHTS = HERE.parent / "weights"
BASE_CKPT = WEIGHTS / "tiny-gpt.pt"
BRAINS = WEIGHTS / "brains"
ECHOVERSE = HERE / "echoverse"
REPORTS = ECHOVERSE / "reports"

# v1 base immutability: verified before every run (first 16 hex of sha256).
BASE_SHA_PREFIX = None  # filled from BASE_SHA_FILE if present
BASE_SHA_FILE = WEIGHTS / "tiny-gpt.sha256"

DEGRADE_TOL = 1.15  # held-out ppl may not exceed baseline * this (after step 3000)
DEGRADE_MIN_STEP = 3000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_texts(path: Path, kind: str | None = None) -> str:
    """Load record texts from a JSONL corpus, optionally filtered by kind."""
    texts = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e
            if kind is not None and rec.get("kind") != kind:
                continue
            t = rec.get("text", "")
            if t:
                texts.append(t)
    if kind is not None and not texts:
        raise ValueError(f"{path}: no records of kind={kind!r} (anchor empty)")
    return "\n\n".join(texts)


def get_batch_mixed(anchor_data, sim_data, batch_size, block_size, anchor_ratio):
    n_anchor = int(batch_size * anchor_ratio)
    n_sim = batch_size - n_anchor
    xs, ys = [], []
    if n_anchor > 0:
        x, y = get_batch(anchor_data, n_anchor, block_size)
        xs.append(x)
        ys.append(y)
    if n_sim > 0:
        x, y = get_batch(sim_data, n_sim, block_size)
        xs.append(x)
        ys.append(y)
    x = torch.cat(xs, dim=0)
    y = torch.cat(ys, dim=0)
    perm = torch.randperm(x.size(0))
    return x[perm], y[perm]


@torch.no_grad()
def heldout_perplexity(model, held_data, block_size, vocab_size, dev) -> float:
    """Mean NLL per token over the held-out set -> perplexity. Never trained on."""
    model.eval()
    total_nll = 0.0
    total_tok = 0
    for start in range(0, len(held_data) - block_size, block_size):
        x = held_data[start : start + block_size].unsqueeze(0).to(dev)
        y = held_data[start + 1 : start + block_size + 1].unsqueeze(0).to(dev)
        logits = model(x)
        nll = F.cross_entropy(logits.view(-1, vocab_size), y.view(-1),
                              reduction="sum").item()
        total_nll += nll
        total_tok += y.numel()
    model.train()
    return math.exp(total_nll / total_tok) if total_tok else float("inf")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="brain name: a, b, or c")
    ap.add_argument("--corpus", default=None,
                    help="default: echoverse/corpus_echoverse_<name>.jsonl")
    ap.add_argument("--heldout", default=None,
                    help="default: echoverse/heldout_echoverse_<name>.jsonl")
    ap.add_argument("--anchor-corpus", default="corpus.jsonl",
                    help="source of identity-anchor records (kind-filtered)")
    ap.add_argument("--anchor-kind", default="identity",
                    help="record kind used for the identity anchor")
    ap.add_argument("--anchor-ratio", type=float, default=0.05,
                    help="fraction of each batch from the identity anchor")
    ap.add_argument("--steps", type=int, default=10000)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--seed", type=int, default=None,
                    help="default: 101/202/303 for brains a/b/c")
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--ckpt-every", type=int, default=500)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    if args.name not in ("a", "b", "c"):
        print("brain name must be a, b, or c", flush=True)
        return 2
    default_seeds = {"a": 101, "b": 202, "c": 303}
    if args.seed is None:
        args.seed = default_seeds[args.name]
    if args.corpus is None:
        args.corpus = f"echoverse/corpus_echoverse_{args.name}.jsonl"
    if args.heldout is None:
        args.heldout = f"echoverse/heldout_echoverse_{args.name}.jsonl"

    torch.manual_seed(args.seed)
    dev = resolve_device(args.device)
    print(f"brain {args.name}: device {dev}, steps {args.steps}, seed {args.seed}",
          flush=True)

    # v1 base immutability check
    if not BASE_CKPT.is_file():
        print(f"ABORT: base weights missing: {BASE_CKPT}", flush=True)
        return 2
    base_sha = sha256_file(BASE_CKPT)
    if BASE_SHA_FILE.is_file():
        expected = BASE_SHA_FILE.read_text().strip().split()[0]
        if base_sha != expected:
            print(f"ABORT: v1 base checksum changed!\n  got      {base_sha}\n"
                  f"  expected {expected}", flush=True)
            return 2
        print(f"v1 base checksum OK ({base_sha[:16]}...)", flush=True)
    else:
        print(f"NOTE: no {BASE_SHA_FILE.name}; recording current base sha "
              f"{base_sha[:16]}... in report", flush=True)

    ckpt = torch.load(BASE_CKPT, map_location=dev, weights_only=False)
    config = ckpt["config"]
    chars = ckpt["chars"]
    stoi = {c: i for i, c in enumerate(chars)}
    vocab_size = len(chars)
    print(f"base: v1 {config['steps']} steps, vocab {vocab_size}, "
          f"params {config['params']:,}", flush=True)

    def p(pth):
        pth = Path(pth)
        return pth if pth.is_absolute() else HERE / pth

    corpus_path = p(args.corpus)
    sim_text = load_texts(corpus_path)  # Echoverse simulations ONLY
    anchor_text = load_texts(p(args.anchor_corpus), kind=args.anchor_kind)
    held_text = load_texts(p(args.heldout))
    manifest_path = str(corpus_path) + ".manifest.json"
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    print(f"  simulation corpus: {corpus_path.name}: {len(sim_text):,} chars "
          f"(variant {manifest['engine_variant']})", flush=True)
    print(f"  identity anchor: kind={args.anchor_kind}: {len(anchor_text):,} chars "
          f"(mix ratio {args.anchor_ratio})", flush=True)
    print(f"  held-out: {len(held_text):,} chars (never trained on)", flush=True)

    for label, text in (("simulation", sim_text), ("anchor", anchor_text),
                        ("heldout", held_text)):
        missing = sorted(set(text) - set(stoi))
        if missing:
            print(f"ABORT: {label} corpus has {len(missing)} chars outside "
                  f"the v1 vocab: {missing[:12]}", flush=True)
            return 2

    sim_data = torch.tensor([stoi[c] for c in sim_text], dtype=torch.long)
    anchor_data = torch.tensor([stoi[c] for c in anchor_text], dtype=torch.long)
    held_data = torch.tensor([stoi[c] for c in held_text], dtype=torch.long)

    model = TinyGPT(vocab_size, n_layer=config["n_layer"],
                    n_head=config["n_head"], n_embd=config["n_embd"],
                    block_size=config["block_size"])
    model.load_state_dict(ckpt["model_state"])
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    block_size = model.block_size
    model.train()

    BRAINS.mkdir(parents=True, exist_ok=True)
    ckpt_dir = BRAINS / f"ckpt_{args.name}"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    loss_log = REPORTS / f"brain_{args.name}_loss.jsonl"
    report_path = REPORTS / f"brain_{args.name}_report.json"

    start_step = 1
    loss_first = None
    loss_min = None
    evals = []  # [step, heldout_ppl]
    if args.resume:
        lat = sorted(ckpt_dir.glob("step-*.pt"))
        lat = [c for c in lat if "STOPPED" not in c.name]
        if lat:
            r = torch.load(lat[-1], map_location=dev, weights_only=False)
            model.load_state_dict(r["model_state"])
            opt.load_state_dict(r["optim_state"])
            start_step = r["step"] + 1
            loss_first = r.get("loss_first")
            loss_min = r.get("loss_min")
            evals = r.get("evals", [])
            print(f"resumed from {lat[-1].name} at step {start_step}", flush=True)

    # baseline: v1 weights on the held-out set, before any new training
    if not evals:
        base_ppl = heldout_perplexity(model, held_data, block_size,
                                      vocab_size, dev)
        evals.append([0, base_ppl])
        print(f"baseline (v1 weights) held-out perplexity: {base_ppl:.4f}",
              flush=True)
    baseline_ppl = evals[0][1]
    best_ppl = min(p for _, p in evals)

    if start_step == 1:
        W = 20
        t0 = time.time()
        for _ in range(W):
            x, y = get_batch_mixed(anchor_data, sim_data, args.batch_size,
                                   block_size, args.anchor_ratio)
            x, y = x.to(dev), y.to(dev)
            loss = F.cross_entropy(model(x).view(-1, vocab_size), y.view(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
        warm = time.time() - t0
        est = warm / W * args.steps
        print(f"cost estimate: {warm:.1f}s / {W} steps -> "
              f"~{est:.0f}s (~{est/60:.1f} min) for {args.steps} steps",
              flush=True)

    t0 = time.time()
    degraded = False
    stop_reason = None
    step = start_step - 1
    try:
        for step in range(start_step, args.steps + 1):
            x, y = get_batch_mixed(anchor_data, sim_data, args.batch_size,
                                   block_size, args.anchor_ratio)
            x, y = x.to(dev), y.to(dev)
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, vocab_size), y.view(-1))
            lv = loss.item()
            if loss_first is None:
                loss_first = lv
            loss_min = lv if loss_min is None else min(loss_min, lv)
            if not math.isfinite(lv):
                stop_reason = f"non-finite loss at step {step}"
                break
            if lv > 20.0:
                stop_reason = f"loss explosion ({lv:.2f}) at step {step}"
                break
            opt.zero_grad()
            loss.backward()
            opt.step()

            if step % 50 == 0 or step == 1:
                with open(loss_log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"step": step, "loss": round(lv, 4),
                                         "t": round(time.time() - t0, 1)}) + "\n")
            if step % max(1, args.steps // 10) == 0:
                print(f"  brain {args.name} step {step}/{args.steps} "
                      f"loss {lv:.4f}", flush=True)

            if step % args.ckpt_every == 0:
                # ALL checkpoints kept: nothing is ever deleted.
                cp = ckpt_dir / f"step-{step:06d}.pt"
                torch.save({"model_state": cpu_state_dict(model),
                            "optim_state": opt.state_dict(),
                            "step": step, "loss_first": loss_first,
                            "loss_min": loss_min, "evals": evals}, cp)

            if step % args.eval_every == 0:
                ppl = heldout_perplexity(model, held_data, block_size,
                                         vocab_size, dev)
                evals.append([step, ppl])
                best_ppl = min(best_ppl, ppl)
                print(f"  brain {args.name} step {step}: held-out ppl "
                      f"{ppl:.4f} (baseline {baseline_ppl:.4f}, "
                      f"best {best_ppl:.4f})", flush=True)
                if step >= DEGRADE_MIN_STEP and ppl > baseline_ppl * DEGRADE_TOL:
                    degraded = True
                    stop_reason = (
                        f"HELD-OUT DEGRADATION: ppl {ppl:.4f} exceeds "
                        f"baseline {baseline_ppl:.4f} x {DEGRADE_TOL} at "
                        f"step {step} - v2 failure mode. Run stopped, "
                        f"weights NOT promoted.")
                    break
    except KeyboardInterrupt:
        stop_reason = f"interrupted by operator at step {step}"

    elapsed = time.time() - t0
    final_path = BRAINS / f"brain_{args.name}.pt"
    promoted = not degraded and stop_reason is None
    if promoted:
        torch.save({"model_state": cpu_state_dict(model), "chars": chars,
                    "config": {**config, "brain": args.name,
                               "continued_steps": args.steps,
                               "continued_lr": args.lr,
                               "continued_seed": args.seed,
                               "anchor_ratio": args.anchor_ratio,
                               "anchor_kind": args.anchor_kind,
                               "training_source": "echoverse-sim",
                               "engine_variant": manifest["engine_variant"],
                               "corpus_sha256": manifest["sha256"],
                               "base_sha256": base_sha}}, final_path)
    else:
        # kept for inspection, never promoted
        cp = ckpt_dir / f"step-{step:06d}-STOPPED.pt"
        torch.save({"model_state": cpu_state_dict(model), "step": step,
                    "evals": evals, "stop_reason": stop_reason}, cp)

    report = {
        "brain": args.name,
        "training_source": "echoverse-sim",
        "engine_variant": manifest["engine_variant"],
        "lineage": manifest["lineage"],
        "corpus": corpus_path.name,
        "corpus_sha256": manifest["sha256"],
        "base_sha256": base_sha,
        "steps_completed": step,
        "steps_planned": args.steps,
        "seconds": round(elapsed, 1),
        "loss_first": round(loss_first, 4) if loss_first is not None else None,
        "loss_min": round(loss_min, 4) if loss_min is not None else None,
        "baseline_heldout_ppl": round(baseline_ppl, 4),
        "best_heldout_ppl": round(best_ppl, 4),
        "final_heldout_ppl": round(evals[-1][1], 4) if evals else None,
        "evals": [[s, round(p, 4)] for s, p in evals],
        "promoted": promoted,
        "weights": str(final_path) if promoted else None,
        "stop_reason": stop_reason,
        "seed": args.seed,
        "lr": args.lr,
        "anchor_ratio": args.anchor_ratio,
        "anchor_kind": args.anchor_kind,
    }
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1), flush=True)
    print(f"brain {args.name}: "
          f"{'PROMOTED -> ' + str(final_path) if promoted else 'NOT PROMOTED: ' + str(stop_reason)}",
          flush=True)
    return 0 if promoted else 3


if __name__ == "__main__":
    raise SystemExit(main())
