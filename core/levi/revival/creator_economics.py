"""creator_economics — transparent per-unit payouts, audience portability.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S4].

Load-bearing idea: creators are paid from a published rate card, not a black
box. Payouts are per unit delivered, weighted by quality signals the audience
gives explicitly (saves, finishes) — and the weighting formula is public, not
an opaque engagement score. The audience list belongs to the creator and can
be exported at any time: portability, not lock-in.

LEVI's take: ``CreatorLedger`` publishes a ``RateCard``, records deliveries
with explicit quality signals, computes payouts with the documented
``quality_weight()`` formula, and hands creators their audience via
``export_audience()``.

Honest limits: the quality signals are supplied by the surrounding app; the
ledger trusts but documents them. Payouts are accounting, not money movement.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

ORIGIN = "levi-revival/creator-economics"


@dataclass
class RateCard:
    """The published deal. Every creator sees the same numbers."""

    per_unit_cents: int
    quality_bonus_cents: int
    currency: str = "USD"

    def describe(self) -> str:
        return (
            f"{self.per_unit_cents}c per unit delivered, plus up to "
            f"{self.quality_bonus_cents}c quality bonus per unit. Same card for everyone."
        )


@dataclass
class Delivery:
    """Units a creator delivered, with the audience's explicit quality signals."""

    creator: str
    units: int
    saves: int = 0  # audience explicitly saved/kept the work
    finishes: int = 0  # audience explicitly finished the work


def quality_weight(saves: int, finishes: int, units: int) -> float:
    """Public quality formula: explicit signals only, bounded 0..1.

    weight = (saves + finishes) / (2 * units), clamped to [0, 1].
    No hidden engagement metrics, no per-creator tuning — the same
    arithmetic for everyone, inspectable by anyone.
    """
    if units <= 0:
        return 0.0
    raw = (saves + finishes) / (2 * units)
    return max(0.0, min(1.0, raw))


class CreatorLedger:
    """Transparent creator payouts with portable audiences."""

    def __init__(self, rate_card: RateCard) -> None:
        self.rate_card = rate_card
        self._deliveries: List[Delivery] = []
        self._audiences: Dict[str, Set[str]] = {}

    def register_creator(self, creator: str) -> None:
        """Register a creator. Registration is free and instant."""
        self._audiences.setdefault(creator, set())

    def add_audience(self, creator: str, member: str) -> None:
        """Record an audience member. The list belongs to the creator."""
        if creator not in self._audiences:
            raise KeyError(f"unknown creator: {creator!r}")
        self._audiences[creator].add(member)

    def record_delivery(self, delivery: Delivery) -> None:
        """Record delivered units with their explicit quality signals."""
        if delivery.creator not in self._audiences:
            raise KeyError(f"unknown creator: {delivery.creator!r}")
        if delivery.units < 0:
            raise ValueError("units must not be negative")
        self._deliveries.append(delivery)

    def payout_cents(self, creator: str) -> int:
        """Total owed to a creator: units x rate + quality bonus x weight.

        Uses only the published rate card and the public quality formula.
        """
        total = 0
        for d in self._deliveries:
            if d.creator != creator:
                continue
            w = quality_weight(d.saves, d.finishes, d.units)
            total += d.units * self.rate_card.per_unit_cents
            total += int(d.units * self.rate_card.quality_bonus_cents * w)
        return total

    def payout_breakdown(self, creator: str) -> List[Dict]:
        """Per-delivery line items, so a creator can check the math."""
        lines = []
        for d in self._deliveries:
            if d.creator != creator:
                continue
            w = quality_weight(d.saves, d.finishes, d.units)
            base = d.units * self.rate_card.per_unit_cents
            bonus = int(d.units * self.rate_card.quality_bonus_cents * w)
            lines.append(
                {
                    "units": d.units,
                    "saves": d.saves,
                    "finishes": d.finishes,
                    "quality_weight": round(w, 4),
                    "base_cents": base,
                    "bonus_cents": bonus,
                    "total_cents": base + bonus,
                }
            )
        return lines

    def export_audience(self, creator: str) -> List[str]:
        """The creator's audience, portable, no exit fee, no notice period."""
        if creator not in self._audiences:
            raise KeyError(f"unknown creator: {creator!r}")
        return sorted(self._audiences[creator])
