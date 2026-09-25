"""Growable experts for LEVI's native brain MLPs.

Interpenetration piece 2 of 3: the mini-AGI *direction* (mixture of
experts that grows by adding experts and sheds by pruning, only a
subset active) composed with the real TinyGPT MLP blocks that LEVI
already trained.

Design
-------
Each transformer block's MLP (fc: d -> 4d with bias, GELU, proj:
4d -> d with bias) becomes a :class:`GrowableMLP`: a set of experts,
each expert a full copy of that MLP's weights, plus a tiny router
(d -> n_experts). Forward runs top-k experts per token and mixes
their outputs by renormalized gate weights.

- ``add_expert(seed)``: new expert = expert 0's weights + small
  seeded Gaussian noise. Deterministic given the seed.
- ``prune_expert()``: drops the lowest-utilization expert (never the
  last one). Utilization = tokens routed to the expert since the last
  reset.
- One expert: gating is bypassed entirely, so forward is
  bit-identical to the plain MLP — the existing forward pass cannot
  break.

Honest scope
------------
- This is a growth *skeleton*: add/prune mechanics, routing, and
  utilization accounting. It does NOT train experts (no load-balancing
  loss, no expert specialization) — that needs the torch training
  loop and is explicitly future work.
- mini-AGI's weights are unreleased; "grows itself on an 8GB laptop"
  is a vendor/community claim, UNVERIFIED here. This module proves
  only that the mechanics compose with LEVI's architecture.

Stdlib-only at import; numpy is imported lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _np():
    import numpy as np  # lazy: kernel stays stdlib-only at import

    return np


def _gelu(x: Any) -> Any:
    np = _np()
    # tanh approximation, matches runtime._gelu_np
    c = np.sqrt(2.0 / np.pi)
    return 0.5 * x * (1.0 + np.tanh(c * (x + 0.044715 * x**3)))


@dataclass
class Expert:
    w1: Any  # (4d, d)
    b1: Any  # (4d,)
    w2: Any  # (d, 4d)
    b2: Any  # (d,)


class GrowableMLP:
    """An MLP block that can grow and shed experts.

    Built from a real trained block via :meth:`from_block_tensors`.
    ``top_k`` experts are active per token; the rest sit idle (the
    phone only pays for k).
    """

    def __init__(
        self,
        experts: List[Expert],
        router_w: Any,
        router_b: Any,
        top_k: int = 1,
    ) -> None:
        np = _np()
        if not experts:
            raise ValueError("GrowableMLP needs at least one expert")
        self.experts: List[Expert] = list(experts)
        self.router_w = np.asarray(router_w, dtype=np.float32)
        self.router_b = np.asarray(router_b, dtype=np.float32)
        self.top_k = max(1, int(top_k))
        self.utilization: List[int] = [0] * len(self.experts)

    # -- construction -------------------------------------------------

    @classmethod
    def from_block_tensors(
        cls,
        w1: Any,
        b1: Any,
        w2: Any,
        b2: Any,
        top_k: int = 1,
        seed: int = 0,
    ) -> "GrowableMLP":
        """Seed from one trained MLP block. Starts as a single expert."""
        np = _np()
        w1a = np.asarray(w1, dtype=np.float32)
        rng = np.random.RandomState(seed)
        d = w1a.shape[1]
        router_w = (rng.randn(d, 1) * 0.02).astype(np.float32)
        router_b = np.zeros(1, dtype=np.float32)
        return cls(
            experts=[
                Expert(
                    w1=w1a,
                    b1=np.asarray(b1, dtype=np.float32),
                    w2=np.asarray(w2, dtype=np.float32),
                    b2=np.asarray(b2, dtype=np.float32),
                )
            ],
            router_w=router_w,
            router_b=router_b,
            top_k=top_k,
        )

    @property
    def n_experts(self) -> int:
        return len(self.experts)

    # -- growth -------------------------------------------------------

    def add_expert(self, seed: int = 0, noise: float = 1e-3) -> int:
        """Append an expert: expert-0 weights + seeded noise. Returns count."""
        np = _np()
        rng = np.random.RandomState(seed)
        base = self.experts[0]
        new = Expert(
            w1=base.w1 + (rng.randn(*base.w1.shape) * noise).astype(np.float32),
            b1=base.b1.copy(),
            w2=base.w2 + (rng.randn(*base.w2.shape) * noise).astype(np.float32),
            b2=base.b2.copy(),
        )
        self.experts.append(new)
        # grow the router with a fresh seeded column so routing can discover it
        col = (rng.randn(self.router_w.shape[0], 1) * 0.02).astype(np.float32)
        self.router_w = np.concatenate([self.router_w, col], axis=1)
        self.router_b = np.concatenate(
            [self.router_b, np.zeros(1, dtype=np.float32)]
        )
        self.utilization.append(0)
        return self.n_experts

    def prune_expert(self) -> Optional[int]:
        """Drop the lowest-utilization expert. Never drops the last one.

        Returns the pruned index, or None when only one expert remains.
        """
        np = _np()
        if self.n_experts <= 1:
            return None
        idx = int(np.argmin(np.asarray(self.utilization)))
        del self.experts[idx]
        self.router_w = np.delete(self.router_w, idx, axis=1)
        self.router_b = np.delete(self.router_b, idx, axis=0)
        del self.utilization[idx]
        return idx

    def reset_utilization(self) -> None:
        self.utilization = [0] * self.n_experts

    # -- forward ------------------------------------------------------

    def _plain_mlp(self, h: Any, e: Expert) -> Any:
        return _gelu(h @ e.w1.T + e.b1) @ e.w2.T + e.b2

    def forward(self, h: Any) -> Any:
        """(T, d) -> (T, d). Top-k experts active per token."""
        np = _np()
        h = np.asarray(h, dtype=np.float32)
        if self.n_experts == 1:
            # No gating: bit-identical to the original MLP forward.
            return self._plain_mlp(h, self.experts[0])
        logits = h @ self.router_w + self.router_b  # (T, E)
        logits = logits - logits.max(axis=-1, keepdims=True)
        exp = np.exp(logits)
        gates = exp / exp.sum(axis=-1, keepdims=True)
        k = min(self.top_k, self.n_experts)
        # top-k mask per token
        top_idx = np.argpartition(-gates, k - 1, axis=-1)[:, :k]  # (T, k)
        mask = np.zeros_like(gates)
        rows = np.arange(gates.shape[0])[:, None]
        mask[rows, top_idx] = gates[rows, top_idx]
        renorm = mask.sum(axis=-1, keepdims=True)
        renorm = np.where(renorm == 0, 1.0, renorm)
        weights = mask / renorm
        out = np.zeros_like(h)
        for e in range(self.n_experts):
            wcol = weights[:, e : e + 1]
            active = wcol[:, 0] != 0
            if not bool(active.any()):
                continue
            self.utilization[e] += int(active.sum())
            out[active] += wcol[active] * self._plain_mlp(
                h[active], self.experts[e]
            )
        return out


def growable_mlps_from_params(
    params: Dict[str, Any], n_layer: int, top_k: int = 1, seed: int = 0
) -> Dict[int, GrowableMLP]:
    """Build one GrowableMLP per block from real trained MLP tensors."""
    mlps: Dict[int, GrowableMLP] = {}
    for layer in range(n_layer):
        p = f"blocks.{layer}"
        mlps[layer] = GrowableMLP.from_block_tensors(
            params[f"{p}.mlp.0.weight"],
            params[f"{p}.mlp.0.bias"],
            params[f"{p}.mlp.2.weight"],
            params[f"{p}.mlp.2.bias"],
            top_k=top_k,
            seed=seed + layer,
        )
    return mlps
