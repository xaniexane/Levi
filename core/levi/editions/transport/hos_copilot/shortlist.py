"""Legally-runnable shortlist: rank, never auto-accept.

:func:`build_shortlist` pairs board offers with driver clock snapshots,
keeps only the pairs whose projection is ``legal``, and ranks them
deterministically (deadhead ascending, rate-per-mile descending).

There is deliberately no ``accept()`` / ``tender()`` / ``dispatch()``
method anywhere in this module: the shortlist is ranked data, and a
human binds the contract. A test asserts the method does not exist.
Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from .clocks import DriverClock
from .projection import Projection, RoutePlan, project


@dataclass(frozen=True)
class LoadOffer:
    """One board offer, normalized into a load card."""

    offer_id: str
    origin: str
    destination: str
    route: RoutePlan
    rate_usd: float
    equipment: str  # dry van | reefer | flatbed | tanker | ...

    @property
    def rpm(self) -> float:
        """Rate per mile — the ranking's second key."""
        miles = self.route.total_miles
        return self.rate_usd / miles if miles > 0 else 0.0


@dataclass(frozen=True)
class Candidate:
    """One legal driver/load pairing, with its projection attached."""

    driver_id: str
    offer_id: str
    projection: Projection
    deadhead_miles: float
    rpm: float


@dataclass(frozen=True)
class Shortlist:
    """The ranked result. Data, not an action."""

    candidates: Tuple[Candidate, ...]
    # Structural guards — a human binds every load, always.
    requires_human_accept: bool = True
    auto_accept: bool = False
    advisory_only: bool = True


def build_shortlist(
    offers: Sequence[LoadOffer],
    clocks: Sequence[DriverClock],
    deadhead_miles: Mapping[Tuple[str, str], float],
) -> Shortlist:
    """Rank the legally-runnable driver/load pairs.

    ``deadhead_miles`` maps (driver_id, offer_id) -> empty miles to the
    pickup. Pairs missing a deadhead entry are treated as unreachable
    (infinite deadhead) — never silently ranked.
    """
    candidates: List[Candidate] = []
    for clock in clocks:
        for offer in offers:
            projection = project(clock, offer.route)
            if not projection.legal:
                continue  # a fatigued pairing never appears on the board
            dh = deadhead_miles.get((clock.driver_id, offer.offer_id))
            if dh is None:
                continue
            candidates.append(
                Candidate(
                    driver_id=clock.driver_id,
                    offer_id=offer.offer_id,
                    projection=projection,
                    deadhead_miles=dh,
                    rpm=offer.rpm,
                )
            )
    # Deterministic ranking: least deadhead first, then best rate-per-mile.
    # (driver_id, offer_id) breaks any remaining tie for total determinism.
    candidates.sort(
        key=lambda c: (c.deadhead_miles, -c.rpm, c.driver_id, c.offer_id)
    )
    return Shortlist(candidates=tuple(candidates))


def shortlist_summary(shortlist: Shortlist) -> List[Dict[str, object]]:
    """Plain-data view for the dispatcher UI / morning brief."""
    rows = []
    for c in shortlist.candidates:
        rows.append(
            {
                "driver_id": c.driver_id,
                "offer_id": c.offer_id,
                "deadhead_miles": round(c.deadhead_miles, 1),
                "rpm_usd": round(c.rpm, 2),
                "drive_hrs": round(c.projection.drive_hrs, 2),
                "breaks": c.projection.breaks_inserted,
                "flags": [f.message for f in c.projection.flags],
                "requires_human_accept": shortlist.requires_human_accept,
            }
        )
    return rows
