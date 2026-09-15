"""Train LEVI's tiny brain: a small character-level GPT on the course corpus.

Pipeline: prepare_corpus.py -> corpus.jsonl -> this script -> weights/tiny-gpt.pt

This is a PROOF-OF-LEARNING model (~2-4M params, CPU-trainable), not a
capable brain. It demonstrates that the full loop works end to end:
corpus -> training -> decreasing loss -> samples. See docs/BRAIN_TRAINING.md
for honest limits and the path to a real model (LoRA fine-tune of the
levi-local Qwen weights on GPU).

Requires torch (CPU). Install: pip install -r requirements.txt
(this lives OUTSIDE core — the core runtime stays stdlib-only).

Usage:
    python3 train.py [--data corpus.jsonl] [--steps 1500] [--out ../weights]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- model


class CausalSelfAttention(nn.Module):
    def __init__(self, n_embd: int, n_head: int, block_size: int):
        super().__init__()
        assert n_embd % n_head == 0
        self.n_head = n_head
        self.head_dim = n_embd // n_head
        self.qkv = nn.Linear(n_embd, 3 * n_embd, bias=False)
        self.proj = nn.Linear(n_embd, n_embd, bias=False)
        self.register_buffer(
            "mask",
            torch.tril(torch.ones(block_size, block_size)).view(
                1, 1, block_size, block_size
            ),
        )

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att = F.softmax(att, dim=-1)
        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class Block(nn.Module):
    def __init__(self, n_embd, n_head, block_size):
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = CausalSelfAttention(n_embd, n_head, block_size)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd), nn.GELU(), nn.Linear(4 * n_embd, n_embd)
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class TinyGPT(nn.Module):
    def __init__(self, vocab_size, n_layer=4, n_head=4, n_embd=256, block_size=128):
        super().__init__()
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Embedding(block_size, n_embd)
        self.blocks = nn.Sequential(
            *[Block(n_embd, n_head, block_size) for _ in range(n_layer)]
        )
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)

    def forward(self, idx):
        B, T = idx.shape
        x = self.tok_emb(idx) + self.pos_emb(torch.arange(T, device=idx.device))
        x = self.blocks(x)
        return self.head(self.ln_f(x))

    def n_params(self):
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------- data


def load_corpus(path: Path) -> str:
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


def build_vocab(text: str):
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    return chars, stoi


def get_batch(data: torch.Tensor, batch_size: int, block_size: int):
    ix = torch.randint(0, len(data) - block_size - 1, (batch_size,))
    x = torch.stack([data[i : i + block_size] for i in ix])
    y = torch.stack([data[i + 1 : i + block_size + 1] for i in ix])
    return x, y


# ---------------------------------------------------------------- train


def train(
    data_path: Path,
    steps: int,
    out_dir: Path,
    seed: int = 1337,
    batch_size: int = 32,
    lr: float = 3e-4,
) -> dict:
    torch.manual_seed(seed)
    random.seed(seed)
    text = load_corpus(data_path)
    if len(text) < 10_000:
        raise SystemExit(
            f"corpus too small ({len(text)} chars); run prepare_corpus.py first"
        )
    chars, stoi = build_vocab(text)
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)

    model = TinyGPT(len(chars))
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    block_size = model.block_size

    losses = []
    t0 = time.time()
    model.train()
    for step in range(1, steps + 1):
        x, y = get_batch(data, batch_size, block_size)
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, len(chars)), y.view(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
        if step % max(1, steps // 10) == 0 or step == 1:
            print(f"  step {step}/{steps}  loss {loss.item():.4f}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "chars": chars,
            "config": {
                "n_layer": 4,
                "n_head": 4,
                "n_embd": 256,
                "block_size": block_size,
                "steps": steps,
                "batch_size": batch_size,
                "lr": lr,
                "seed": seed,
                "params": model.n_params(),
                "corpus_chars": len(text),
                "corpus_file": str(data_path),
            },
        },
        out_dir / "tiny-gpt.pt",
    )
    log = {
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "loss_min": min(losses),
        "steps": steps,
        "seconds": round(time.time() - t0, 1),
        "params": model.n_params(),
        "vocab_size": len(chars),
    }
    (out_dir / "train_log.json").write_text(json.dumps(log, indent=1))
    print(
        f"params: {model.n_params():,}  loss {losses[0]:.4f} -> {losses[-1]:.4f} "
        f"(min {min(losses):.4f}) in {log['seconds']}s"
    )
    print("wrote", out_dir / "tiny-gpt.pt")
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "corpus.jsonl"))
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--out", default=str(HERE.parent / "weights"))
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args(argv)
    train(Path(args.data), args.steps, Path(args.out), seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
