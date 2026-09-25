"""Hands-off check calls and proof-of-delivery handoffs.

The engine consumes arrival / departure / POD events and — with no user
input — updates the load lifecycle (through the existing ``allowed_next``
guard, never around it), accrues detention per the stated policy, and
notifies via a :class:`Channel`.

COMMS POSTURE: the only channel shipped is :class:`SimulatedChannel` —
in-memory, no socket, no network. No message can reach a real driver:
there is no other Channel implementation in this package, and the engine
refuses to run against an unknown channel type. Real channels
(SMS / WhatsApp / Messenger) plug in later behind the same ``Channel``
interface once the keeper provides driver contacts and approves the
channel; until then, everything is simulated and labeled as such.

Detention policy (stated): ``free_hours`` of dwell per stop are free;
beyond that, whole hours (rounded up) bill at ``rate_cents_per_hour``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil

from .ledger import DispatchLedger, Load
from .lifecycle import LoadStatus, allowed_next


class CheckCallRefusal(ValueError):
    """An event the engine will not apply (bad order, bad state)."""


# -- channels --------------------------------------------------------------


@dataclass(frozen=True)
class ChannelReceipt:
    channel: str
    recipient: str
    message: str
    seq: int


class Channel(ABC):
    """Outbound driver-notification channel."""

    kind: str = "abstract"

    @abstractmethod
    def send(self, recipient: str, message: str) -> ChannelReceipt:
        """Deliver a notification; return its receipt."""


class SimulatedChannel(Channel):
    """In-memory stand-in. Records everything, delivers nothing.

    Every receipt is labeled ``simulated`` so a simulated message can
    never be mistaken for a real one downstream.
    """

    kind = "simulated"

    def __init__(self) -> None:
        self.sent: list[ChannelReceipt] = []
        self._seq = 0

    def send(self, recipient: str, message: str) -> ChannelReceipt:
        self._seq += 1
        receipt = ChannelReceipt(
            channel="simulated",
            recipient=recipient,
            message=f"[SIMULATED] {message}",
            seq=self._seq,
        )
        self.sent.append(receipt)
        return receipt


# -- policy + events --------------------------------------------------------


@dataclass(frozen=True)
class DetentionPolicy:
    free_hours: float = 2.0
    rate_cents_per_hour: int = 7500  # $75 / hour

    def charge_cents(self, dwell_hours: float) -> int:
        # MONEY LAW: pure arithmetic — dwell hours -> detention cents.
        # Computes and returns a number; no funds, no rails, no movement.
        overage = dwell_hours - self.free_hours
        if overage <= 0:
            return 0
        return ceil(overage - 1e-9) * self.rate_cents_per_hour


@dataclass
class StopRecord:
    arrived_at: str | None = None
    departed_at: str | None = None
    detention_cents: int = 0


@dataclass
class PodRecord:
    signed_by: str
    document_ref: str
    received_at: str


def _iso(at: datetime | None) -> str:
    return (at or datetime.now(timezone.utc)).isoformat()


def _hours_between(start_iso: str, end_iso: str) -> float:
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end - start).total_seconds() / 3600.0


# -- engine -----------------------------------------------------------------


class CheckCallEngine:
    """Hands-off check-call processor.

    Owns no network and no decisions beyond the stated policy: it records
    events, moves loads through lifecycle transitions the twin-pair rules
    already allow, accrues detention, and notifies the driver contact on
    file through the configured (simulated) channel.
    """

    def __init__(
        self,
        ledger: DispatchLedger,
        channel: Channel,
        policy: DetentionPolicy | None = None,
    ) -> None:
        if not isinstance(channel, SimulatedChannel):
            # Until a real channel is keeper-approved, only the simulator
            # exists. Refusing here keeps a future half-wired channel from
            # silently becoming real.
            raise CheckCallRefusal(
                f"only the simulated channel is approved; got {channel.kind!r}"
            )
        self.ledger = ledger
        self.channel = channel
        self.policy = policy or DetentionPolicy()
        self.stops: dict[str, dict[str, StopRecord]] = {}  # load_id -> stop -> record
        self.pods: dict[str, PodRecord] = {}
        self.events: list[dict] = []

    # -- internals ----------------------------------------------------------

    def _load(self, load_id: str) -> Load:
        load = self.ledger.get_load(load_id)
        if load is None:
            raise CheckCallRefusal(f"unknown load {load_id!r}")
        return load

    def _transition(self, load: Load, to: LoadStatus) -> None:
        if to not in allowed_next(load.status):
            raise CheckCallRefusal(
                f"illegal transition {load.status.value} -> {to.value}"
            )
        load.status = to
        self.ledger.update_load(load)

    def _stop(self, load_id: str, stop: str) -> StopRecord:
        return self.stops.setdefault(load_id, {}).setdefault(stop, StopRecord())

    def _notify(self, load: Load, message: str) -> ChannelReceipt:
        driver = self.ledger.get_driver(load.driver_id or "")
        recipient = driver.phone if driver and driver.phone else (
            driver.name if driver else "unassigned"
        )
        return self.channel.send(recipient, f"Load {load.reference}: {message}")

    def _log(self, **entry: object) -> None:
        self.events.append({"at": _iso(None), **entry})

    # -- check calls ----------------------------------------------------------

    def arrive(
        self, load_id: str, stop: str, location: str, at: datetime | None = None
    ) -> ChannelReceipt:
        """Driver arrived at a stop ('pickup' or 'delivery'). Hands-off."""
        if stop not in ("pickup", "delivery"):
            raise CheckCallRefusal(f"unknown stop {stop!r}")
        load = self._load(load_id)
        record = self._stop(load_id, stop)
        if record.arrived_at is not None:
            raise CheckCallRefusal(f"already arrived at {stop} for {load_id!r}")
        record.arrived_at = _iso(at)
        if stop == "delivery" and load.status == LoadStatus.IN_TRANSIT:
            self._transition(load, LoadStatus.DELIVERED)
        self._log(type="arrival", load_id=load_id, stop=stop, location=location)
        return self._notify(load, f"arrived {location} ({stop})")

    def depart(
        self, load_id: str, stop: str, at: datetime | None = None
    ) -> ChannelReceipt:
        """Driver departed a stop. Computes dwell, accrues detention."""
        load = self._load(load_id)
        record = self._stop(load_id, stop)
        if record.arrived_at is None:
            raise CheckCallRefusal(f"cannot depart {stop}: no arrival recorded")
        if record.departed_at is not None:
            raise CheckCallRefusal(f"already departed {stop} for {load_id!r}")
        record.departed_at = _iso(at)
        dwell = _hours_between(record.arrived_at, record.departed_at)
        record.detention_cents = self.policy.charge_cents(dwell)
        if stop == "pickup" and load.status == LoadStatus.PICKED_UP:
            self._transition(load, LoadStatus.IN_TRANSIT)
        self._log(
            type="departure",
            load_id=load_id,
            stop=stop,
            dwell_hours=round(dwell, 2),
            detention_cents=record.detention_cents,
        )
        note = f"departed {stop} after {dwell:.1f}h dwell"
        if record.detention_cents:
            note += f" — detention ${record.detention_cents / 100:.2f} accruing"
        return self._notify(load, note)

    def mark_picked_up(self, load_id: str, at: datetime | None = None) -> ChannelReceipt:
        """Goods loaded at pickup: booked/dispatched -> picked_up, hands-off."""
        load = self._load(load_id)
        if load.status not in (LoadStatus.BOOKED, LoadStatus.DISPATCHED):
            raise CheckCallRefusal(
                f"pickup only from booked/dispatched, not {load.status.value}"
            )
        self._transition(load, LoadStatus.PICKED_UP)
        self._log(type="picked_up", load_id=load_id)
        return self._notify(load, "picked up — goods aboard")

    # -- POD handoff ------------------------------------------------------------

    def receive_pod(
        self,
        load_id: str,
        signed_by: str,
        document_ref: str = "",
        at: datetime | None = None,
    ) -> ChannelReceipt:
        """Proof of delivery received: closes the loop, hands off paperwork.

        Requires the load to have arrived at delivery (status DELIVERED).
        The POD is recorded with signer + document reference; the handoff
        notice goes out on the channel; the load is then ready for the
        dispatcher twin to invoice — this engine never invoices.
        """
        load = self._load(load_id)
        if load.status != LoadStatus.DELIVERED:
            raise CheckCallRefusal(
                f"POD only after delivery arrival, not {load.status.value}"
            )
        if load_id in self.pods:
            raise CheckCallRefusal(f"POD already recorded for {load_id!r}")
        self.pods[load_id] = PodRecord(
            signed_by=signed_by, document_ref=document_ref, received_at=_iso(at)
        )
        self._log(
            type="pod",
            load_id=load_id,
            signed_by=signed_by,
            document_ref=document_ref,
        )
        return self._notify(
            load, f"POD received — signed by {signed_by}, ready for invoicing"
        )

    # -- reads ------------------------------------------------------------------

    def detention_due_cents(self, load_id: str) -> int:
        """Total detention accrued across stops, in cents."""
        return sum(r.detention_cents for r in self.stops.get(load_id, {}).values())

    def pod_complete(self, load_id: str) -> bool:
        return load_id in self.pods
