"""Memory-envelope estimator for on-device models. Pure math — no I/O.

Estimates how much RAM a model needs as:

    weights  = params × bytes-per-param(quant)
    kv_cache = 2 × layers × hidden_dim × ctx_tokens × bytes-per-elem
    total    = (weights + kv_cache + headroom) × overhead

Sizes are decimal GB (1 GB = 1e9 bytes), matching how model publishers
quote download sizes. This is an *estimate*, not a measurement: real
runners add allocator overhead, mmap behavior, and per-backend quirks.
"""

from __future__ import annotations

import re

GB = 1_000_000_000

#: Bytes per parameter for each quantization. int4 is 0.5 by definition
#: (4 bits); real GGUF K-quants land within ~15% of these ideals.
BYTES_PER_PARAM = {
    "fp32": 4.0,
    "fp16": 2.0,
    "bf16": 2.0,
    "int8": 1.0,
    "int4": 0.5,
}

#: Approximate (layers, hidden_dim) for common sizes. These are *typical*
#: values for labeling estimates, not exact specs for any one checkpoint.
TYPICAL_ARCH: dict[float, tuple[int, int]] = {
    0.6: (28, 1024),
    1.0: (28, 1536),
    4.0: (36, 2560),
    7.0: (32, 4096),
    8.0: (32, 4096),
    30.0: (48, 6656),
    70.0: (80, 8192),
}

_PARAM_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmbt]?)\s*$", re.IGNORECASE)
_CTX_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([k]?)\s*$", re.IGNORECASE)


def parse_params(text: str | int | float) -> int:
    """Parse '30B', '0.6B', '600M', '3.3M', '1.2T', '500K' (or a number) to a param count."""
    if isinstance(text, (int, float)):
        return int(text)
    m = _PARAM_RE.match(str(text))
    if not m:
        raise ValueError(f"parse_params: cannot parse {text!r} (try '30B', '600M', '3.3M')")
    value, suffix = float(m.group(1)), m.group(2).lower()
    mult = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}[suffix]
    return int(value * mult)


def parse_ctx(text: str | int) -> int:
    """Parse '32k', '4096', '128K' to a token count.

    The 'k' suffix means 1024 — matching how LEVI's own docs write '32k'
    for the 32768-token context window.
    """
    if isinstance(text, int):
        return text
    m = _CTX_RE.match(str(text))
    if not m:
        raise ValueError(f"parse_ctx: cannot parse {text!r} (try '32k', '4096')")
    value, suffix = float(m.group(1)), m.group(2).lower()
    return int(value * (1024 if suffix == "k" else 1))


def weight_bytes(params: int, quant: str = "int4") -> float:
    """Weight memory in bytes for a param count at a quantization."""
    q = quant.lower()
    if q not in BYTES_PER_PARAM:
        raise ValueError(f"weight_bytes: unknown quant {quant!r}; choose from {sorted(BYTES_PER_PARAM)}")
    return params * BYTES_PER_PARAM[q]


def kv_cache_bytes(
    layers: int,
    hidden_dim: int,
    ctx_tokens: int,
    bytes_per_elem: float = 2.0,
) -> float:
    """KV-cache bytes: 2 (K and V) × layers × hidden × ctx × bytes/elem.

    The factor of 2 counts the K and V tensors. GQA/MQA shrink the *effective*
    KV heads in real checkpoints; this formula uses the dense upper bound,
    which is the honest choice for capacity planning.
    """
    if layers <= 0 or hidden_dim <= 0 or ctx_tokens <= 0:
        raise ValueError("kv_cache_bytes: layers, hidden_dim, ctx_tokens must be positive")
    return 2.0 * layers * hidden_dim * ctx_tokens * bytes_per_elem


def typical_arch(params: int) -> tuple[int, int] | None:
    """Nearest typical (layers, hidden_dim) for a param count, or None."""
    b = params / 1e9
    key = min(TYPICAL_ARCH, key=lambda k: abs(k - b))
    # Only claim "typical" within 25% of a table entry.
    if abs(key - b) / key > 0.25:
        return None
    return TYPICAL_ARCH[key]


def footprint(
    params: str | int | float,
    quant: str = "int4",
    ctx: str | int = "32k",
    *,
    layers: int | None = None,
    hidden_dim: int | None = None,
    headroom_gb: float = 1.0,
    overhead: float = 1.15,
) -> dict:
    """Estimate the RAM envelope for running a model.

    Args:
        params: parameter count ('30B', '0.6B', 600_000_000 …).
        quant: one of fp32/fp16/bf16/int8/int4.
        ctx: context window ('32k', 4096 …).
        layers/hidden_dim: transformer shape for the KV cache. When omitted,
            a *typical* shape is used and flagged as estimated.
        headroom_gb: flat GB for vision encoders, drafters, OS, etc.
        overhead: multiplier for allocator/runtime overhead (default 1.15).

    Returns a dict with weights_gb, kv_cache_gb, headroom_gb, total_gb,
    and the arch used (with ``arch_estimated`` True when guessed).
    """
    n_params = parse_params(params)
    n_ctx = parse_ctx(ctx)
    arch_estimated = False
    if layers is None or hidden_dim is None:
        guess = typical_arch(n_params)
        if guess is None:
            raise ValueError(
                "footprint: no typical arch for this size — pass layers and hidden_dim"
            )
        layers, hidden_dim = guess
        arch_estimated = True
    weights_gb = weight_bytes(n_params, quant) / GB
    kv_gb = kv_cache_bytes(layers, hidden_dim, n_ctx) / GB
    total_gb = (weights_gb + kv_gb + headroom_gb) * overhead
    return {
        "params": n_params,
        "quant": quant.lower(),
        "ctx_tokens": n_ctx,
        "layers": layers,
        "hidden_dim": hidden_dim,
        "arch_estimated": arch_estimated,
        "weights_gb": round(weights_gb, 3),
        "kv_cache_gb": round(kv_gb, 3),
        "headroom_gb": round(headroom_gb, 3),
        "overhead": overhead,
        "total_gb": round(total_gb, 3),
        "note": "Estimate, not a measurement. Real runners vary by backend.",
    }


def format_footprint(fp: dict) -> str:
    """Human-readable rendering of :func:`footprint`."""
    arch = f"{fp['layers']} layers × {fp['hidden_dim']} hidden"
    if fp["arch_estimated"]:
        arch += " (typical — estimated)"
    lines = [
        f"Model footprint: {fp['params']:,} params @ {fp['quant']}, ctx {fp['ctx_tokens']:,}",
        f"  weights : {fp['weights_gb']:.3f} GB",
        f"  KV cache: {fp['kv_cache_gb']:.3f} GB  [{arch}]",
        f"  headroom: {fp['headroom_gb']:.3f} GB (×{fp['overhead']} overhead)",
        "  ─────────────────────────────",
        f"  total   : {fp['total_gb']:.3f} GB  ← estimate, not a measurement",
    ]
    return "\n".join(lines)
