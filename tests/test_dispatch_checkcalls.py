"""Tests for hands-off check calls + POD handoffs.

Hermetic: tmp ledger, simulated channel, explicit timestamps. Run from zero:
    cd ~/workspace/levi && python3 -m pytest -q tests/test_dispatch_checkcalls.py

Detention math check: 3.5h dwell, 2.0h free, $75/h -> 1.5h over -> 2h billed
-> 15000 cents.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.dispatch import (
    CheckCallEngine,
    CheckCallRefusal,
    Channel,
    ChannelReceipt,
    DetentionPolicy,
    DispatcherTwin,
    DispatchLedger,
    LoadStatus,
    SimulatedChannel,
)

T0 = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def setup(tmp_path):
    ledger = DispatchLedger(tmp_path / "test.db")
    twin = DispatcherTwin(ledger)
    driver, _ = twin.register_driver("Maya R.", phone="555-0100", home_base="Springfield")
    truck, _ = twin.register_truck("UNIT-1")
    load, _ = twin.book_load(
        "LD-100",
        origin="Springfield",
        destination="Chicago",
        pickup_date="2026-09-22",
        delivery_date="2026-09-23",
    )
    twin.offer_load(load.id, driver.id, truck.id)
    twin.accept_offer(load.id, rate_cents=180000)
    return ledger, twin, driver, truck, load


def _engine(ledger, **kw):
    return CheckCallEngine(ledger, SimulatedChannel(), **kw)


def test_full_handoff_flow_no_user_input(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)

    engine.mark_picked_up(load.id, at=T0)
    engine.arrive(load.id, "pickup", "Springfield yard", at=T0)
    depart_at = T0 + timedelta(hours=3, minutes=30)
    engine.depart(load.id, "pickup", at=depart_at)
    engine.arrive(load.id, "delivery", "Chicago DC", at=depart_at + timedelta(hours=6))
    engine.receive_pod(load.id, signed_by="J. Doe", document_ref="BOL-7788")

    final = ledger.get_load(load.id)
    assert final.status == LoadStatus.DELIVERED
    assert engine.pod_complete(load.id)
    assert engine.detention_due_cents(load.id) == 15000

    # every notification is labeled simulated; nothing real was sent
    assert engine.channel.sent, "expected simulated check-call messages"
    assert all(r.channel == "simulated" for r in engine.channel.sent)
    assert all(m.startswith("[SIMULATED]") for m in (r.message for r in engine.channel.sent))


def test_detention_free_time_not_charged(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    engine.mark_picked_up(load.id, at=T0)
    engine.arrive(load.id, "pickup", "Springfield yard", at=T0)
    engine.depart(load.id, "pickup", at=T0 + timedelta(hours=1, minutes=30))
    assert engine.detention_due_cents(load.id) == 0


def test_depart_before_arrive_refused(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    with pytest.raises(CheckCallRefusal):
        engine.depart(load.id, "pickup", at=T0)


def test_double_arrival_refused(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    engine.arrive(load.id, "pickup", "Springfield yard", at=T0)
    with pytest.raises(CheckCallRefusal):
        engine.arrive(load.id, "pickup", "Springfield yard", at=T0)


def test_pod_before_delivery_refused(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    with pytest.raises(CheckCallRefusal):
        engine.receive_pod(load.id, signed_by="J. Doe")


def test_double_pod_refused(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    engine.mark_picked_up(load.id, at=T0)
    engine.arrive(load.id, "pickup", "Springfield yard", at=T0)
    engine.depart(load.id, "pickup", at=T0 + timedelta(minutes=30))
    engine.arrive(load.id, "delivery", "Chicago DC", at=T0 + timedelta(hours=8))
    engine.receive_pod(load.id, signed_by="J. Doe")
    with pytest.raises(CheckCallRefusal):
        engine.receive_pod(load.id, signed_by="J. Doe")


def test_illegal_lifecycle_transition_blocked(setup) -> None:
    # mark_picked_up from IN_TRANSIT must be refused by the allowed_next guard
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    engine = _engine(ledger)
    engine.mark_picked_up(load.id, at=T0)
    engine.arrive(load.id, "pickup", "yard", at=T0)
    engine.depart(load.id, "pickup", at=T0 + timedelta(minutes=30))
    assert ledger.get_load(load.id).status == LoadStatus.IN_TRANSIT
    with pytest.raises(CheckCallRefusal):
        engine.mark_picked_up(load.id, at=T0)


def test_only_simulated_channel_approved(setup) -> None:
    ledger, *_ = setup

    class FakeRealChannel(Channel):
        kind = "sms"

        def send(self, recipient: str, message: str) -> ChannelReceipt:
            raise AssertionError("must never be called")

    with pytest.raises(CheckCallRefusal):
        CheckCallEngine(ledger, FakeRealChannel())


def test_custom_detention_policy(setup) -> None:
    ledger, twin, driver, truck, load = setup
    twin.dispatch_load(load.id)
    policy = DetentionPolicy(free_hours=1.0, rate_cents_per_hour=10000)
    engine = _engine(ledger, policy=policy)
    engine.mark_picked_up(load.id, at=T0)
    engine.arrive(load.id, "pickup", "yard", at=T0)
    engine.depart(load.id, "pickup", at=T0 + timedelta(hours=2, minutes=5))
    # 1h05m over -> 2h billed at $100 = 20000
    assert engine.detention_due_cents(load.id) == 20000
