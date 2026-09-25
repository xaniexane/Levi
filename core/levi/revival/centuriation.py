"""LEVI's titled land grid: parcels with deeds, and quarantined survey conflicts.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(Roman Pes/Actus — centuriation)

The studied mechanism:

* land as a *titled spatial database*: the survey grid divided country
  into regular squares (centuries), each with a recorded holder — the
  map *was* the ownership record;
* subsecivum — the elegant part. Where new surveys collided with old
  claims, the disputed strip was *quarantined*: recorded with both
  claims attached and left unassigned, instead of being overwritten by
  whoever surveyed last. Conflicts were data, not errors to pave over.

This module rebuilds that as LEVI's own mechanism. A
:class:`LandRegistry` holds rectangular :class:`Parcel`s on an integer
grid, each with a title deed (holder, surveyed date, surveyor). Registering
a parcel that overlaps an existing one does not overwrite: the overlap
becomes a :class:`Quarantine` — both claims recorded, the strip marked
unassigned — and :meth:`LandRegistry.adjudicate` later resolves it by a
stated rule (earliest survey wins by default; the caller may pass
another). :meth:`lookup` finds which parcel owns a point; quarantined
strips answer "disputed" honestly.

Honest limits: rectangles on an integer grid, not real geodesy. The
adjudication rules are declared policy, not law — the module records
*which* rule resolved each dispute so the decision stays auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


ORIGIN = "levi-revival/centuriation"


class LandError(Exception):
    """Base error for land-registry failures."""


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle on the integer grid: (x0, y0, x1, y1)."""

    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise LandError(f"degenerate rect {self}")

    def area(self) -> int:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def contains(self, x: int, y: int) -> bool:
        return self.x0 <= x < self.x1 and self.y0 <= y < self.y1

    def overlap(self, other: "Rect") -> Optional["Rect"]:
        x0, y0 = max(self.x0, other.x0), max(self.y0, other.y0)
        x1, y1 = min(self.x1, other.x1), min(self.y1, other.y1)
        if x0 < x1 and y0 < y1:
            return Rect(x0, y0, x1, y1)
        return None


@dataclass
class Parcel:
    """A titled square of the grid: bounds + deed."""

    name: str
    bounds: Rect
    holder: str
    surveyed: str  # date string, e.g. "2026-03-01" — ordering by string
    surveyor: str


@dataclass
class Quarantine:
    """A subsecivum: a disputed strip, quarantined, never overwritten.

    claim_a / claim_b name the two colliding parcels. resolved_holder is
    None until adjudicated; resolution_rule records which policy decided.
    """

    bounds: Rect
    claim_a: str
    claim_b: str
    resolved_holder: Optional[str] = None
    resolution_rule: Optional[str] = None

    @property
    def resolved(self) -> bool:
        return self.resolved_holder is not None


class LandRegistry:
    """The titled grid: register parcels, quarantine collisions."""

    def __init__(self, grid_unit: str = "actus") -> None:
        self.grid_unit = grid_unit
        self._parcels: Dict[str, Parcel] = {}
        self.quarantines: List[Quarantine] = []

    def register(self, parcel: Parcel) -> List[Quarantine]:
        """Register a titled parcel.

        Overlaps with existing parcels become Quarantines and the
        overlapping claims are attached — the new parcel still registers,
        but the disputed strips are marked unassigned. Returns the new
        quarantines (empty list = clean survey).
        """
        if parcel.name in self._parcels:
            raise LandError(f"parcel {parcel.name!r} already titled")
        new_quarantines: List[Quarantine] = []
        for existing in self._parcels.values():
            strip = parcel.bounds.overlap(existing.bounds)
            if strip is not None:
                q = Quarantine(bounds=strip, claim_a=existing.name, claim_b=parcel.name)
                self.quarantines.append(q)
                new_quarantines.append(q)
        self._parcels[parcel.name] = parcel
        return new_quarantines

    def adjudicate(
        self,
        quarantine: Quarantine,
        rule: Optional[Callable[[Parcel, Parcel], Parcel]] = None,
        rule_name: str = "earliest survey wins",
    ) -> Parcel:
        """Resolve a quarantined strip by a stated rule.

        Default rule: the earlier-surveyed parcel wins. The rule's name is
        recorded on the quarantine so the decision stays auditable.
        """
        if quarantine.resolved:
            raise LandError("quarantine already adjudicated")
        a = self._parcels[quarantine.claim_a]
        b = self._parcels[quarantine.claim_b]
        winner = (
            rule(a, b) if rule is not None else (a if a.surveyed <= b.surveyed else b)
        )
        quarantine.resolved_holder = winner.holder
        quarantine.resolution_rule = rule_name
        return winner

    def lookup(self, x: int, y: int) -> Tuple[str, Optional[str]]:
        """Who owns point (x, y)?

        Returns (status, holder): ("titled", holder), ("disputed", None)
        when the point falls in an unresolved quarantine, or ("open", None)
        for unclaimed land.
        """
        for q in self.quarantines:
            if not q.resolved and q.bounds.contains(x, y):
                return ("disputed", None)
        for parcel in self._parcels.values():
            if parcel.bounds.contains(x, y):
                return ("titled", parcel.holder)
        return ("open", None)

    def parcels(self) -> List[Parcel]:
        return list(self._parcels.values())

    def open_quarantines(self) -> List[Quarantine]:
        return [q for q in self.quarantines if not q.resolved]
