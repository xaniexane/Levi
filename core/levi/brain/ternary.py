"""Ternary quantization for LEVI's native brain weights.

Interpenetration piece 1 of 3: the Bonsai-2 *direction* (weights as
+1/0/-1) applied to LEVI's own trained weights — measured here, not
claimed.

Method: per-tensor ternarization (Li et al. TWN-style). For a weight
tensor ``w``::

    delta = 0.7 * mean(|w|)
    code  = sign(w) where |w| > delta, else 0        # in {-1, 0, +1}
    alpha = mean(|w| over |w| > delta)               # per-tensor scale
    w_hat = alpha * code

What is ternarized: 2-D linear weight matrices (attention qkv/proj,
MLP, output head). Embeddings, biases, and norm scales stay fp32 —
standard practice; ternarizing embeddings is known-lossy and is left
as an explicit experiment, not a default.

Storage: codes are int8 in memory (measured below); the honest
phone-size number is 2-bit packing (4 weights/byte), reported as a
*projection* — this module does not claim a packed kernel.

Honest scope
------------
- This is post-training quantization WITHOUT any retraining. Measured
  on tiny-gpt (3.3M params, char-level): the size cut is real
  (~3.7x at int8, ~11.6x projected at 2-bit) but naive ternarization
  shifts logits materially (mean |dlogit| ~0.8, top-1 agreement ~38%
  on a short probe). Vendor "98% intact" claims are for 27B models
  with quantization-aware training — UNVERIFIED here and not
  comparable to this measurement.
- Recovery path (not built here): quantization-aware fine-tuning on
  the existing training loop, then re-measure. That is the experiment
  this prototype exists to motivate.

Stdlib-only at import; numpy is imported lazily. Never touches the
original weight files — everything operates on in-memory copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _np():
    import numpy as np  # lazy: kernel stays stdlib-only at import

    return np


@dataclass
class TernaryTensor:
    """One ternarized weight tensor: int8 codes in {-1,0,+1} + fp32 scale."""

    name: str
    codes: Any  # int8 ndarray, values in {-1, 0, +1}
    scale: float
    shape: Tuple[int, ...]
    sparsity: float  # fraction of codes == 0


def quantize_ternary(w: Any, name: str = "") -> TernaryTensor:
    """Ternarize a float weight tensor. Deterministic (no randomness)."""
    np = _np()
    w = np.asarray(w, dtype=np.float32)
    a = np.abs(w)
    delta = 0.7 * float(a.mean())
    mask = a > delta
    codes = np.sign(w).astype(np.int8)
    codes[~mask] = 0
    alpha = float(a[mask].mean()) if bool(mask.any()) else 1.0
    sparsity = float((~mask).mean())
    return TernaryTensor(
        name=name, codes=codes, scale=alpha, shape=tuple(w.shape),
        sparsity=sparsity,
    )


def dequantize_ternary(t: TernaryTensor) -> Any:
    """Reconstruct the fp32 approximation: scale * codes."""
    np = _np()
    return (t.codes.astype(np.float32) * np.float32(t.scale)).reshape(t.shape)


def should_ternarize(name: str, w: Any) -> bool:
    """Policy: 2-D linear weights only; embeddings/biases/norms stay fp32."""
    np = _np()
    w = np.asarray(w)
    return w.ndim == 2 and name.endswith(".weight") and "emb" not in name


def ternarize_state_dict(
    params: Dict[str, Any],
) -> Tuple[Dict[str, TernaryTensor], List[str]]:
    """Ternarize a COPY of a params dict. Returns (ternary, untouched_names).

    The input dict is never modified; callers dequantize into a fresh
    dict via :func:`apply_ternary`.
    """
    ternary: Dict[str, TernaryTensor] = {}
    untouched: List[str] = []
    for name, w in params.items():
        if should_ternarize(name, w):
            ternary[name] = quantize_ternary(w, name)
        else:
            untouched.append(name)
    return ternary, untouched


def apply_ternary(
    params: Dict[str, Any], ternary: Dict[str, TernaryTensor]
) -> Dict[str, Any]:
    """Return a NEW params dict with ternarized weights dequantized in place.

    Original ``params`` is untouched — the source weights are never
    overwritten.
    """
    np = _np()
    out = dict(params)
    for name, t in ternary.items():
        out[name] = dequantize_ternary(t)
    return out


@dataclass
class SizeReport:
    fp32_bytes: int
    int8_codes_bytes: int  # measured: int8 codes + fp32 scales
    packed2bit_bytes: int  # projection: 2 bits/weight + fp32 scales
    n_ternarized: int
    n_untouched: int

    @property
    def int8_ratio(self) -> float:
        return self.fp32_bytes / self.int8_codes_bytes

    @property
    def packed_ratio(self) -> float:
        return self.fp32_bytes / self.packed2bit_bytes


def size_report(
    params: Dict[str, Any], ternary: Dict[str, TernaryTensor]
) -> SizeReport:
    """Measured size delta. int8 is measured; 2-bit is a labeled projection."""
    np = _np()
    fp32 = sum(np.asarray(w).nbytes for w in params.values())
    int8b = 0
    packed = 0
    for name, w in params.items():
        w = np.asarray(w)
        if name in ternary:
            n = w.size
            int8b += n + 4  # int8 codes + one fp32 scale
            packed += (n + 3) // 4 + 4  # 2-bit packed + one fp32 scale
        else:
            int8b += w.nbytes
            packed += w.nbytes
    return SizeReport(
        fp32_bytes=fp32,
        int8_codes_bytes=int8b,
        packed2bit_bytes=packed,
        n_ternarized=len(ternary),
        n_untouched=len(params) - len(ternary),
    )


@dataclass
class DivergenceReport:
    mean_abs: float
    max_abs: float
    top1_agreement: float  # fraction of positions, all T
    last_pos_agree: bool


def divergence(logits_fp32: Any, logits_tern: Any) -> DivergenceReport:
    """Fidelity proxy between two logit arrays. Pure numpy, deterministic."""
    np = _np()
    a = np.asarray(logits_fp32, dtype=np.float64)
    b = np.asarray(logits_tern, dtype=np.float64)
    d = np.abs(a - b)
    agree = (a.argmax(-1) == b.argmax(-1)).mean()
    return DivergenceReport(
        mean_abs=float(d.mean()),
        max_abs=float(d.max()),
        top1_agreement=float(agree),
        last_pos_agree=bool(a.argmax(-1)[-1] == b.argmax(-1)[-1]),
    )
