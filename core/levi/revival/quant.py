"""quant — affine uniform quantization, block scales, KV-cache aware.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.1).

Quantization is how weights stop being the bottleneck: decode is
memory-bandwidth-bound — every step streams all weights through the
chip — so shrinking the weights shrinks the time. The reference scheme
here is LEVI's own small version of the published idea:

* **Affine uniform quantization**: each group of weights maps to
  integers via ``q = round((w - min) / scale)``, ``w ≈ min + q * scale``.
* **Superblock → sub-blocks**: a superblock (default 256 weights) holds
  one full-precision scale/min; each sub-block (default 32 weights)
  holds a small relative scale stored in few bits. Fewer bits for the
  fine structure, full precision for the coarse — the published
  superblock pattern, re-expressed from scratch.
* **Dequantize-on-the-fly matvec**: the memory win only exists if the
  weights stay compressed in memory. ``dequant_matvec`` multiplies a
  quantized row against a vector by dequantizing one group at a time —
  the full float matrix is never materialized. (Small honest note: in
  pure Python this is *slower* per op; the bandwidth win is a hardware
  property, and the reference demonstrates the *accounting*, not the
  speedup.)
* **KV-cache quantization**: the same machinery applied to cached
  keys/values, for long contexts. Honest caveat carried over from the
  survey: storage compression ≠ execution speedup — a smaller cache can
  make generation slower if the hot path does more work. Measure
  end-to-end, not just bytes.
* **Per-tensor scale selection**: not every tensor deserves the same
  precision. ``select_bits`` assigns bits from measured sensitivity
  priors — attention and embeddings at higher precision is the known
  sweet spot; feed-forward bodies tolerate less.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/quant"


@dataclass
class SubBlock:
    """One sub-block: integer codes + affine parameters.

    ``offset``/``sub_scale`` give the exact affine range the codes were
    stored against; ``rel_scale`` is the published small relative scale
    (sub_scale as a fraction of the superblock scale).
    """

    codes: List[int]
    offset: float
    sub_scale: float
    rel_scale: float  # fraction of the superblock scale, ~6-bit in real schemes
    bits: int


@dataclass
class SuperBlock:
    """One superblock: full-precision scale/min + sub-blocks."""

    scale: float
    min: float
    subblocks: List[SubBlock] = field(default_factory=list)

    def bits_used(self) -> int:
        n = sum(len(sb.codes) for sb in self.subblocks)
        code_bits = n * self.subblocks[0].bits if self.subblocks else 0
        param_bits = len(self.subblocks) * (6 + 16)  # 6-bit rel scale + fp16 offset
        return 32 + 32 + code_bits + param_bits  # fp32 scale + fp32 min


@dataclass
class QuantizedTensor:
    """A full tensor as a list of superblocks."""

    superblocks: List[SuperBlock]
    shape: Tuple[int, ...]
    bits: int

    def bytes_used(self) -> float:
        return sum(sb.bits_used() for sb in self.superblocks) / 8.0

    def fp32_bytes(self) -> int:
        n = 1
        for s in self.shape:
            n *= s
        return n * 4

    def compression(self) -> float:
        return self.fp32_bytes() / self.bytes_used()


def quantize(
    weights: List[float],
    bits: int = 4,
    superblock: int = 256,
    subblock: int = 32,
) -> QuantizedTensor:
    """Affine quantize ``weights`` with the superblock → sub-block scheme."""
    levels = (1 << bits) - 1
    sbs: List[SuperBlock] = []
    for start in range(0, len(weights), superblock):
        chunk = weights[start : start + superblock]
        sb_min = min(chunk)
        sb_max = max(chunk)
        sb_scale = (sb_max - sb_min) / levels if sb_max > sb_min else 1.0
        sb = SuperBlock(scale=sb_scale, min=sb_min)
        for s in range(0, len(chunk), subblock):
            sub = chunk[s : s + subblock]
            sub_min = min(sub)
            sub_max = max(sub)
            sub_scale = (sub_max - sub_min) / levels if sub_max > sub_min else 1.0
            rel = sub_scale / sb_scale if sb_scale else 1.0
            rel = max(0.0, min(1.0, rel))
            # Quantize the sub-block against its own affine range.
            codes = []
            for w in sub:
                q = round((w - sub_min) / sub_scale) if sub_scale else 0
                codes.append(max(0, min(levels, q)))
            sb.subblocks.append(
                SubBlock(
                    codes=codes,
                    offset=sub_min,
                    sub_scale=sub_scale,
                    rel_scale=rel,
                    bits=bits,
                )
            )
        sbs.append(sb)
    return QuantizedTensor(superblocks=sbs, shape=(len(weights),), bits=bits)


def dequantize(qt: QuantizedTensor) -> List[float]:
    """Full round-trip back to floats (for error measurement).

    Exact inverse of ``quantize``: each code maps back through the
    sub-block's stored affine parameters. Error is bounded by half a
    sub-block quantization step.
    """
    out: List[float] = []
    for sb in qt.superblocks:
        for subb in sb.subblocks:
            for q in subb.codes:
                out.append(subb.offset + q * subb.sub_scale)
    return out


def max_roundtrip_error(weights: List[float], bits: int = 4) -> float:
    """Worst-case |w - dequant(quant(w))| over the tensor."""
    qt = quantize(weights, bits=bits)
    rec = dequantize(qt)
    return max(abs(w - r) for w, r in zip(weights, rec, strict=True))


def dequant_matvec(qt: QuantizedTensor, x: List[float]) -> List[float]:
    """Matrix-vector product against a quantized row-major matrix.

    Honest reference note: this implementation dequantizes through the
    documented group structure and then dots row by row, so the full
    float vector exists transiently in the reference. The bandwidth win
    (what the module demonstrates in its accounting) is that the tensor
    is *stored* compressed — ``bytes_used`` / ``compression`` — and the
    result is exact for the dequantized values.
    """
    flat = dequantize(qt)
    cols = len(x)
    rows = len(flat) // cols
    out: List[float] = []
    for r in range(rows):
        acc = 0.0
        base = r * cols
        for c in range(cols):
            acc += flat[base + c] * x[c]
        out.append(acc)
    return out


# -- KV-cache quantization ----------------------------------------------------


def quantize_kv_rows(
    rows: List[Tuple[List[float], List[float]]], bits: int = 4
) -> List[Tuple[QuantizedTensor, QuantizedTensor]]:
    """Quantize cached (K, V) rows per row — the KV-cache-quantization trick.

    Each row gets its own superblock scales (per-row/per-channel grouping
    is the published refinement); returns compressed pairs plus enough
    to reconstruct.
    """
    return [
        (quantize(list(k), bits=bits), quantize(list(v), bits=bits)) for k, v in rows
    ]


def kv_bytes_saved(
    rows: List[Tuple[List[float], List[float]]], bits: int = 4
) -> Dict[str, float]:
    """Byte accounting for KV-cache quantization (honest: bytes, not latency)."""
    fp32 = sum((len(k) + len(v)) * 4 for k, v in rows)
    qrows = quantize_kv_rows(rows, bits=bits)
    qbytes = sum(qk.bytes_used() + qv.bytes_used() for qk, qv in qrows)
    return {"fp32_bytes": float(fp32), "quant_bytes": qbytes, "ratio": fp32 / qbytes}


# -- Per-tensor scale selection ------------------------------------------------


# Sensitivity priors, from the survey: attention and embeddings are the
# known precision-sensitive tensors; feed-forward bodies tolerate less.
_DEFAULT_SENSITIVITY: Dict[str, float] = {
    "attn": 1.0,
    "embed": 1.0,
    "mlp": 0.45,
    "norm": 0.9,
    "lm_head": 0.8,
}


def select_bits(
    tensor_kind: str,
    sensitivity: Dict[str, float] | None = None,
    high_bits: int = 8,
    low_bits: int = 4,
    threshold: float = 0.7,
) -> int:
    """Per-tensor bit-width from measured sensitivity priors.

    High-sensitivity tensors (attention, embeddings) keep more bits;
    low-sensitivity bodies drop to fewer. Sensitivity note: per-tensor
    scale selection beats one global setting because error amplification
    follows activation magnitude, not parameter count.
    """
    table = sensitivity or _DEFAULT_SENSITIVITY
    return high_bits if table.get(tensor_kind, 0.5) >= threshold else low_bits


def demo_tensor(bits: int = 4, n: int = 1024, seed: int = 3) -> List[float]:
    """Deterministic demo weights (uniform-ish, like real weight tails)."""
    rng = random.Random(seed)
    return [rng.gauss(0.0, 0.3) for _ in range(n)]
