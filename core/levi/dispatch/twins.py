"""The paired mind of the dispatch board (KFX2 workstream DISPATCH).

Two twins, one board:

- :class:`DispatcherTwin` — the proposer. It is the only side that mutates
  the ledger (register, book, offer, transition). It never moves a load
  without the verifier's countersign.
- :class:`VerifierTwin` — the checker. It never mutates anything. It
  validates every lifecycle transition, every offer move, every schedule
  assignment, and the receipt chain itself. When something is wrong it
  raises :class:`DispatchRefusal` with a plain-language reason — the
  operation stops honestly instead of corrupting the book.

This is the "2 among 0s and 1s" as an operational pattern: their
centralized cloud TMS is one mind with all the power; ours is a pair
that checks each other locally, needing the giants never.
"""

from __future__ import annotations

from datetime import date

from .ledger import DispatchLedger, Driver, Load, Truck, new_id
from .lifecycle import (
    OFFER_TRANSITIONS,
    TRANSITIONS,
    LoadStatus,
    OfferState,
    Readiness,
    ScheduleFit,
)
from .receipts import Receipt, verify_chain

TWIN_A = "dispatcher"
TWIN_B = "verifier"

#: Days of slack between a driver's loads before the verifier calls the
#: fit TIGHT instead of CLEAR. Under this gap the squeeze is flagged on
#: the receipt so the dispatcher sees it — honest, not hidden.
TIGHT_BUFFER_DAYS = 1


class DispatchRefusal(Exception):
    """The verifier refused an operation. Carries the plain reason.

    A refusal is a first-class outcome, not an exception to be swallowed:
    the caller is expected to show it to the dispatcher as-is.
    """


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def ranges_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """True when two [pickup, delivery] ranges overlap (inclusive)."""
    return _parse(a_start) <= _parse(b_end) and _parse(b_start) <= _parse(a_end)


def gap_days(a_start: str, a_end: str, b_start: str, b_end: str) -> int:
    """Days between two non-overlapping ranges (>= 0). Callers must check
    overlap first."""
    if _parse(a_end) < _parse(b_start):
        return (_parse(b_start) - _parse(a_end)).days
    return (_parse(a_start) - _parse(b_end)).days


class VerifierTwin:
    """Checks everything, mutates nothing."""

    name = TWIN_B

    def __init__(self, ledger: DispatchLedger) -> None:
        self.ledger = ledger

    # -- lifecycle -------------------------------------------------------
    def check_transition(self, load: Load, to: LoadStatus) -> None:
        if to not in TRANSITIONS[load.status]:
            raise DispatchRefusal(
                f"refused: load {load.reference} cannot move "
                f"{load.status.value} -> {to.value}"
            )

    def check_offer(self, load: Load, to: OfferState) -> None:
        if to not in OFFER_TRANSITIONS[load.offer_state]:
            raise DispatchRefusal(
                f"refused: offer for load {load.reference} cannot move "
                f"{load.offer_state.value} -> {to.value}"
            )

    def check_dispatch_ready(self, load: Load) -> str | None:
        """Return a warning note for CONDITIONAL, None for READY.

        Raises DispatchRefusal for BLOCKED, for offers that are not
        ACCEPTED, and for missing/inactive crew or equipment.
        """
        if load.offer_state != OfferState.ACCEPTED:
            raise DispatchRefusal(
                f"refused: load {load.reference} offer is "
                f"'{load.offer_state.value}', not accepted — dispatch blocked"
            )
        if load.readiness == Readiness.BLOCKED:
            raise DispatchRefusal(
                f"refused: load {load.reference} is missing route or dates — "
                "close the gap before dispatch"
            )
        driver = self.ledger.get_driver(load.driver_id or "")
        if driver is None or not driver.active:
            raise DispatchRefusal(
                f"refused: load {load.reference} has no active driver assigned"
            )
        truck = self.ledger.get_truck(load.truck_id or "")
        if truck is None or not truck.active:
            raise DispatchRefusal(
                f"refused: load {load.reference} has no active truck assigned"
            )
        if load.readiness == Readiness.CONDITIONAL:
            return (
                f"conditional dispatch: load {load.reference} dispatched while "
                f"readiness was 'conditional' — flagged for dispatcher review"
            )
        return None

    # -- scheduling --------------------------------------------------------
    def check_schedule_fit(
        self,
        driver_id: str,
        load: Load,
        *,
        buffer_days: int = TIGHT_BUFFER_DAYS,
    ) -> ScheduleFit:
        """Ternary fit of a load against a driver's active schedule."""
        for other in self.ledger.active_loads_for_driver(driver_id):
            if other.id == load.id:
                continue
            if ranges_overlap(
                load.pickup_date,
                load.delivery_date,
                other.pickup_date,
                other.delivery_date,
            ):
                return ScheduleFit.CONFLICT
            if (
                gap_days(
                    load.pickup_date,
                    load.delivery_date,
                    other.pickup_date,
                    other.delivery_date,
                )
                <= buffer_days
            ):
                return ScheduleFit.TIGHT
        return ScheduleFit.CLEAR

    def check_assignment(self, load: Load, driver_id: str) -> ScheduleFit:
        fit = self.check_schedule_fit(driver_id, load)
        if fit == ScheduleFit.CONFLICT:
            raise DispatchRefusal(
                f"refused: driver {driver_id} already has an overlapping "
                f"active load — cannot take {load.reference}"
            )
        return fit

    # -- chain ---------------------------------------------------------------
    def check_chain(self, load_id: str | None = None) -> None:
        ok, reason = verify_chain(self.ledger.receipt_chain(load_id))
        if not ok:
            raise DispatchRefusal(f"refused: receipt chain broken — {reason}")


class DispatcherTwin:
    """Proposes and mutates — only with the verifier's countersign."""

    name = TWIN_A

    def __init__(
        self, ledger: DispatchLedger, verifier: VerifierTwin | None = None
    ) -> None:
        self.ledger = ledger
        self.verifier = verifier or VerifierTwin(ledger)

    # -- internals ---------------------------------------------------------
    def _receipt(
        self,
        *,
        load_id: str,
        action: str,
        from_state: str = "",
        to_state: str = "",
        details: dict | None = None,
    ) -> Receipt:
        receipt = Receipt.create(
            seq=self.ledger.next_receipt_seq(),
            load_id=load_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
            prev_hash=self.ledger.last_receipt_hash(),
            twin_a=self.name,
            twin_b=self.verifier.name,
        )
        return self.ledger.record_receipt(receipt)

    def _move(
        self, load: Load, to: LoadStatus, action: str, details: dict | None = None
    ) -> tuple[Load, Receipt]:
        self.verifier.check_transition(load, to)
        from_state = load.status.value
        load.status = to
        self.ledger.update_load(load)
        receipt = self._receipt(
            load_id=load.id,
            action=action,
            from_state=from_state,
            to_state=to.value,
            details=details,
        )
        return load, receipt

    # -- registry ------------------------------------------------------------
    def register_driver(
        self, name: str, phone: str = "", home_base: str = ""
    ) -> tuple[Driver, Receipt]:
        if not name.strip():
            raise DispatchRefusal("refused: driver needs a name")
        driver = self.ledger.add_driver(
            Driver(
                id=new_id("drv"), name=name.strip(), phone=phone, home_base=home_base
            )
        )
        receipt = self._receipt(
            load_id=driver.id,
            action="driver.registered",
            details={"name": driver.name, "home_base": driver.home_base},
        )
        return driver, receipt

    def register_truck(
        self, unit_number: str, equipment: str = "dry_van"
    ) -> tuple[Truck, Receipt]:
        if not unit_number.strip():
            raise DispatchRefusal("refused: truck needs a unit number")
        truck = self.ledger.add_truck(
            Truck(
                id=new_id("trk"), unit_number=unit_number.strip(), equipment=equipment
            )
        )
        receipt = self._receipt(
            load_id=truck.id,
            action="truck.registered",
            details={"unit_number": truck.unit_number, "equipment": truck.equipment},
        )
        return truck, receipt

    # -- loads -----------------------------------------------------------------
    def book_load(
        self,
        reference: str,
        *,
        origin: str = "",
        destination: str = "",
        pickup_date: str = "",
        delivery_date: str = "",
        rate_cents: int = 0,
        notes: str = "",
    ) -> tuple[Load, Receipt]:
        if not reference.strip():
            raise DispatchRefusal("refused: load needs a reference")
        if (
            pickup_date
            and delivery_date
            and _parse(pickup_date) > _parse(delivery_date)
        ):
            raise DispatchRefusal(
                f"refused: load {reference} pickup date is after its delivery date"
            )
        load = self.ledger.add_load(
            Load(
                id=new_id("lod"),
                reference=reference.strip(),
                origin=origin,
                destination=destination,
                pickup_date=pickup_date,
                delivery_date=delivery_date,
                rate_cents=rate_cents,
                notes=notes,
            )
        )
        receipt = self._receipt(
            load_id=load.id,
            action="load.booked",
            to_state=LoadStatus.BOOKED.value,
            details={
                "reference": load.reference,
                "lane": f"{load.origin} -> {load.destination}",
                "readiness": load.readiness.value,
            },
        )
        return load, receipt

    # -- offers (ternary) ----------------------------------------------------------
    def offer_load(
        self, load_id: str, driver_id: str, truck_id: str
    ) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        if load.status != LoadStatus.BOOKED:
            raise DispatchRefusal(
                f"refused: only a booked load can be offered "
                f"({load.reference} is {load.status.value})"
            )
        driver = self.ledger.get_driver(driver_id)
        if driver is None or not driver.active:
            raise DispatchRefusal(f"refused: driver {driver_id} unknown or inactive")
        truck = self.ledger.get_truck(truck_id)
        if truck is None or not truck.active:
            raise DispatchRefusal(f"refused: truck {truck_id} unknown or inactive")
        load.driver_id = driver_id
        load.truck_id = truck_id
        if load.offer_state == OfferState.DECLINED:
            self.verifier.check_offer(load, OfferState.NEGOTIATING)
            load.offer_state = OfferState.NEGOTIATING
        fit = self.verifier.check_assignment(load, driver_id)
        self.ledger.update_load(load)
        details: dict = {
            "reference": load.reference,
            "driver": driver.name,
            "truck": truck.unit_number,
            "offer_state": load.offer_state.value,
            "readiness": load.readiness.value,
            "schedule_fit": fit.value,
        }
        if fit == ScheduleFit.TIGHT:
            details["warning"] = (
                "tight schedule: this load sits within "
                f"{TIGHT_BUFFER_DAYS} day(s) of another active load for "
                f"{driver.name} — dispatcher acknowledged the squeeze"
            )
        receipt = self._receipt(load_id=load.id, action="offer.opened", details=details)
        return load, receipt

    def accept_offer(
        self, load_id: str, rate_cents: int | None = None
    ) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        self.verifier.check_offer(load, OfferState.ACCEPTED)
        if rate_cents is not None:
            if rate_cents < 0:
                raise DispatchRefusal("refused: rate cannot be negative")
            load.rate_cents = rate_cents  # counter-offer settled into the book
        load.offer_state = OfferState.ACCEPTED
        self.ledger.update_load(load)
        receipt = self._receipt(
            load_id=load.id,
            action="offer.accepted",
            details={"reference": load.reference, "rate_cents": load.rate_cents},
        )
        return load, receipt

    def decline_offer(self, load_id: str, reason: str = "") -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        self.verifier.check_offer(load, OfferState.DECLINED)
        load.offer_state = OfferState.DECLINED
        self.ledger.update_load(load)
        receipt = self._receipt(
            load_id=load.id,
            action="offer.declined",
            details={"reference": load.reference, "reason": reason},
        )
        return load, receipt

    # -- lifecycle ---------------------------------------------------------------
    def dispatch_load(self, load_id: str) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        warning = self.verifier.check_dispatch_ready(load)
        details = {"reference": load.reference}
        if warning:
            details["warning"] = warning
        return self._move(load, LoadStatus.DISPATCHED, "load.dispatched", details)

    def record_pickup(self, load_id: str) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        return self._move(
            load, LoadStatus.PICKED_UP, "load.picked_up", {"reference": load.reference}
        )

    def record_departure(self, load_id: str) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        return self._move(
            load, LoadStatus.IN_TRANSIT, "load.departed", {"reference": load.reference}
        )

    def record_delivery(self, load_id: str) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        return self._move(
            load, LoadStatus.DELIVERED, "load.delivered", {"reference": load.reference}
        )

    def record_invoice(self, load_id: str) -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        return self._move(
            load,
            LoadStatus.INVOICED,
            "load.invoiced",
            {"reference": load.reference, "rate_cents": load.rate_cents},
        )

    def cancel_load(self, load_id: str, reason: str = "") -> tuple[Load, Receipt]:
        load = self._must_get_load(load_id)
        return self._move(
            load,
            LoadStatus.CANCELLED,
            "load.cancelled",
            {"reference": load.reference, "reason": reason},
        )

    # -- helpers -------------------------------------------------------------------
    def _must_get_load(self, load_id: str) -> Load:
        load = self.ledger.get_load(load_id)
        if load is None:
            raise DispatchRefusal(f"refused: load {load_id} not in the ledger")
        return load
