"""Task-vector merging: combine fine-tuned skills in weight space, zero training.

Studied from: ai-si-software-internals-20260916-0005/report.md (section 2.9)

A task vector is the difference a fine-tune made:

    tau = theta_finetuned - theta_base        (same base required)

The discovery: fine-tuned skills compose in weight space. Merging is a
zero-training way to combine capabilities — no gradients, no data, just
arithmetic on the deltas.

Four methods, each with its documented property:

- linear: weighted average of task vectors (model soups). Simple,
  surprisingly strong; the baseline everything else is measured against.
- slerp: spherical interpolation, per vector pair. theta_t =
  sin((1-t)Omega)/sin(Omega) * A + sin(t Omega)/sin(Omega) * B, where
  Omega is the angle between them. Property: preserves norm — the merged
  vector rides the sphere between the two, never dips through the middle.
- ties: trim low-magnitude deltas + elect the majority sign per parameter
  + merge the sign-agreeing mean. Property: conflicting directions
  resolve by majority vote instead of canceling out.
- dare: randomly drop a fraction p of delta params, rescale survivors by
  1/(1-p). Property: robust to high drop rates (reported 90%) — the
  expected delta is unchanged by the dropout.

Pure-Python reference on toy vectors. The operations are per-parameter,
so they lift directly to real weight tensors.
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence

ORIGIN = "levi-revival/taskvec"

Vector = List[float]


def _check(a: Sequence[float], b: Sequence[float]) -> None:
    if len(a) != len(b):
        raise ValueError("vector length mismatch")


def task_vector(finetuned: Vector, base: Vector) -> Vector:
    """tau = theta_finetuned - theta_base."""
    _check(finetuned, base)
    return [f - b for f, b in zip(finetuned, base, strict=True)]


def apply(base: Vector, tau: Vector) -> Vector:
    """theta = base + tau."""
    _check(base, tau)
    return [b + t for b, t in zip(base, tau, strict=True)]


def norm(v: Vector) -> float:
    return math.sqrt(sum(x * x for x in v))


def merge_linear(tau_list: List[Vector], weights: List[float]) -> Vector:
    """Weighted average of task vectors (model soups)."""
    if len(tau_list) != len(weights):
        raise ValueError("need one weight per task vector")
    if not tau_list:
        raise ValueError("nothing to merge")
    total = sum(weights)
    if total == 0:
        raise ValueError("weights sum to zero")
    dim = len(tau_list[0])
    for tau in tau_list:
        if len(tau) != dim:
            raise ValueError("vector length mismatch")
    return [
        sum(w * tau[i] for w, tau in zip(weights, tau_list, strict=True)) / total
        for i in range(dim)
    ]


def slerp(a: Vector, b: Vector, t: float) -> Vector:
    """Spherical interpolation between a and b at fraction t in [0, 1].

    Rides the great-circle arc between the vectors, so the result keeps
    the (interpolated) norm instead of shrinking through the middle the
    way a naive linear blend does. Falls back to linear interpolation for
    degenerate cases (zero or parallel vectors), where the angle is
    undefined.
    """
    _check(a, b)
    na, nb = norm(a), norm(b)
    if na == 0.0 or nb == 0.0:
        return [(1 - t) * x + t * y for x, y in zip(a, b, strict=True)]
    cos_omega = sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)
    cos_omega = max(-1.0, min(1.0, cos_omega))
    omega = math.acos(cos_omega)
    if omega < 1e-9:  # parallel: nothing spherical to do
        return [(1 - t) * x + t * y for x, y in zip(a, b, strict=True)]
    sin_omega = math.sin(omega)
    wa = math.sin((1 - t) * omega) / sin_omega
    wb = math.sin(t * omega) / sin_omega
    return [wa * x + wb * y for x, y in zip(a, b, strict=True)]


def ties_merge(tau_list: List[Vector], keep_frac: float = 0.2) -> Vector:
    """TIES: trim + elect + merge.

    1. Trim: per vector, zero out everything but the top-keep_frac
       magnitudes (keep the deltas that mattered).
    2. Elect: per parameter, the majority sign across vectors wins.
    3. Merge: average only the vectors that agree with the elected sign.

    Conflicting updates resolve by vote instead of canceling to mush.
    """
    if not tau_list:
        raise ValueError("nothing to merge")
    if not 0 < keep_frac <= 1.0:
        raise ValueError("keep_frac must be in (0, 1]")
    dim = len(tau_list[0])
    for tau in tau_list:
        if len(tau) != dim:
            raise ValueError("vector length mismatch")

    # Trim: keep the largest-magnitude entries per vector.
    trimmed: List[Vector] = []
    for tau in tau_list:
        order = sorted(range(dim), key=lambda i: abs(tau[i]), reverse=True)
        keep = max(1, int(dim * keep_frac))
        kept = set(order[:keep])
        trimmed.append([tau[i] if i in kept else 0.0 for i in range(dim)])

    # Elect + merge.
    merged = []
    for i in range(dim):
        votes = [tau[i] for tau in trimmed if tau[i] != 0.0]
        if not votes:
            merged.append(0.0)
            continue
        pos = sum(1 for v in votes if v > 0)
        neg = sum(1 for v in votes if v < 0)
        sign = 1.0 if pos >= neg else -1.0
        agreeing = [v for v in votes if (v > 0) == (sign > 0)]
        merged.append(sum(agreeing) / len(agreeing))
    return merged


def dare_merge(tau_list: List[Vector], drop_p: float, seed: int = 0) -> Vector:
    """DARE: randomly drop fraction p of delta params, rescale by 1/(1-p).

    Each vector is independently sparsified; survivors are rescaled so the
    expected delta is unchanged. Reported robust to very high drop rates;
    the survivors are then averaged. drop_p=0 is the identity.
    """
    if not tau_list:
        raise ValueError("nothing to merge")
    if not 0.0 <= drop_p < 1.0:
        raise ValueError("drop_p must be in [0, 1)")
    dim = len(tau_list[0])
    for tau in tau_list:
        if len(tau) != dim:
            raise ValueError("vector length mismatch")
    rng = random.Random(seed)
    scale = 1.0 / (1.0 - drop_p) if drop_p > 0 else 1.0
    sparsified = []
    for tau in tau_list:
        sparsified.append([0.0 if rng.random() < drop_p else v * scale for v in tau])
    n = len(sparsified)
    return [sum(s[i] for s in sparsified) / n for i in range(dim)]


def merge_taus(
    base: Vector,
    taus: List[Vector],
    method: str = "linear",
    **kwargs,
) -> Vector:
    """Merge task vectors onto a base with the named method."""
    if method == "linear":
        weights = kwargs.get("weights", [1.0] * len(taus))
        tau = merge_linear(taus, list(weights))
    elif method == "slerp":
        if len(taus) != 2:
            raise ValueError("slerp merges exactly two vectors")
        tau = slerp(taus[0], taus[1], kwargs.get("t", 0.5))
    elif method == "ties":
        tau = ties_merge(taus, kwargs.get("keep_frac", 0.2))
    elif method == "dare":
        tau = dare_merge(taus, kwargs.get("drop_p", 0.5), kwargs.get("seed", 0))
    else:
        raise ValueError(f"unknown method: {method}")
    return apply(base, tau)


def demo() -> str:
    base = [1.0, 2.0, 3.0, 4.0]
    skill_a = [1.5, 1.0, 3.2, 4.1]  # learned: push dim0 up, dim1 down
    skill_b = [0.8, 2.4, 2.6, 4.0]  # learned: push dim0 down, dim1 up
    tau_a = task_vector(skill_a, base)
    tau_b = task_vector(skill_b, base)

    lin = merge_taus(base, [tau_a, tau_b], "linear", weights=[0.5, 0.5])
    sl = merge_taus(base, [tau_a, tau_b], "slerp", t=0.5)
    ti = merge_taus(base, [tau_a, tau_b], "ties", keep_frac=0.5)
    da = merge_taus(base, [tau_a, tau_b], "dare", drop_p=0.5, seed=7)

    mid_norm = norm([(x + y) / 2 for x, y in zip(tau_a, tau_b, strict=True)])
    lines = [
        f"linear: {[round(v, 3) for v in lin]}",
        f"slerp:  {[round(v, 3) for v in sl]} (tau norm={norm(task_vector(sl, base)):.3f} vs linear-blend norm={mid_norm:.3f})",
        f"ties:   {[round(v, 3) for v in ti]}",
        f"dare:   {[round(v, 3) for v in da]}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(demo())
