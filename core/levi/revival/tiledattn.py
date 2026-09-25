"""tiledattn — exact attention by tiling with online softmax.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.1).

The FlashAttention idea, expressed at reference scale: standard
attention materializes the whole n×n score matrix before the softmax,
which is the memory wall that makes long-context prefill painful.
Tiled attention never builds that matrix. It streams K and V through in
blocks and keeps a *running* softmax — the online softmax recurrence
(Milakov & Gimelshein) — so the output after the last block is exactly
the same as the naive version, up to floating-point order.

Concretely, for each query row we keep a running maximum ``m`` and a
running normalizer ``norm`` plus a running output accumulator. For each
K/V block we compute the block's scores, take the block max, rescale
the accumulator by the ratio of old/new normalizers, and fold the block
in. The rescaling is the whole trick: it corrects for the fact that we
didn't know the global max when we started.

Pure Python, lists of floats. ``tiled_attention`` must agree with
``naive_attention`` — that equivalence is the entire point, and the
test suite pins it down.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
from typing import List

ORIGIN = "levi-revival/tiledattn"


def _row_dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def naive_attention(
    q: List[List[float]], k: List[List[float]], v: List[List[float]]
) -> List[List[float]]:
    """Reference attention: full n×n score matrix, then softmax."""
    scale = 1.0 / math.sqrt(len(q[0]))
    out: List[List[float]] = []
    for qi in q:
        scores = [_row_dot(qi, kj) * scale for kj in k]
        m = max(scores)
        exps = [math.exp(s - m) for s in scores]
        total = sum(exps)
        weights = [e / total for e in exps]
        dim = len(v[0])
        row = [0.0] * dim
        for w, vj in zip(weights, v, strict=True):
            for d in range(dim):
                row[d] += w * vj[d]
        out.append(row)
    return out


def tiled_attention(
    q: List[List[float]],
    k: List[List[float]],
    v: List[List[float]],
    tile: int = 4,
) -> List[List[float]]:
    """Exact attention via tiling + online softmax.

    ``tile`` is the K/V block size. Memory touched at once is
    O(tile × d) per query row instead of O(n × d) — the n×n matrix never
    exists.
    """
    n = len(k)
    dim = len(v[0])
    scale = 1.0 / math.sqrt(len(q[0]))
    out: List[List[float]] = []
    for qi in q:
        m = float("-inf")  # running row max
        norm = 0.0  # running normalizer sum
        acc = [0.0] * dim  # running output accumulator
        for start in range(0, n, tile):
            kb = k[start : start + tile]
            vb = v[start : start + tile]
            scores = [_row_dot(qi, kj) * scale for kj in kb]
            block_max = max(scores)
            # New running max and how much the old accumulator must shrink.
            m_new = max(m, block_max)
            rescale = math.exp(m - m_new) if m != float("-inf") else 0.0
            norm = norm * rescale
            acc = [a * rescale for a in acc]
            # Fold the block in under the new max.
            block_exps = [math.exp(s - m_new) for s in scores]
            norm += sum(block_exps)
            for e, vj in zip(block_exps, vb, strict=True):
                for d in range(dim):
                    acc[d] += e * vj[d]
            m = m_new
        out.append([a / norm for a in acc])
    return out


def max_abs_diff(a: List[List[float]], b: List[List[float]]) -> float:
    """Largest absolute element-wise difference between two matrices."""
    return max(
        abs(x - y)
        for ra, rb in zip(a, b, strict=True)
        for x, y in zip(ra, rb, strict=True)
    )


def attention_flops_saved(n: int, d: int, tile: int) -> dict:
    """Back-of-envelope memory accounting for the tiling win.

    Naive holds n×n scores (floats); tiled holds tile×d per row pass.
    Returns element counts, not bytes — the ratio is what matters.
    """
    return {
        "naive_score_elements": n * n,
        "tiled_working_elements": tile * d,
        "ratio": (n * n) / max(1, tile * d),
    }
