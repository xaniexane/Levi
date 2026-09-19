"""moerouter — mixture-of-experts routing, reference scale.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.4).

Sparse layers scale parameters without scaling FLOPs per token: each
token is processed by k of E expert networks, chosen by a learned gate.
The whole game is load balancing — the failure mode is *expert
collapse*, where the gate self-reinforces a few popular experts and the
rest atrophy. This module is the routing machinery, from scratch, with
four published balancing ideas expressed in LEVI's own words:

* **Token-choice gating**: scores ``s = softmax(x·Wg)`` plus exploration
  noise ``N(0,1)·softplus(x·Wnoise)``; keep the top-k, renormalize; the
  output is the weighted sum of the chosen experts.
* **Auxiliary load-balancing loss**: ``L = E · Σ f_i · p_i`` where
  ``f_i`` is the fraction of tokens routed to expert i and ``p_i`` the
  mean gate probability. Added to the training objective, it punishes
  the gate for playing favorites.
* **Expert capacity + token dropping**: each expert takes at most
  ``capacity_factor × (tokens × k / E)`` tokens; overflow tokens are
  dropped (passed through unchanged). Overprovision the factor 2–8× in
  real systems; here it's a knob.
* **Expert-choice routing**: the mirror image — each expert picks its
  top-k tokens. Balance is guaranteed by construction (every expert
  gets exactly k), at the cost of a variable number of experts per
  token.
* **Aux-loss-free bias nudging**: per-expert biases used *only* for
  routing (never in the output), nudged by measured load each step —
  ``b_i -= γ·(load_i − mean_load)``. Balances the router without letting
  an auxiliary loss distort the main objective.

Toy-scale honesty: real MoE needs millions of samples before experts
specialize; on small data, parameter dilution hurts. This module is for
studying the *routing dynamics* — watch the load histograms — not for
training a useful MoE. The pattern LEVI actually steals is at the agent
level: a tiny gating decision over tools/experts with usage-based bias
correction, so the router can't collapse onto one favorite.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

ORIGIN = "levi-revival/moerouter"


def softmax(xs: List[float]) -> List[float]:
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass
class Routing:
    """Result of routing one batch of tokens."""

    # token index -> list of (expert index, weight)
    assignments: Dict[int, List[Tuple[int, float]]]
    gate_probs: List[List[float]]  # per token, over all experts
    dropped: List[int] = field(default_factory=list)

    def load_histogram(self, n_experts: int) -> List[int]:
        hist = [0] * n_experts
        for pairs in self.assignments.values():
            for expert, _ in pairs:
                hist[expert] += 1
        return hist

    def mean_probs(self) -> List[float]:
        n = len(self.gate_probs[0])
        acc = [0.0] * n
        for probs in self.gate_probs:
            for i, p in enumerate(probs):
                acc[i] += p
        return [a / len(self.gate_probs) for a in acc]


class MoERouter:
    """Token-choice router: noisy softmax gate + top-k + capacity."""

    def __init__(
        self,
        n_experts: int,
        dim: int,
        top_k: int = 2,
        capacity_factor: float = 2.0,
        noise: float = 1.0,
        seed: int = 11,
    ) -> None:
        self.n_experts = n_experts
        self.dim = dim
        self.top_k = top_k
        self.capacity_factor = capacity_factor
        self.noise = noise
        rng = random.Random(seed)
        self.w_gate = [
            [rng.gauss(0, 0.5) for _ in range(dim)] for _ in range(n_experts)
        ]
        self.w_noise = [
            [rng.gauss(0, 0.5) for _ in range(dim)] for _ in range(n_experts)
        ]

    def _gate_scores(self, x: List[float], rng: random.Random) -> List[float]:
        scores = []
        for e in range(self.n_experts):
            clean = _dot(x, self.w_gate[e])
            sigma = math.log1p(math.exp(_dot(x, self.w_noise[e])))  # softplus
            scores.append(clean + rng.gauss(0, 1) * sigma * self.noise)
        return scores

    def route(self, tokens: List[List[float]], seed: int = 0) -> Routing:
        """Route tokens; drop tokens overflowing expert capacity."""
        rng = random.Random(seed)
        gate_probs = [softmax(self._gate_scores(x, rng)) for x in tokens]
        capacity = max(
            1,
            math.ceil(self.capacity_factor * len(tokens) * self.top_k / self.n_experts),
        )
        used = [0] * self.n_experts
        assignments: Dict[int, List[Tuple[int, float]]] = {}
        dropped: List[int] = []
        for t, (_x, probs) in enumerate(zip(tokens, gate_probs, strict=True)):
            ranked = sorted(range(self.n_experts), key=lambda e: probs[e], reverse=True)
            chosen = [e for e in ranked[: self.top_k] if used[e] < capacity]
            for e in chosen:
                used[e] += 1
            if len(chosen) < self.top_k:
                dropped.append(t)  # token overflowed every candidate expert
            total = sum(probs[e] for e in chosen) or 1.0
            assignments[t] = [(e, probs[e] / total) for e in chosen]
        return Routing(assignments=assignments, gate_probs=gate_probs, dropped=dropped)

    def forward(
        self,
        tokens: List[List[float]],
        experts: List[Callable[[List[float]], List[float]]],
        seed: int = 0,
    ) -> Tuple[List[List[float]], Routing]:
        """Run the routed batch through toy expert callables."""
        routing = self.route(tokens, seed=seed)
        out: List[List[float]] = []
        for t, x in enumerate(tokens):
            acc = [0.0] * len(x)
            for e, w in routing.assignments.get(t, []):
                y = experts[e](x)
                for i in range(len(acc)):
                    acc[i] += w * y[i]
            out.append(acc)
        return out, routing

    @staticmethod
    def aux_loss(routing: Routing, n_experts: int) -> float:
        """L = E · Σ f_i · p_i — the auxiliary load-balancing loss."""
        counts = routing.load_histogram(n_experts)
        total = sum(counts) or 1
        f = [c / total for c in counts]
        p = routing.mean_probs()
        return n_experts * sum(fi * pi for fi, pi in zip(f, p, strict=True))


def expert_choice_route(
    scores: List[List[float]], k_per_expert: int
) -> Dict[int, List[Tuple[int, float]]]:
    """Expert-choice routing: each expert picks its top-k tokens.

    ``scores``: per token, per expert affinity. Returns
    token -> [(expert, weight)] with exactly k_per_expert tokens per
    expert — balance by construction, variable experts per token.
    """
    n_tokens = len(scores)
    n_experts = len(scores[0])
    probs = [softmax(s) for s in scores]
    chosen: Dict[int, List[Tuple[int, float]]] = {t: [] for t in range(n_tokens)}
    for e in range(n_experts):
        ranked = sorted(range(n_tokens), key=lambda t: probs[t][e], reverse=True)
        for t in ranked[:k_per_expert]:
            chosen[t].append((e, probs[t][e]))
    for t in chosen:
        total = sum(w for _, w in chosen[t]) or 1.0
        chosen[t] = [(e, w / total) for e, w in chosen[t]]
    return chosen


class AuxLossFreeBalancer:
    """Per-expert routing biases nudged by measured load (no aux loss).

    Biases participate in routing only — never in the output — so the
    main objective is never distorted. Each step: ``b_i -= γ·(load_i −
    mean_load)``; overloaded experts get a negative nudge, idle ones a
    positive nudge.
    """

    def __init__(self, n_experts: int, gamma: float = 0.05) -> None:
        self.biases = [0.0] * n_experts
        self.gamma = gamma

    def route_with_bias(self, gate_probs: List[List[float]]) -> List[int]:
        """Argmax routing with biases applied (top-1 for clarity)."""
        winners = []
        for probs in gate_probs:
            scored = [p + b for p, b in zip(probs, self.biases, strict=True)]
            winners.append(max(range(len(scored)), key=lambda i: scored[i]))
        return winners

    def nudge(self, winners: List[int]) -> List[float]:
        n = len(self.biases)
        loads = [0] * n
        for w in winners:
            loads[w] += 1
        mean = sum(loads) / n
        for i in range(n):
            self.biases[i] -= self.gamma * (loads[i] - mean)
        return list(self.biases)

    def load_std(self, winners: List[int]) -> float:
        n = len(self.biases)
        loads = [winners.count(i) for i in range(n)]
        mean = sum(loads) / n
        return math.sqrt(sum((load - mean) ** 2 for load in loads) / n)
