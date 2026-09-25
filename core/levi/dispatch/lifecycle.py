"""LEVI Dispatch — load lifecycle and ternary states (KFX2 workstream DISPATCH).

Phase 1 milestone: the local dispatch board. This module holds the load
status lifecycle plus the ternary third-states the giants skip:

- OfferState: ACCEPTED / DECLINED / **NEGOTIATING** — the third state
  between yes and no. Real dispatching lives in the middle: the driver
  counter-offers, the dispatcher adjusts the rate, nobody has "failed".
- Readiness: READY / CONDITIONAL / **BLOCKED** is a binary pair with a
  third real state in the middle — CONDITIONAL: dispatchable, but the
  receipt must say what was missing.
- ScheduleFit: CLEAR / **TIGHT** / CONFLICT — the third state between a
  clean schedule and a clash: loads that don't overlap but sit close
  enough that the dispatcher should see the squeeze.

No ELD, no FMCSA/DOT compliance claim is made anywhere in this module.
See :data:`levi.dispatch.ELD_DISCLAIMER`.
"""

from __future__ import annotations

from enum import Enum


class LoadStatus(str, Enum):
    BOOKED = "booked"
    DISPATCHED = "dispatched"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset({LoadStatus.INVOICED, LoadStatus.CANCELLED})

#: Allowed forward transitions. The lifecycle only moves forward; the
#: verifier twin enforces this and refuses anything not listed.
TRANSITIONS: dict[LoadStatus, frozenset[LoadStatus]] = {
    LoadStatus.BOOKED: frozenset({LoadStatus.DISPATCHED, LoadStatus.CANCELLED}),
    LoadStatus.DISPATCHED: frozenset({LoadStatus.PICKED_UP, LoadStatus.CANCELLED}),
    LoadStatus.PICKED_UP: frozenset({LoadStatus.IN_TRANSIT}),
    LoadStatus.IN_TRANSIT: frozenset({LoadStatus.DELIVERED}),
    LoadStatus.DELIVERED: frozenset({LoadStatus.INVOICED}),
    LoadStatus.INVOICED: frozenset(),
    LoadStatus.CANCELLED: frozenset(),
}


def allowed_next(status: LoadStatus) -> frozenset[LoadStatus]:
    """Return the statuses ``status`` may legally move to."""
    return TRANSITIONS[status]


def is_terminal(status: LoadStatus) -> bool:
    return status in TERMINAL_STATUSES


class OfferState(str, Enum):
    """Ternary load-offer state: the third state NEGOTIATING sits between
    the binary yes/no the incumbents' load boards reduce offers to."""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    NEGOTIATING = "negotiating"


#: Offer moves: an offer opens in NEGOTIATING; the driver settles it to
#: ACCEPTED or DECLINED; a declined offer can be re-opened for another
#: round rather than dying as a binary "no".
OFFER_TRANSITIONS: dict[OfferState, frozenset[OfferState]] = {
    OfferState.NEGOTIATING: frozenset({OfferState.ACCEPTED, OfferState.DECLINED}),
    OfferState.ACCEPTED: frozenset(),
    OfferState.DECLINED: frozenset({OfferState.NEGOTIATING}),
}


class Readiness(str, Enum):
    """Ternary load readiness before dispatch.

    READY: everything present. CONDITIONAL: dispatchable, but the receipt
    records what was missing (honest, not hidden). BLOCKED: the verifier
    refuses dispatch until the gap is closed.
    """

    READY = "ready"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class ScheduleFit(str, Enum):
    """Ternary schedule fit for assigning a load to a driver.

    CLEAR: no overlap with the driver's active loads. TIGHT: no overlap,
    but the gap to a neighboring load is under the buffer — allowed, and
    the receipt flags it so the dispatcher sees the squeeze. CONFLICT:
    hard overlap — the verifier refuses.
    """

    CLEAR = "clear"
    TIGHT = "tight"
    CONFLICT = "conflict"


def compute_readiness(
    *,
    origin: str | None,
    destination: str | None,
    pickup_date: str | None,
    delivery_date: str | None,
    driver_id: str | None,
    truck_id: str | None,
) -> Readiness:
    """Derive a load's readiness from what is known about it.

    BLOCKED when the load cannot be planned (no route or no dates).
    CONDITIONAL when it can be planned but the crew/equipment is not
    pinned down yet. READY when fully specified.
    """
    if not origin or not destination or not pickup_date or not delivery_date:
        return Readiness.BLOCKED
    if not driver_id or not truck_id:
        return Readiness.CONDITIONAL
    return Readiness.READY
