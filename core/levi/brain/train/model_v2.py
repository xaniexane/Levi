"""LEVI native brain v2 — a modern tiny transformer, CPU-trainable.

The successor to the ``TinyGPT`` seed in ``train.py`` (which stays untouched):
RMSNorm instead of LayerNorm, RoPE rotary position embeddings instead of
learned absolute positions (so context can extend to 512-1024+ tokens),
SwiGLU gated MLP instead of GELU, optional grouped-query attention,
optional embedding/output weight tying, and an optional gradient
checkpointing flag for memory-constrained training.

``build_model(cfg)`` takes a plain config dict so the v2 training harness
(SCAFFOLD worker's ``core/levi/brain/train/v2/``) can plug it in without
importing anything else from this module.

The v2 checkpoint contract lives here too (``CKPT_FORMAT``/``CKPT_VERSION``,
:func:`save_checkpoint`, :func:`load_checkpoint`) for torch-native
experiments. The harness's canonical training format is the numpy
``.npz`` + manifest format in ``v2/checkpoint.py`` — :func:`save_v2_checkpoint`
and :func:`load_v2_checkpoint` bridge a ``LeviBrainV2`` to exactly that
format, so checkpoints written here resume cleanly under the harness.

The harness also resolves ``levi.brain.train.model_v2:build_tokenizer`` as
its no-argument tokenizer builder — see :func:`build_tokenizer`.

Requires torch (CPU). Training-only dependency; the core runtime stays
stdlib-only.

Honest scope: an 8-15M parameter CPU model learns local statistics and
short-range structure. It will NOT reason, plan, or reliably recall facts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

# ------------------------------------------------------------------ config

DEFAULT_CFG: dict = {
    "vocab_size": 8192,
    "n_layer": 6,
    "n_head": 6,
    "n_kv_head": None,  # None -> n_head (plain MHA); set < n_head for GQA
    "n_embd": 384,
    "ffn_mult": 8 / 3,  # SwiGLU hidden dim = int(ffn_mult * n_embd)
    "block_size": 512,  # max context length
    "rope_theta": 10000.0,
    "tie_weights": True,  # share token embedding and output head
    "norm_eps": 1e-6,
    "dropout": 0.0,
    "gradient_checkpointing": False,  # trade compute for memory per block
}

# v2 checkpoint contract (adopted by the v2 training harness)
CKPT_FORMAT = "levi-brain-v2"
CKPT_VERSION = 1


def _merged_cfg(cfg: dict | None) -> dict:
    merged = dict(DEFAULT_CFG)
    if cfg:
        unknown = set(cfg) - set(DEFAULT_CFG)
        if unknown:
            raise ValueError(f"unknown model config keys: {sorted(unknown)}")
        merged.update(cfg)
    if merged["n_kv_head"] is None:
        merged["n_kv_head"] = merged["n_head"]
    n_embd, n_head, n_kv = merged["n_embd"], merged["n_head"], merged["n_kv_head"]
    if n_embd % n_head != 0:
        raise ValueError("n_embd must be divisible by n_head")
    if (n_embd // n_head) % 2 != 0:
        raise ValueError("head_dim must be even for RoPE")
    if n_head % n_kv != 0:
        raise ValueError("n_head must be divisible by n_kv_head")
    if merged["block_size"] < 1:
        raise ValueError("block_size must be >= 1")
    return merged


# ------------------------------------------------------------------ pieces


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        var = x.pow(2).mean(dim=-1, keepdim=True)
        x = x * torch.rsqrt(var + self.eps)
        return self.weight * x


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    d2 = x.shape[-1] // 2
    return torch.cat([-x[..., d2:], x[..., :d2]], dim=-1)


class RotaryEmbedding(nn.Module):
    """RoPE: rotate q/k by position-dependent angles. No learned params."""

    def __init__(self, head_dim: int, theta: float = 10000.0):
        super().__init__()
        inv_freq = 1.0 / (theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, nh, T, hd) -> same shape, positions 0..T-1
        t = torch.arange(x.shape[2], device=x.device, dtype=self.inv_freq.dtype)
        freqs = torch.outer(t, self.inv_freq)  # (T, hd/2)
        emb = torch.cat([freqs, freqs], dim=-1)  # (T, hd)
        cos = emb.cos()[None, None, :, :]
        sin = emb.sin()[None, None, :, :]
        return x * cos + _rotate_half(x) * sin


class CausalAttention(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        n_embd, n_head, n_kv = cfg["n_embd"], cfg["n_head"], cfg["n_kv_head"]
        self.n_head = n_head
        self.n_kv_head = n_kv
        self.n_rep = n_head // n_kv
        self.head_dim = n_embd // n_head
        self.q = nn.Linear(n_embd, n_head * self.head_dim, bias=False)
        self.kv = nn.Linear(n_embd, 2 * n_kv * self.head_dim, bias=False)
        self.proj = nn.Linear(n_embd, n_embd, bias=False)
        self.rope = RotaryEmbedding(self.head_dim, cfg["rope_theta"])
        self.drop = nn.Dropout(cfg["dropout"])
        # additive causal mask, sliced to (T, T) at runtime
        self.register_buffer(
            "_causal",
            torch.full((cfg["block_size"], cfg["block_size"]), float("-inf")).triu(1),
            persistent=False,
        )

    def forward(
        self, x: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        # mask: optional additive (B, 1, T, T) with 0.0 keep / -inf block,
        # e.g. from data_pipe.doc_boundary_mask for doc-isolated packing.
        B, T, _ = x.shape
        q = self.q(x).view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        kv = self.kv(x).view(B, T, self.n_kv_head, 2 * self.head_dim)
        k, v = kv.split(self.head_dim, dim=-1)
        k = k.transpose(1, 2).contiguous()
        v = v.transpose(1, 2).contiguous()
        q, k = self.rope(q), self.rope(k)
        if self.n_rep > 1:  # grouped-query: repeat kv heads
            k = k.repeat_interleave(self.n_rep, dim=1)
            v = v.repeat_interleave(self.n_rep, dim=1)
        att = (q @ k.transpose(-2, -1)) / (self.head_dim**0.5)
        att = att + self._causal[:T, :T]
        if mask is not None:
            att = att + mask
        att = F.softmax(att, dim=-1)
        att = self.drop(att)
        y = (att @ v).transpose(1, 2).contiguous().view(B, T, -1)
        return self.proj(y)


class SwiGLU(nn.Module):
    def __init__(self, n_embd: int, hidden: int):
        super().__init__()
        self.gate = nn.Linear(n_embd, hidden, bias=False)
        self.up = nn.Linear(n_embd, hidden, bias=False)
        self.down = nn.Linear(hidden, n_embd, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down(F.silu(self.gate(x)) * self.up(x))


class Block(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        self.ln1 = RMSNorm(cfg["n_embd"], cfg["norm_eps"])
        self.attn = CausalAttention(cfg)
        self.ln2 = RMSNorm(cfg["n_embd"], cfg["norm_eps"])
        hidden = int(cfg["ffn_mult"] * cfg["n_embd"])
        self.mlp = SwiGLU(cfg["n_embd"], hidden)

    def forward(
        self, x: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.mlp(self.ln2(x))
        return x


# ------------------------------------------------------------------ model


class LeviBrainV2(nn.Module):
    """Modern tiny decoder-only transformer. See module docstring for scope."""

    def __init__(self, cfg: dict | None = None):
        super().__init__()
        self.config = _merged_cfg(cfg)
        c = self.config
        self.tok_emb = nn.Embedding(c["vocab_size"], c["n_embd"])
        self.drop = nn.Dropout(c["dropout"])
        self.blocks = nn.ModuleList([Block(c) for _ in range(c["n_layer"])])
        self.ln_f = RMSNorm(c["n_embd"], c["norm_eps"])
        self.head = nn.Linear(c["n_embd"], c["vocab_size"], bias=False)
        if c["tie_weights"]:
            self.head.weight = self.tok_emb.weight
        self.grad_ckpt = c["gradient_checkpointing"]
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, std=0.02)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, std=0.02)

    def forward(
        self, idx: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        B, T = idx.shape
        if T > self.config["block_size"]:
            raise ValueError(
                f"sequence length {T} exceeds block_size {self.config['block_size']}"
            )
        x = self.drop(self.tok_emb(idx))
        for blk in self.blocks:
            if self.grad_ckpt and self.training:
                x = torch.utils.checkpoint.checkpoint(blk, x, mask, use_reentrant=False)
            else:
                x = blk(x, mask)
        return self.head(self.ln_f(x))

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new: int,
        temperature: float = 1.0,
        top_k: int = 0,
    ) -> torch.Tensor:
        """Greedy/temperature sampling for smoke checks (not a product API)."""
        self.eval()
        for _ in range(max_new):
            ctx = idx[:, -self.config["block_size"] :]
            logits = self(ctx)[:, -1, :]
            if temperature <= 0:
                nxt = logits.argmax(dim=-1, keepdim=True)
            else:
                logits = logits / temperature
                if top_k > 0:
                    v, _ = torch.topk(logits, top_k)
                    logits[logits < v[:, [-1]]] = float("-inf")
                nxt = torch.multinomial(F.softmax(logits, dim=-1), 1)
            idx = torch.cat([idx, nxt], dim=1)
        return idx


def build_model(cfg: dict | None = None) -> LeviBrainV2:
    """Build a v2 brain from a plain config dict (harness entry point)."""
    return LeviBrainV2(cfg)


def default_param_count(cfg: dict | None = None) -> int:
    """Param count for a config (instantiates the model; cheap, no compute)."""
    return build_model(cfg).n_params()


DEFAULT_TOKENIZER_PATH = Path(__file__).resolve().parent / "tokenizer.json"


def build_tokenizer(path: str | Path | None = None):
    """v2 harness entry point: no-argument tokenizer builder.

    Resolution order: explicit ``path`` > ``$LEVI_TOKENIZER_PATH`` >
    ``tokenizer.json`` next to this module. Returns a
    :class:`tok.ByteBPETokenizer` (has ``encode``/``decode``/``vocab_size``/
    ``eod_id``).

    Raises FileNotFoundError with the exact training command when no
    tokenizer file exists yet — the harness surfaces this instead of
    training on a silently wrong vocabulary.
    """
    if __package__:
        from .tok import ByteBPETokenizer
    else:  # imported as a top-level module (tests, standalone scripts)
        from tok import ByteBPETokenizer

    candidate = (
        Path(path)
        if path
        else Path(os.environ["LEVI_TOKENIZER_PATH"])
        if os.environ.get("LEVI_TOKENIZER_PATH")
        else DEFAULT_TOKENIZER_PATH
    )
    if not candidate.is_file():
        raise FileNotFoundError(
            f"v2 tokenizer not found at {candidate}; train one first:\n"
            f"  python3 tok.py --corpus corpus.jsonl --vocab 8192 --out {candidate}"
        )
    return ByteBPETokenizer.load(candidate)


# ------------------------------------------------------------------ checkpoint
# v2 checkpoint contract. SCAFFOLD's harness (train/v2/) had not landed when
# this was written; it should adopt these exact keys.


def save_checkpoint(
    path: str | Path,
    model: LeviBrainV2,
    optimizer: torch.optim.Optimizer | None = None,
    step: int = 0,
    extra: dict | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "format": CKPT_FORMAT,
            "version": CKPT_VERSION,
            "config": dict(model.config),
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict() if optimizer else None,
            "step": step,
            "extra": dict(extra or {}),
        },
        path,
    )
    return path


def load_checkpoint(
    path: str | Path,
    model: LeviBrainV2 | None = None,
    device: str = "cpu",
    strict: bool = True,
) -> dict:
    """Load a v2 checkpoint; optionally load weights into ``model``.

    Returns the full checkpoint dict (config, step, extra, ...). Raises
    ValueError on format/version mismatch so a v1 tiny-gpt.pt can never be
    silently loaded as v2.
    """
    ckpt = torch.load(path, map_location=device, weights_only=True)
    if ckpt.get("format") != CKPT_FORMAT:
        raise ValueError(
            f"not a {CKPT_FORMAT} checkpoint: {path} (format={ckpt.get('format')!r})"
        )
    if ckpt.get("version") != CKPT_VERSION:
        raise ValueError(
            f"unsupported {CKPT_FORMAT} version {ckpt.get('version')!r} "
            f"(expected {CKPT_VERSION})"
        )
    if model is not None:
        model.load_state_dict(ckpt["model_state"], strict=strict)
    return ckpt


# ------------------------------------------------------------------ v2 harness
# bridge: the harness's canonical checkpoint format is the numpy .npz +
# manifest format in v2/checkpoint.py (torch-optional). These helpers let a
# LeviBrainV2 write/read exactly that format so checkpoints resume cleanly
# under the v2 trainer. The torch .pt helpers above remain for quick
# ad-hoc experiments.


def _v2_checkpoint_module():
    """Import v2/checkpoint.py, whether via the installed levi package or
    via direct sys.path use of the train/ directory (tests, scripts)."""
    import importlib

    try:
        return importlib.import_module("levi.brain.train.v2.checkpoint")
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        return importlib.import_module("v2.checkpoint")


def save_v2_checkpoint(
    ckpt_dir: str | Path,
    model: LeviBrainV2,
    *,
    step: int,
    config_hash: str = "",
    metrics: dict | None = None,
    keep_last: int = 5,
) -> Path:
    """Save model weights in the harness v2 format (npz + manifest).

    The model config dict is embedded as ``__levi_config__`` so a loader
    can verify the architecture before applying weights.
    """
    import json as _json

    import numpy as np

    v2ckpt = _v2_checkpoint_module()
    arrays = v2ckpt.torch_state_dict_to_numpy(model.state_dict())
    arrays["__levi_config__"] = np.frombuffer(
        _json.dumps(model.config).encode("utf-8"), dtype=np.uint8
    )
    return v2ckpt.save_checkpoint(
        ckpt_dir,
        step=step,
        arrays=arrays,
        metrics=metrics,
        config_hash=config_hash,
        keep_last=keep_last,
    )


def load_v2_checkpoint(
    path: str | Path, model: LeviBrainV2 | None = None, *, strict: bool = True
) -> dict:
    """Load a harness v2 checkpoint; optionally apply weights to ``model``.

    Verifies the embedded config matches ``model.config`` when a model is
    given (refuses on mismatch instead of silently loading wrong-shaped
    weights). Returns the harness checkpoint dict (step, metrics,
    config_hash, sha256).
    """
    import json as _json

    v2ckpt = _v2_checkpoint_module()
    ckpt = v2ckpt.load_checkpoint(path)
    arrays = dict(ckpt["arrays"])
    raw_cfg = arrays.pop("__levi_config__", None)
    if model is not None:
        if raw_cfg is not None:
            saved_cfg = _json.loads(bytes(raw_cfg).decode("utf-8"))
            arch_keys = (
                "vocab_size",
                "n_layer",
                "n_head",
                "n_kv_head",
                "n_embd",
                "ffn_mult",
                "block_size",
            )
            mismatch = [k for k in arch_keys if saved_cfg.get(k) != model.config.get(k)]
            if mismatch:
                raise ValueError(
                    f"v2 checkpoint architecture mismatch on {mismatch}: "
                    "refusing to load"
                )
        state = v2ckpt.numpy_to_torch_state_dict(arrays, model.state_dict())
        model.load_state_dict(state, strict=strict)
    ckpt["model_config"] = (
        _json.loads(bytes(raw_cfg).decode("utf-8")) if raw_cfg is not None else {}
    )
    return ckpt
