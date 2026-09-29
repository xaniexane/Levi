#!/usr/bin/env python3
"""LEVI native brain — BPE round 3 (serious round).

Chauncey 2026-09-21: the real BPE/token-level round on the v3 curriculum
corpus. LeviBrainV2 (6L/6H/384E, ~13.77M params, tied embeddings, RoPE,
RMSNorm, SwiGLU) + levi-bpe-v2 tokenizer (8192, explicit <bos>/<eos>).

Short benchmark round first: N_STEPS steps, held-out CE + the fixed
13-prompt qualitative suite every EVAL_EVERY steps. CPU-only.

Rule: stop early if loss does not move honestly.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))          # .../core/levi/brain/train
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))  # ~/workspace/levi
TRAIN_DIR = _HERE

# NOTE: import torch BEFORE touching sys.path — core/levi/ contains a
# package named `torch` (levi.torch) that would shadow the real one.
import torch
import torch.nn.functional as F

sys.path.insert(0, TRAIN_DIR)

from tok import ByteBPETokenizer
from model_v2 import build_model, default_param_count

MODEL_CONFIG = {
    "vocab_size": 8192,
    "block_size": 256,
    "n_layer": 6,
    "n_head": 6,
    "n_kv_head": 6,  # full MHA
    "n_embd": 384,
    "ffn_mult": 8 / 3,
    "dropout": 0.0,
    "tie_weights": True,
}

CURRICULUM = os.path.join(TRAIN_DIR, "corpus_curriculum.jsonl")
PROGRAMMING = os.path.join(TRAIN_DIR, "corpus_programming.jsonl")
DIALOGUE = os.path.join(TRAIN_DIR, "corpus_dialogue.jsonl")
TOKENIZER_PATH = os.environ.get(
    "LEVI_TOKENIZER_PATH",
    os.path.join(REPO, "core", "levi", "brain", "tokenizers", "levi-bpe-v2", "tokenizer.json"),
)

QUALITATIVE_PROMPTS = [
    "User: 2+2\nLEVI:",
    "User: 7x8\nLEVI:",
    "User: what is 144/12\nLEVI:",
    "User: solve for x: x + 7 = 15\nLEVI:",
    "User: what is the capital of France\nLEVI:",
    "User: name the three branches of US government\nLEVI:",
    "User: fix the grammar: she dont know nothing\nLEVI:",
    "User: the system is down, what do I do\nLEVI:",
    "User: summarize: the dog barked, the mail arrived, the cat slept\nLEVI:",
    "User: what causes the seasons\nLEVI:",
    "User: state Newton's first law\nLEVI:",
    "User: the tests pass\nLEVI:",
    "User: I'm overwhelmed. Everything is due at once.\nLEVI:",
    "User: write a function that doubles a number\nLEVI:",
    "User: what does this print: for i in range(3): print(i)\nLEVI:",
    "User: fix this code: pirnt('hi')\nLEVI:",
]


def load_sequences(tok: ByteBPETokenizer, seed: int = 20260921):
    texts = []
    for path in (CURRICULUM, PROGRAMMING, DIALOGUE):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    texts.append(json.loads(line)["text"])
    rng = random.Random(seed)
    rng.shuffle(texts)
    bos, eos = tok.bos_id, tok.eos_id
    seqs = []
    for t in texts:
        ids = [bos] + tok.encode(t) + [eos]
        seqs.append(ids)
    return seqs


@torch.no_grad()
def generate(model, tok, prompt: str, max_new: int = 60, temperature: float = 0.9, top_k: int = 40):
    model.eval()
    ids = [tok.bos_id] + tok.encode(prompt)
    x = torch.tensor([ids], dtype=torch.long)
    for _ in range(max_new):
        x_cond = x[:, -MODEL_CONFIG["block_size"]:]
        logits = model(x_cond)[0, -1]
        if temperature <= 0:
            nxt = logits.argmax().item()
        else:
            logits = logits / temperature
            if top_k > 0:
                vals, _ = torch.topk(logits, top_k)
                logits[logits < vals[-1]] = float("-inf")
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, 1).item()
        if nxt == tok.eos_id:
            break
        ids.append(nxt)
        x = torch.tensor([ids], dtype=torch.long)
    return tok.decode(ids[1:])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--steps", type=int, default=800)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seq", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--eval-every", type=int, default=100)
    ap.add_argument("--out", default=os.path.join(TRAIN_DIR, "weights", "bpe_round3"))
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--resume", default=None, help="checkpoint .pt to resume from")
    args = ap.parse_args(argv)

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(max(1, os.cpu_count() or 4))

    tok = ByteBPETokenizer.load(TOKENIZER_PATH)
    assert tok.vocab_size == 8192, tok.vocab_size
    print(f"tokenizer: {TOKENIZER_PATH} vocab={tok.vocab_size} bos={tok.bos_id} eos={tok.eos_id}", flush=True)

    seqs = load_sequences(tok, args.seed)
    print(f"sequences: {len(seqs)}", flush=True)
    split = int(len(seqs) * 0.98)
    train_seqs, held_seqs = seqs[:split], seqs[split:]
    print(f"train: {len(train_seqs)} held-out: {len(held_seqs)}", flush=True)

    model = build_model(MODEL_CONFIG)
    n_params = default_param_count(MODEL_CONFIG)
    print(f"model: LeviBrainV2 params={n_params:,}", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.05)

    start_step = 0
    if args.resume and os.path.exists(args.resume):
        ck = torch.load(args.resume, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        start_step = ck["step"]
        print(f"resumed from {args.resume} at step {start_step}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "loss.jsonl")

    def lr_at(step):
        if step < args.warmup:
            return args.lr * (step + 1) / args.warmup
        prog = (step - args.warmup) / max(1, args.steps - args.warmup)
        return args.lr * 0.5 * (1 + math.cos(math.pi * min(1.0, prog)))

    def batch_xy():
        xs, ys = [], []
        for _ in range(args.batch):
            s = random.choice(train_seqs)
            if len(s) > args.seq + 1:
                i = random.randrange(0, len(s) - args.seq - 1)
                seg = s[i : i + args.seq + 1]
            else:
                seg = s + [tok.eos_id] * (args.seq + 1 - len(s))
            xs.append(seg[:-1])
            ys.append(seg[1:])
        return torch.tensor(xs, dtype=torch.long), torch.tensor(ys, dtype=torch.long)

    @torch.no_grad()
    def heldout_ce():
        # Same per-sequence crop procedure as training: no cross-document
        # boundary transitions, so train and held-out are the same task.
        model.eval()
        rng_h = random.Random(args.seed + 999)
        total, count = 0.0, 0
        for _ in range(50):
            s = rng_h.choice(held_seqs)
            if len(s) > args.seq + 1:
                i = rng_h.randrange(0, len(s) - args.seq - 1)
                seg = s[i : i + args.seq + 1]
            else:
                seg = s + [tok.eos_id] * (args.seq + 1 - len(s))
            x = torch.tensor([seg[:-1]], dtype=torch.long)
            y = torch.tensor([seg[1:]], dtype=torch.long)
            logits = model(x)
            total += F.cross_entropy(logits.view(-1, 8192), y.view(-1), reduction="sum").item()
            count += y.numel()
        model.train()
        return total / count

    model.train()
    t0 = time.time()
    for step in range(start_step, args.steps):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        x, y = batch_xy()
        opt.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, 8192), y.view(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if (step + 1) % 20 == 0 or step == start_step:
            dt = time.time() - t0
            msg = f"step {step+1}/{args.steps} loss={loss.item():.4f} lr={opt.param_groups[0]['lr']:.2e} elapsed={dt:.0f}s"
            print(msg, flush=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"step": step + 1, "loss": loss.item(), "lr": opt.param_groups[0]["lr"], "elapsed_s": dt}) + "\n")

        if (step + 1) % args.eval_every == 0:
            hce = heldout_ce()
            ppl = math.exp(hce)
            print(f"--- eval step {step+1}: held-out CE={hce:.4f} ppl={ppl:.1f}", flush=True)
            ckpt = os.path.join(args.out, f"round3_step{step+1}.pt")
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step + 1,
                        "held_ce": hce, "config": MODEL_CONFIG}, ckpt)
            print(f"checkpoint -> {ckpt}", flush=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"step": step + 1, "held_ce": hce, "ppl": ppl, "checkpoint": ckpt}) + "\n")
            for p in QUALITATIVE_PROMPTS:
                out = generate(model, tok, p)
                print(f"  SAMPLE {p[:40]!r} -> {out[len(p)-6:][:120]!r}", flush=True)
            model.train()

    final = os.path.join(args.out, "round3_final.pt")
    torch.save({"model": model.state_dict(), "step": args.steps, "config": MODEL_CONFIG}, final)
    print(f"done. final -> {final}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
