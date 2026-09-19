"""LEVI's delta sweep: the two-phase learning pass, from scratch.

Studied from: ai-si (§1.9) — the two-phase sweep (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: learning is a sweep with two phases.
**Phase one**, the forward sweep: activations flow through the layers and
the network ventures a guess. **Phase two**, the backward sweep: the error
flows back through the chain rule, and every weight takes a step downhill
— ``w -= η · ∂E/∂w``. Do that thousands of times on a toy problem and a
lump of random numbers learns XOR.

The network is layer arrays and one 3-D weight array
``W[layer][to][from]`` plus per-layer biases — pure Python lists, no
numpy, no network, CPU only.

Honesty: LOAD-BEARING. This is reference-scale on purpose: a 2-4-1
network, a seeded RNG, a few thousand epochs on XOR. It demonstrates the
mechanism faithfully — forward pass, error-derivative propagation via
the chain rule, gradient descent — at a scale where you can watch every
number move. It is not a training framework.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

ORIGIN = "levi-revival/deltasweep"


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class MLP:
    """A tiny multilayer perceptron. ``W[l][i][j]`` is the weight from
    unit ``j`` of layer ``l`` to unit ``i`` of layer ``l+1``."""

    def __init__(self, sizes: List[int], seed: int = 7) -> None:
        if len(sizes) < 2:
            raise ValueError("deltasweep: need at least input and output layers")
        self.sizes = list(sizes)
        rng = random.Random(seed)
        # 3-D weight array: [layer][to][from]
        self.W: List[List[List[float]]] = [
            [[rng.uniform(-1.0, 1.0) for _ in range(n_in)] for _ in range(n_out)]
            for n_in, n_out in zip(sizes[:-1], sizes[1:], strict=True)
        ]
        self.b: List[List[float]] = [
            [rng.uniform(-1.0, 1.0) for _ in range(n)] for n in sizes[1:]
        ]

    # -- phase one: the forward sweep ---------------------------------------
    def forward(self, x: List[float]) -> List[List[float]]:
        """Run the input through; return activations per layer (incl. input)."""
        acts = [list(x)]
        for W, b in zip(self.W, self.b, strict=True):
            prev = acts[-1]
            acts.append(
                [
                    _sigmoid(sum(w * p for w, p in zip(row, prev, strict=True)) + bias)
                    for row, bias in zip(W, b, strict=True)
                ]
            )
        return acts

    # -- phase two: the backward sweep ----------------------------------------
    def _backward(
        self, acts: List[List[float]], target: List[float], eta: float
    ) -> float:
        """Propagate error derivatives via the chain rule and step every
        weight downhill: ``w -= η · ∂E/∂w``. Returns the sample error."""
        n_layers = len(self.W)
        # deltas[l][i] = ∂E/∂net for unit i of layer l+1
        deltas: List[List[float]] = [[] for _ in range(n_layers)]

        # output layer: ∂E/∂net = (out - target) · σ'(net)
        out = acts[-1]
        err = sum((o - t) ** 2 for o, t in zip(out, target, strict=True)) / 2.0
        deltas[-1] = [(o - t) * o * (1.0 - o) for o, t in zip(out, target, strict=True)]

        # hidden layers, walking backwards: δ^l = (W^{l+1}ᵀ δ^{l+1}) · σ'
        for li in range(n_layers - 2, -1, -1):
            nxt_W, nxt_delta = self.W[li + 1], deltas[li + 1]
            deltas[li] = [
                sum(nxt_W[k][j] * nxt_delta[k] for k in range(len(nxt_delta)))
                * a
                * (1.0 - a)
                for j, a in enumerate(acts[li + 1])
            ]

        # the weight step itself: ∂E/∂w = δ · activation
        for li in range(n_layers):
            for i, row in enumerate(self.W[li]):
                for j in range(len(row)):
                    row[j] -= eta * deltas[li][i] * acts[li][j]
            for i in range(len(self.b[li])):
                self.b[li][i] -= eta * deltas[li][i]
        return err

    def train_step(self, x: List[float], y: List[float], eta: float = 1.0) -> float:
        """One full two-phase sweep on a single sample."""
        return self._backward(self.forward(x), y, eta)

    def train(
        self,
        data: List[Tuple[List[float], List[float]]],
        epochs: int = 5000,
        eta: float = 1.0,
        shuffle_seed: int = 1,
    ) -> List[float]:
        """Train over the dataset; returns mean error per epoch (sampled)."""
        rng = random.Random(shuffle_seed)
        history = []
        for _ in range(epochs):
            order = list(range(len(data)))
            rng.shuffle(order)
            total = sum(self.train_step(*data[i], eta) for i in order)
            history.append(total / len(data))
        return history

    def predict(self, x: List[float]) -> List[float]:
        return self.forward(x)[-1]


# ---------------------------------------------------------------------------
# Demo — XOR, the classic non-linearly-separable toy
# ---------------------------------------------------------------------------

XOR = [
    ([0.0, 0.0], [0.0]),
    ([0.0, 1.0], [1.0]),
    ([1.0, 0.0], [1.0]),
    ([1.0, 1.0], [0.0]),
]


def demo(epochs: int = 8000, eta: float = 1.0) -> Tuple[MLP, List[float]]:
    """Train a 2-4-1 network on XOR; returns the network and error history."""
    net = MLP([2, 4, 1], seed=7)
    history = net.train(XOR, epochs=epochs, eta=eta)
    return net, history


if __name__ == "__main__":  # pragma: no cover - demo
    net, history = demo()
    print(f"epochs=8000  first err={history[0]:.4f}  last err={history[-1]:.6f}")
    for x, y in XOR:
        print(f"  {x} -> {net.predict(x)[0]:.3f} (want {y[0]:.0f})")
