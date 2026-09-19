"""attention_dials — sovereign ranking weights, user-owned and visible.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 1]).
Load-bearing idea: the weights that rank a feed belong to the user —
visible, editable, and portable — with chronological order as a sticky
default the user can always return to.

LEVI's take: ``Dials`` holds named weights (recency, affinity, engagement,
topicality, diversity, serendipity), each 0..1 and editable, and ranks
plain item dicts with a fully inspectable score breakdown. ``chronological``
is a sticky default preset: ``reset_to_chronological()`` is one call, and
any ranking can be forced chronological. Presets serialize to dicts so the
user can carry their dials anywhere.

Ranking here is a deterministic weighted sum over declared features — a
heuristic the user steers, not a black box. Score breakdowns are always
returned alongside the order so nothing is hidden.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


ORIGIN = "levi-revival/attention-dials"

# Feature keys every ranked item may carry; missing features count as 0.
DIALS = ("recency", "affinity", "engagement", "topicality", "diversity", "serendipity")


@dataclass
class ScoredItem:
    item: dict
    score: float
    breakdown: Dict[str, float]


class Dials:
    """User-owned ranking weights. Chronological is the sticky default."""

    def __init__(self, weights: Dict[str, float] | None = None) -> None:
        self.weights: Dict[str, float] = self._chrono_weights()
        if weights:
            self.set_all(weights)

    @staticmethod
    def _chrono_weights() -> Dict[str, float]:
        return {d: (1.0 if d == "recency" else 0.0) for d in DIALS}

    # -- editing the dials ----------------------------------------------------

    def set(self, dial: str, weight: float) -> None:
        if dial not in DIALS:
            raise KeyError(f"unknown dial {dial!r}; choose from {DIALS}")
        if not 0.0 <= weight <= 1.0:
            raise ValueError("weight must be within 0..1")
        self.weights[dial] = weight

    def set_all(self, weights: Dict[str, float]) -> None:
        for dial, weight in weights.items():
            self.set(dial, weight)

    def reset_to_chronological(self) -> None:
        """The sticky default: pure recency, everything else zero."""
        self.weights = self._chrono_weights()

    def preset(self) -> Dict[str, float]:
        return dict(self.weights)

    def load_preset(self, weights: Dict[str, float]) -> None:
        self.reset_to_chronological()
        self.set_all(weights)

    # -- ranking --------------------------------------------------------------

    def score(self, item: dict) -> ScoredItem:
        features = item.get("features", {}) if isinstance(item, dict) else {}
        breakdown = {d: self.weights[d] * float(features.get(d, 0.0)) for d in DIALS}
        total = sum(breakdown.values())
        return ScoredItem(item=item, score=total, breakdown=breakdown)

    def rank(self, items: Sequence[dict]) -> List[ScoredItem]:
        """Rank by weighted score; ties break by recency feature, then id."""
        scored = [self.score(it) for it in items]

        def key(s: ScoredItem) -> Tuple[float, float, str]:
            feats = s.item.get("features", {}) if isinstance(s.item, dict) else {}
            return (
                -s.score,
                -float(feats.get("recency", 0.0)),
                str(s.item.get("id", "")) if isinstance(s.item, dict) else "",
            )

        return sorted(scored, key=key)

    def rank_chronological(self, items: Sequence[dict]) -> List[ScoredItem]:
        """Sticky-default view: newest first, dials ignored."""

        def ts(it: dict) -> float:
            return float(it.get("ts", 0.0)) if isinstance(it, dict) else 0.0

        return [
            ScoredItem(item=it, score=ts(it), breakdown={"ts": ts(it)})
            for it in sorted(items, key=ts, reverse=True)
        ]

    # -- snapshots ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {"weights": dict(self.weights)}

    @classmethod
    def from_dict(cls, d: dict) -> "Dials":
        return cls(weights=dict(d.get("weights", {})))
