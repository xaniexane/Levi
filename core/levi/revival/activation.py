"""Activation-based memory — remembering as a side effect of arithmetic.

Studied from: retired-software catalog (sec 17);
ai-si-software-internals-20260916-0005/report.md (sec 1.6) — MERGED,
plus the "Memory scoring (re-derived)" entry (ai-si sec 2.7) folded in.

The mechanism under study: memory strength is a number, not a place.
Each chunk carries a base-level activation from its history — recency ×
frequency with power-law decay, so yesterday's tenth rehearsal beats
last month's single glance. Context spreads extra activation to chunks
that share its elements; partial matching penalizes dissimilar chunks;
noise keeps retrieval honest and non-degenerate. Retrieval takes the
highest-activation chunk above a threshold — and *forgetting emerges*:
a chunk that decays below threshold simply stops being retrievable. No
deletion routine exists. Nothing is ever erased on purpose.

The declarative store (chunks) is strictly separate from a tiny
procedural rule set (condition → action productions); the two meet only
through retrieval calls, the way perception meets memory.

The folded-in scoring entry: ``score()`` blends similarity, recency,
and usage with a quality floor — anything below the floor is
unrankable, no matter how loud the other signals are.

Original, from-scratch implementation for LEVI. Time is an explicit
float you control (no wall-clock dependence — deterministic tests).
Noise is deterministic (hash-seeded), so runs are reproducible.

Public surface:
- ``DeclarativeStore`` — ``encode(kind, slots, at)``,
  ``retrieve(cue, context=None, at=now, partial=False)``,
  ``rehearse(chunk_id, at)``, ``activation(chunk, cue, context, at)``,
  ``score(chunk, cue, at)``, ``rank(cue, at)``.
- ``ProceduralMemory`` — ``add_rule(name, condition, action)``,
  ``step(buffers, declarative, at)``; conditions see buffers only.
- ``Chunk`` — the unit of memory.

stdlib-only. No network.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/activation"


def _noise(chunk_id: int, n_uses: int, scale: float) -> float:
    """Deterministic pseudo-noise in [-scale, +scale]."""
    h = hashlib.md5(f"{chunk_id}:{n_uses}".encode()).digest()
    u = int.from_bytes(h[:4], "big") / 2**32  # [0, 1)
    return (u * 2.0 - 1.0) * scale


@dataclass
class Chunk:
    """One declarative memory: a typed bundle of slot values + its history."""

    id: int
    kind: str
    slots: Dict[str, Any] = field(default_factory=dict)
    created: float = 0.0
    uses: List[float] = field(default_factory=list)  # encoding + rehearsals

    def touch(self, at: float) -> None:
        self.uses.append(at)


class DeclarativeStore:
    """Chunks with activation arithmetic. Forgetting is emergent."""

    def __init__(
        self,
        decay: float = 0.5,
        threshold: float = 0.0,
        noise_scale: float = 0.1,
        mismatch_penalty: float = 1.0,
        spread_weight: float = 1.0,
        score_weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
        quality_floor: float = 0.15,
    ) -> None:
        self.decay = decay
        self.threshold = threshold
        self.noise_scale = noise_scale
        self.mismatch_penalty = mismatch_penalty
        self.spread_weight = spread_weight
        self.score_weights = score_weights
        self.quality_floor = quality_floor
        self.chunks: Dict[int, Chunk] = {}
        self._next_id = 0

    # ------------------------------------------------------------------
    # encoding / rehearsal
    # ------------------------------------------------------------------
    def encode(self, kind: str, slots: Dict[str, Any], at: float = 0.0) -> Chunk:
        self._next_id += 1
        chunk = Chunk(self._next_id, kind, dict(slots), created=at, uses=[at])
        self.chunks[chunk.id] = chunk
        return chunk

    def rehearse(self, chunk_id: int, at: float) -> None:
        self.chunks[chunk_id].touch(at)

    # ------------------------------------------------------------------
    # activation components
    # ------------------------------------------------------------------
    def base_level(self, chunk: Chunk, at: float) -> float:
        """ln( sum_k (at - t_k)^-d ) — recency × frequency, power-law decay."""
        total = 0.0
        for t in chunk.uses:
            lag = max(at - t, 1e-6)
            total += lag ** (-self.decay)
        return math.log(total) if total > 0 else float("-inf")

    def spreading(self, chunk: Chunk, context: Optional[Dict[str, Any]]) -> float:
        """Activation flowing in from context elements the chunk shares."""
        if not context:
            return 0.0
        w = 1.0 / len(context)
        strength = 0.0
        values = set(chunk.slots.values())
        for elem in context.values():
            if elem in values:
                strength += w
        return self.spread_weight * strength

    def similarity(self, chunk: Chunk, cue: Dict[str, Any]) -> float:
        """Fraction of cue slots the chunk matches (kind must match)."""
        if chunk.kind != cue.get("__kind", chunk.kind):
            return 0.0
        keys = [k for k in cue if not k.startswith("__")]
        if not keys:
            return 1.0
        hits = sum(1 for k in keys if chunk.slots.get(k) == cue[k])
        return hits / len(keys)

    def partial_penalty(self, chunk: Chunk, cue: Dict[str, Any]) -> float:
        return -self.mismatch_penalty * (1.0 - self.similarity(chunk, cue))

    def activation(
        self,
        chunk: Chunk,
        cue: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        at: float = 0.0,
    ) -> float:
        a = self.base_level(chunk, at)
        a += self.spreading(chunk, context)
        if cue:
            a += self.partial_penalty(chunk, cue)
        a += _noise(chunk.id, len(chunk.uses), self.noise_scale)
        return a

    # ------------------------------------------------------------------
    # retrieval — winner above threshold, or honest nothing
    # ------------------------------------------------------------------
    def retrieve(
        self,
        cue: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        at: float = 0.0,
    ) -> Optional[Tuple[Chunk, float, float]]:
        """Returns (chunk, activation, latency) or None when nothing clears
        the threshold — that silence IS forgetting."""
        best: Optional[Chunk] = None
        best_a = float("-inf")
        for chunk in self.chunks.values():
            a = self.activation(chunk, cue, context, at)
            if a > best_a:
                best_a, best = a, chunk
        if best is None or best_a < self.threshold:
            return None
        best.touch(at)  # retrieval is itself a use — memory strengthens
        latency = math.exp(-best_a)
        return best, best_a, latency

    def retrievable(
        self, chunk_id: int, at: float, cue: Optional[Dict[str, Any]] = None
    ) -> bool:
        chunk = self.chunks[chunk_id]
        return self.activation(chunk, cue, None, at) >= self.threshold

    # ------------------------------------------------------------------
    # memory scoring — similarity/recency/usage blend with a quality floor
    # ------------------------------------------------------------------
    def _recency(self, chunk: Chunk, at: float) -> float:
        if not chunk.uses:
            return 0.0
        lag = max(at - max(chunk.uses), 1e-6)
        return 1.0 / (1.0 + lag)

    def _usage(self, chunk: Chunk) -> float:
        return 1.0 - 1.0 / (1.0 + len(chunk.uses))

    def score(self, chunk: Chunk, cue: Dict[str, Any], at: float) -> float:
        """Blend of similarity, recency, usage — floored at quality_floor."""
        ws, wr, wu = self.score_weights
        raw = (
            ws * self.similarity(chunk, cue)
            + wr * self._recency(chunk, at)
            + wu * self._usage(chunk)
        )
        return raw if raw >= self.quality_floor else 0.0

    def rank(
        self, cue: Dict[str, Any], at: float = 0.0, limit: Optional[int] = None
    ) -> List[Tuple[Chunk, float]]:
        ranked = [(c, self.score(c, cue, at)) for c in self.chunks.values()]
        ranked = [(c, s) for (c, s) in ranked if s > 0.0]
        ranked.sort(key=lambda cs: -cs[1])
        return ranked[:limit] if limit else ranked

    def __len__(self) -> int:
        return len(self.chunks)


# ----------------------------------------------------------------------
# procedural side — deliberately tiny, deliberately separate
# ----------------------------------------------------------------------
@dataclass
class Production:
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    action: Callable[[Dict[str, Any], DeclarativeStore, float], Optional[str]]


class ProceduralMemory:
    """A small rule set that sees buffers only — never chunk internals.

    Rules match on the buffer dict; actions may call into the declarative
    store (retrieve/encode/rehearse) and may rewrite buffers. The
    separation is the point: skill lives here, facts live over there.
    """

    def __init__(self) -> None:
        self.rules: List[Production] = []
        self.fired: List[str] = []

    def add_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        action: Callable[[Dict[str, Any], DeclarativeStore, float], Optional[str]],
    ) -> None:
        self.rules.append(Production(name, condition, action))

    def step(
        self, buffers: Dict[str, Any], declarative: DeclarativeStore, at: float = 0.0
    ) -> Optional[str]:
        """First matching rule fires (ordered). Returns its name or None."""
        for rule in self.rules:
            if rule.condition(buffers):
                note = rule.action(buffers, declarative, at)
                self.fired.append(rule.name)
                return rule.name if note is None else f"{rule.name}: {note}"
        return None

    def run(
        self,
        buffers: Dict[str, Any],
        declarative: DeclarativeStore,
        at: float = 0.0,
        max_steps: int = 10,
    ) -> List[str]:
        trace: List[str] = []
        for _ in range(max_steps):
            fired = self.step(buffers, declarative, at)
            if fired is None:
                break
            trace.append(fired)
        return trace
