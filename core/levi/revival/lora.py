"""LoRA mechanics as a pure-Python reference: freeze the base, learn a whisper.

Studied from: ai-si-software-internals-20260916-0005/report.md (section 2.9)

LoRA (low-rank adaptation): freeze the base weight W0 and learn only a
low-rank delta Delta-W = B @ A, with A (r x d_in) randomly initialized
and B (d_out x r) zero-initialized — so training starts as the identity
(the adapter contributes nothing on step zero). Forward:

    h = W0 @ x + (B @ (A @ x)) * (alpha / r)

Merging is free: W = W0 + (alpha/r) * B @ A gives zero inference latency.
Rank r is typically 4-32 (start small); alpha ~= 2r is the rule of thumb.
The premise: fine-tuning has low intrinsic dimension, so a rank-r update
captures what matters.

Deployment story: one frozen base, many tiny swappable adapters. This
module is that story on toy matrices — no frameworks, no accelerators,
just lists of floats, so every operation is visible.

Shapes: W0 is d_out x d_in; x is a length-d_in vector; h is length-d_out.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional

ORIGIN = "levi-revival/lora"

Matrix = List[List[float]]
Vector = List[float]

TYPICAL_RANK_MIN = 4
TYPICAL_RANK_MAX = 32


def matmul(A: Matrix, B: Matrix) -> Matrix:
    """Matrix product of A (m x n) and B (n x p)."""
    m, n = len(A), len(A[0])
    p = len(B[0])
    if len(B) != n:
        raise ValueError(f"shape mismatch: {m}x{n} @ {len(B)}x{p}")
    return [
        [sum(A[i][k] * B[k][j] for k in range(n)) for j in range(p)] for i in range(m)
    ]


def matvec(A: Matrix, x: Vector) -> Vector:
    """A (m x n) times vector x (n)."""
    if len(x) != len(A[0]):
        raise ValueError("shape mismatch in matvec")
    return [sum(row[k] * x[k] for k in range(len(x))) for row in A]


def add(A: Matrix, B: Matrix) -> Matrix:
    return [
        [a + b for a, b in zip(ra, rb, strict=True)]
        for ra, rb in zip(A, B, strict=True)
    ]


def scale(A: Matrix, s: float) -> Matrix:
    return [[a * s for a in row] for row in A]


def zeros(rows: int, cols: int) -> Matrix:
    return [[0.0] * cols for _ in range(rows)]


class LoRAAdapter:
    """A low-rank delta: Delta-W = B @ A, with B zero-initialized.

    ``train_step`` is a deliberately simple gradient-free stand-in: it
    nudges B in the direction of the residual (target - current output)
    outer-producted with the A-projected input. It exists so the reference
    can show B moving away from zero and the delta becoming non-trivial —
    it is a teaching aid, not an optimizer.
    """

    def __init__(
        self,
        d_in: int,
        d_out: int,
        rank: int = 8,
        alpha: Optional[float] = None,
        seed: int = 0,
    ) -> None:
        if rank < 1:
            raise ValueError("rank must be >= 1")
        if not (TYPICAL_RANK_MIN <= rank <= TYPICAL_RANK_MAX):
            # Honest, not a refusal: the literature's range is advice,
            # the mechanism works anywhere.
            pass
        self.d_in = d_in
        self.d_out = d_out
        self.rank = rank
        self.alpha = float(alpha) if alpha is not None else 2.0 * rank
        rng = random.Random(seed)
        scale_a = 1.0 / math.sqrt(d_in)
        # A: random init (r x d_in). B: zero init (d_out x r).
        self.A: Matrix = [
            [rng.uniform(-scale_a, scale_a) for _ in range(d_in)] for _ in range(rank)
        ]
        self.B: Matrix = zeros(d_out, rank)

    @property
    def scaling(self) -> float:
        return self.alpha / self.rank

    def delta(self) -> Matrix:
        """The learned update Delta-W = (alpha/r) * B @ A."""
        return scale(matmul(self.B, self.A), self.scaling)

    def apply(self, x: Vector) -> Vector:
        """Adapter-only contribution: (B @ (A @ x)) * (alpha/r)."""
        return [v * self.scaling for v in matvec(self.B, matvec(self.A, x))]

    def is_identity(self) -> bool:
        """True while B is still all zeros — the adapter changes nothing."""
        return all(v == 0.0 for row in self.B for v in row)

    def train_step(self, x: Vector, residual: Vector, lr: float = 0.01) -> None:
        """Nudge B so the adapter output moves toward ``residual``.

        residual = desired_output - current_output. Teaching aid only.
        """
        ax = matvec(self.A, x)  # length r
        for i in range(self.d_out):
            for k in range(self.rank):
                self.B[i][k] += lr * residual[i] * ax[k] * self.scaling

    def param_count(self) -> int:
        return self.rank * (self.d_in + self.d_out)

    def summary(self) -> str:
        return (
            f"LoRA(r={self.rank}, alpha={self.alpha:g}, "
            f"params={self.param_count()}, identity={self.is_identity()})"
        )


class LoRALinear:
    """A frozen base weight with one hot-swappable adapter slot.

    The base never moves. Adapters come and go; merging is free.
    """

    def __init__(self, W0: Matrix) -> None:
        self.W0 = [row[:] for row in W0]
        self.d_out = len(W0)
        self.d_in = len(W0[0])
        self.adapter: Optional[LoRAAdapter] = None

    def attach(self, adapter: LoRAAdapter) -> None:
        if (adapter.d_in, adapter.d_out) != (self.d_in, self.d_out):
            raise ValueError("adapter shape does not match base")
        self.adapter = adapter

    def detach(self) -> Optional[LoRAAdapter]:
        old, self.adapter = self.adapter, None
        return old

    def forward(self, x: Vector) -> Vector:
        out = matvec(self.W0, x)
        if self.adapter is not None:
            delta = self.adapter.apply(x)
            out = [o + d for o, d in zip(out, delta, strict=True)]
        return out

    def merged_weights(self) -> Matrix:
        """W = W0 + (alpha/r) B A — merge the current adapter for free."""
        if self.adapter is None:
            return [row[:] for row in self.W0]
        return add(self.W0, self.adapter.delta())

    def base_param_count(self) -> int:
        return self.d_in * self.d_out


def demo() -> str:
    # Toy 3x2 base, two "skills" as adapters.
    W0 = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    layer = LoRALinear(W0)
    x = [1.0, 2.0]
    base_out = layer.forward(x)

    terse = LoRAAdapter(2, 3, rank=4, seed=1)
    for _ in range(50):
        out = [b + d for b, d in zip(base_out, terse.apply(x), strict=True)]
        terse.train_step(x, [r - o for r, o in zip([3.0, 3.0, 3.0], out, strict=True)])
    layer.attach(terse)
    adapted = layer.forward(x)
    layer.detach()
    plain = layer.forward(x)
    merged = layer.merged_weights()
    # merged weights must reproduce the adapted forward exactly
    check = matvec(merged, x)
    lines = [
        f"base output:    {[round(v, 3) for v in base_out]}",
        f"adapted output: {[round(v, 3) for v in adapted]}",
        f"detached again: {[round(v, 3) for v in plain]}",
        f"merged == adapted: {all(abs(a - b) < 1e-9 for a, b in zip(check, adapted, strict=True))}",
        f"base params={layer.base_param_count()} adapter params={terse.param_count()}",
        terse.summary(),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(demo())
