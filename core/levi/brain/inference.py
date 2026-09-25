"""Offline inference for the native-brain proof-of-learning weights.

Loads ``core/levi/brain/weights/tiny-gpt.pt`` (a char-level causal GPT,
4 layers / 256 dim / 4 heads / block 128, vocab 162 chars, 3,271,168
params, 600 training steps on the course corpus) and generates text
continuations on CPU — no network, no training, no weight changes.

HONESTY LAW — this is a proof-of-learning brain, and its samples are
garbled (see ``weights/eval.json`` and ``weights/samples.md``). This
module runs the brain for real — it never simulates a brain, never
returns canned text — but its output is labeled as raw brain
continuation everywhere it is used, never as reasoning. Callers
(``levi.alpha.reason``) keep the decider on the rules engine and say
which mind did what.

Stdlib only at import time: ``torch`` is imported lazily inside the
functions that need it. ``BrainError`` is raised (never a crash through
torch) whenever inference cannot run — missing torch, missing or
corrupt weights, unusable prompts — so callers can report honestly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-brain/inference"

# Hard generation cap: one call never produces more than this many chars.
MAX_NEW_CHARS_CAP = 2048

# The checkpoint records its own expected sha256 in the weights README;
# verify on load so a corrupt download is reported, not inferred through.
EXPECTED_SHA256 = "7474e24f97c8df50904a26367a27e2e57dbaa050b0238cba1b1e79a46997e3b2"


class BrainError(Exception):
    """Raised when brain inference cannot run — the reason IS the report."""


# ---------------------------------------------------------------- model
# A local mirror of the char-level GPT in train/train.py. The checkpoint
# carries its own ``config`` + ``chars`` + ``model_state``, so no corpus
# or train-time module is needed. Torch is imported lazily by the loader.


def _build_model(torch, nn, F, config, vocab_size):  # noqa: N803
    import math

    class CausalSelfAttention(nn.Module):
        def __init__(self, n_embd, n_head, block_size):
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
        def __init__(self):
            super().__init__()
            n_embd = int(config["n_embd"])
            n_head = int(config["n_head"])
            n_layer = int(config["n_layer"])
            block_size = int(config["block_size"])
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

    return TinyGPT()


# ---------------------------------------------------------------- loading


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class BrainInference:
    """A loaded native-brain weights file, ready to continue text."""

    def __init__(
        self,
        model: Any,
        torch: Any,
        chars: List[str],
        config: Dict[str, Any],
        weights_path: Path,
        sha256: str,
    ) -> None:
        self._model = model
        self._torch = torch
        self._chars = chars
        self._config = config
        self._weights_path = weights_path
        self._sha256 = sha256
        self._stoi = {c: i for i, c in enumerate(chars)}
        self._n_params = sum(p.numel() for p in model.parameters())

    # -- provenance ------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """Provenance of the loaded brain — everything a reader can verify."""
        cfg = self._config
        return {
            "origin": ORIGIN,
            "weights_path": str(self._weights_path),
            "sha256": self._sha256,
            "sha256_expected": EXPECTED_SHA256,
            "sha256_match": self._sha256 == EXPECTED_SHA256,
            "params": self._n_params,
            "training_steps": int(cfg.get("steps", -1)),
            "vocab_chars": len(self._chars),
            "corpus_chars": int(cfg.get("corpus_chars", -1)),
            "corpus_file": str(cfg.get("corpus_file", "?")),
            "architecture": {
                "layers": int(cfg["n_layer"]),
                "heads": int(cfg["n_head"]),
                "embed": int(cfg["n_embd"]),
                "block_size": int(cfg["block_size"]),
                "level": "char",
            },
            "honest_note": (
                "Proof-of-learning model: the loss curve proves the "
                "architecture learns, but generated samples are garbled — "
                "this brain cannot reason, converse, or replace a language "
                "model. See weights/eval.json and weights/samples.md."
            ),
        }

    @property
    def chars(self) -> List[str]:
        return list(self._chars)

    # -- generation ------------------------------------------------------

    def encode(self, text: str) -> Tuple[List[int], int]:
        """Encode ``text`` to vocab ids; chars outside the vocab map to a
        space and are counted (returned as the second value)."""
        ids: List[int] = []
        unmapped = 0
        for ch in text:
            idx = self._stoi.get(ch)
            if idx is None:
                ids.append(self._stoi[" "])
                unmapped += 1
            else:
                ids.append(idx)
        return ids, unmapped

    def generate(
        self,
        prompt: str,
        max_new_chars: int = 160,
        temperature: float = 0.8,
        seed: int = 1337,
    ) -> Dict[str, Any]:
        """Continue ``prompt`` with raw brain text.

        Deterministic for a fixed (prompt, seed, temperature): sampling
        uses a seeded ``torch.Generator``. ``temperature <= 0`` selects
        greedily. ``max_new_chars`` is clamped to [1, MAX_NEW_CHARS_CAP].
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise BrainError("empty prompt: nothing to continue")
        torch = self._torch
        block_size = int(self._config["block_size"])
        max_new_chars = max(1, min(int(max_new_chars), MAX_NEW_CHARS_CAP))
        if temperature is None or temperature < 0:
            raise BrainError(f"temperature must be >= 0, got {temperature!r}")

        ids, unmapped = self.encode(prompt.strip())
        if not ids:
            raise BrainError("prompt has no usable characters")
        idx = torch.tensor([ids[-block_size:]], dtype=torch.long)

        generator = torch.Generator().manual_seed(int(seed))
        self._model.eval()
        with torch.no_grad():
            for _ in range(max_new_chars):
                logits = self._model(idx[:, -block_size:])[0, -1]
                if temperature == 0:
                    next_id = int(torch.argmax(logits))
                else:
                    probs = torch.softmax(logits / temperature, dim=-1)
                    next_id = int(torch.multinomial(probs, 1, generator=generator))
                idx = torch.cat(
                    [idx, torch.tensor([[next_id]], dtype=torch.long)], dim=1
                )

        continuation = "".join(self._chars[i] for i in idx[0, len(ids) :].tolist())
        return {
            "prompt": prompt.strip(),
            "continuation": continuation,
            "text": prompt.strip() + continuation,
            "unmapped_chars": unmapped,
            "max_new_chars": max_new_chars,
            "temperature": float(temperature),
            "seed": int(seed),
            "params": self._n_params,
            "label": "raw brain continuation — not reasoning",
        }


def load_brain(weights_path: Optional[str] = None) -> BrainInference:
    """Load the native-brain weights for inference.

    ``weights_path`` defaults to ``core/levi/brain/weights/tiny-gpt.pt``.
    Raises ``BrainError`` with an honest reason whenever inference cannot
    run — never a raw torch traceback.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        raise BrainError(
            "torch is not installed in this environment — "
            "the native-brain weights cannot be exercised"
        ) from None
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    path = (
        Path(weights_path)
        if weights_path
        else Path(__file__).resolve().parent / "weights" / "tiny-gpt.pt"
    )
    if not path.is_file():
        raise BrainError(
            f"no native-brain weights found at {path} — nothing to infer over"
        )

    try:
        checkpoint = torch.load(str(path), map_location="cpu", weights_only=True)
    except Exception as exc:  # noqa: BLE001 - the reason IS the report
        raise BrainError(
            f"weights file present but unreadable ({exc.__class__.__name__}: {exc})"
        ) from exc
    if not isinstance(checkpoint, dict):
        raise BrainError(
            f"weights file is not a checkpoint dict (got {type(checkpoint).__name__})"
        )
    for key in ("model_state", "chars", "config"):
        if key not in checkpoint:
            raise BrainError(f"checkpoint missing required key {key!r}")
    chars = checkpoint["chars"]
    config = checkpoint["config"]
    if not isinstance(chars, list) or not chars:
        raise BrainError("checkpoint 'chars' is not a usable vocabulary")
    if not isinstance(config, dict):
        raise BrainError("checkpoint 'config' is not a usable config dict")
    for key in ("n_layer", "n_head", "n_embd", "block_size"):
        if key not in config:
            raise BrainError(f"checkpoint config missing required key {key!r}")

    model = _build_model(torch, nn, F, config, len(chars))
    try:
        model.load_state_dict(checkpoint["model_state"], strict=True)
    except Exception as exc:  # noqa: BLE001 - the reason IS the report
        raise BrainError(
            f"weights do not match the char-GPT architecture "
            f"({exc.__class__.__name__}: {exc})"
        ) from exc
    model.eval()
    return BrainInference(
        model=model,
        torch=torch,
        chars=chars,
        config=config,
        weights_path=path,
        sha256=_sha256(path),
    )


__all__ = ["ORIGIN", "BrainError", "BrainInference", "load_brain", "MAX_NEW_CHARS_CAP"]
