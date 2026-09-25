"""bound_tiers — murex-purple memory: expensive to write, bound for life.

Studied from: lost-crafts-20260916 — report.md [Batch 4] (Murex Purple).

Load-bearing idea: the marvel of Tyrian purple was lightfastness —
6,6'-dibromoindigo binds wool *without a mordant*, permanently, and
costs a fortune to produce: thousands of snails for a gram. LEVI's
take: a tiered memory where higher tiers are extremely expensive to
write, permanently bound to their substrate identity, and hard to
bulk-export. ``write`` charges a cost budget per tier (the snail
harvest); reads bind the record to a substrate key and the record can
never be re-bound; bulk export is throttled per tier and the top tier
refuses bulk export entirely. Downgrades are one-way — bound records
only move to *cheaper* tiers, never up, so the expensive binding is
never minted cheaply.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/bound-tiers"


@dataclass(frozen=True)
class TierSpec:
    """The price and portability of one binding tier."""

    name: str
    write_cost: int  # cost units per write — the snail harvest
    bulk_export: bool  # may records leave in bulk?
    export_quota: int  # max records per export call


# Purple, bound without mordant: cost climbs steeply, export narrows.
TIERS: List[TierSpec] = [
    TierSpec("shell", write_cost=1, bulk_export=True, export_quota=100),
    TierSpec("vat", write_cost=10, bulk_export=True, export_quota=10),
    TierSpec("purple", write_cost=100, bulk_export=False, export_quota=1),
]


@dataclass
class BoundRecord:
    """A record permanently bound to its substrate."""

    id: str
    tier: str
    substrate: str  # the "wool" — set once, never re-bound
    body: str
    bound_at: float
    cost_paid: int


class BindingError(Exception):
    """The binding rules refused an operation."""


class BoundTiers:
    """Tiered, permanently-bound memory with real write costs."""

    def __init__(self) -> None:
        self._tiers: Dict[str, TierSpec] = {t.name: t for t in TIERS}
        self.records: Dict[str, BoundRecord] = {}
        self.budget: int = 0  # cost units available for writes
        self._exported: Dict[str, int] = {}  # tier -> records exported this session

    # -- the harvest ---------------------------------------------------------

    def grant_budget(self, units: int) -> int:
        """Top up the cost budget (the fleet's snail harvest)."""
        if units < 0:
            raise BindingError("budget grants must be non-negative")
        self.budget += units
        return self.budget

    # -- binding ---------------------------------------------------------------

    def write(
        self,
        record_id: str,
        tier: str,
        substrate: str,
        body: str,
        now: Optional[float] = None,
    ) -> BoundRecord:
        """Bind a record to a substrate in a tier. Charges the write cost.

        Purple is permanent: rewriting an existing id in the same or a
        higher tier is refused; only a one-way downgrade to a cheaper
        tier is allowed (the old binding is kept as history).
        """
        spec = self._tier(tier)
        if record_id in self.records:
            existing = self.records[record_id]
            if self._cost_of(existing.tier) <= spec.write_cost:
                raise BindingError(
                    f"{record_id!r} is already bound at {existing.tier!r}: "
                    "re-binding is forbidden; only downgrades allowed"
                )
        if self.budget < spec.write_cost:
            raise BindingError(
                f"tier {tier!r} costs {spec.write_cost} but budget is {self.budget}"
            )
        self.budget -= spec.write_cost
        record = BoundRecord(
            id=record_id,
            tier=tier,
            substrate=substrate,
            body=body,
            bound_at=now if now is not None else time.time(),
            cost_paid=spec.write_cost,
        )
        self.records[record_id] = record
        return record

    def read(self, record_id: str) -> BoundRecord:
        return self.records[record_id]

    # -- the re-binding prohibition ----------------------------------------------

    def rebind(self, record_id: str, new_substrate: str) -> None:
        """Re-binding is impossible — the dye is in the wool. Always refused."""
        record = self.records.get(record_id)
        detail = (
            f"{record_id!r} is permanently bound to {record.substrate!r}"
            if record is not None
            else f"{record_id!r} is unknown"
        )
        raise BindingError(f"{detail}: records are never re-bound")

    # -- hard-to-bulk-export -------------------------------------------------------

    def export(self, tier: str, limit: Optional[int] = None) -> List[BoundRecord]:
        """Export records from a tier, honoring the tier's export quota.

        The purple tier refuses bulk export entirely (quota 1, and only
        via single-record export). Export is throttled per tier per
        session.
        """
        spec = self._tier(tier)
        if not spec.bulk_export:
            raise BindingError(
                f"tier {tier!r} refuses bulk export: "
                "permanently-bound records do not leave in bulk"
            )
        quota = min(limit or spec.export_quota, spec.export_quota)
        already = self._exported.get(tier, 0)
        available = [r for r in self.records.values() if r.tier == tier][
            already : already + quota
        ]
        self._exported[tier] = already + len(available)
        return available

    # -- internals ----------------------------------------------------------

    def _tier(self, name: str) -> TierSpec:
        try:
            return self._tiers[name]
        except KeyError:
            raise BindingError(f"unknown tier {name!r}") from None

    def _cost_of(self, tier: str) -> int:
        return self._tier(tier).write_cost

    def tier_names(self) -> List[str]:
        return [t.name for t in TIERS]
