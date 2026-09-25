"""Tests for LEVI Dispatch Phase 1 — The Board (KFX2 workstream DISPATCH).

Hermetic: every test uses a tmp_path ledger; nothing touches HOME or the
network. Run from zero:
    cd ~/workspace/levi && python3 -m pytest -q tests/test_dispatch_board.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.dispatch import (
    ELD_DISCLAIMER,
    DispatcherTwin,
    DispatchLedger,
    DispatchRefusal,
    Load,
    LoadStatus,
    OfferState,
    Readiness,
    Receipt,
    ScheduleFit,
    board_conflicts,
    honest_limits,
    new_id,
    render_board_text,
    verify_chain,
    week_board,
)


@pytest.fixture()
def ledger(tmp_path: Path) -> DispatchLedger:
    return DispatchLedger(tmp_path / "test.db")


@pytest.fixture()
def twins(ledger: DispatchLedger) -> DispatcherTwin:
    return DispatcherTwin(ledger)


def _crew(twins: DispatcherTwin):
    driver, _ = twins.register_driver("Maya R.", home_base="Springfield")
    truck, _ = twins.register_truck("T-101")
    return driver, truck


def _booked(twins: DispatcherTwin, ref="LD-1", **kw):
    defaults = dict(
        origin="Chicago",
        destination="Dallas",
        pickup_date="2026-09-21",
        delivery_date="2026-09-23",
        rate_cents=185000,
    )
    defaults.update(kw)
    load, _ = twins.book_load(ref, **defaults)
    return load


# -- lifecycle -----------------------------------------------------------------


def test_lifecycle_is_forward_only(twins: DispatcherTwin):
    load = _booked(twins)
    with pytest.raises(DispatchRefusal):
        twins.record_delivery(load.id)  # booked -> delivered is illegal


def test_terminal_states_are_final(twins: DispatcherTwin):
    load = _booked(twins)
    load, _ = twins.cancel_load(load.id, reason="shipper pulled it")
    assert load.status == LoadStatus.CANCELLED
    with pytest.raises(DispatchRefusal):
        twins.dispatch_load(load.id)


def test_full_lifecycle_end_to_end(twins: DispatcherTwin, ledger: DispatchLedger):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, r = twins.offer_load(load.id, driver.id, truck.id)
    assert load.offer_state == OfferState.NEGOTIATING
    load, r = twins.accept_offer(load.id)
    assert load.offer_state == OfferState.ACCEPTED
    load, r = twins.dispatch_load(load.id)
    assert load.status == LoadStatus.DISPATCHED
    load, _ = twins.record_pickup(load.id)
    assert load.status == LoadStatus.PICKED_UP
    load, _ = twins.record_departure(load.id)
    assert load.status == LoadStatus.IN_TRANSIT
    load, _ = twins.record_delivery(load.id)
    assert load.status == LoadStatus.DELIVERED
    load, r = twins.record_invoice(load.id)
    assert load.status == LoadStatus.INVOICED
    assert r.twin_a == "dispatcher" and r.twin_b == "verifier"
    assert r.from_state == "delivered" and r.to_state == "invoiced"

    ok, reason = verify_chain(ledger.receipt_chain())
    assert ok, reason
    assert len(ledger.receipt_chain()) == 10  # 2 crew + book + offer + accept + 5 moves


# -- offer ternary ----------------------------------------------------------------


def test_offer_starts_negotiating_not_binary(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)
    assert load.offer_state == OfferState.NEGOTIATING  # the third state


def test_declined_offer_can_be_reopened(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)
    load, _ = twins.decline_offer(load.id, reason="rate too low")
    assert load.offer_state == OfferState.DECLINED
    load, _ = twins.offer_load(load.id, driver.id, truck.id)  # re-open the round
    assert load.offer_state == OfferState.NEGOTIATING


def test_accept_twice_is_refused(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)
    load, _ = twins.accept_offer(load.id)
    with pytest.raises(DispatchRefusal):
        twins.accept_offer(load.id)


def test_dispatch_requires_accepted_offer(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)  # still negotiating
    with pytest.raises(DispatchRefusal):
        twins.dispatch_load(load.id)


def test_negative_rate_refused(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load = _booked(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)
    with pytest.raises(DispatchRefusal):
        twins.accept_offer(load.id, rate_cents=-50)


# -- readiness ternary ---------------------------------------------------------------


def test_blocked_load_cannot_dispatch(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    load, _ = twins.book_load("LD-X")  # no route, no dates
    assert load.readiness == Readiness.BLOCKED
    with pytest.raises(DispatchRefusal):
        twins.dispatch_load(load.id)


def test_conditional_becomes_ready_once_crewed(twins: DispatcherTwin):
    load = _booked(twins)  # route + dates, but no crew yet -> conditional
    assert load.readiness == Readiness.CONDITIONAL
    driver, truck = _crew(twins)
    load, _ = twins.offer_load(load.id, driver.id, truck.id)
    load, _ = twins.accept_offer(load.id)
    assert load.readiness == Readiness.READY  # crew pinned -> fully ready
    load, receipt = twins.dispatch_load(load.id)
    assert load.status == LoadStatus.DISPATCHED
    assert "warning" not in receipt.details


def test_verifier_flags_conditional_dispatch(twins: DispatcherTwin):
    """A load that ever reaches dispatch while CONDITIONAL gets its gap
    written onto the receipt — the honest middle state, not a silent pass."""
    driver, truck = _crew(twins)
    load = Load(
        id=new_id("lod"),
        reference="LD-COND",
        origin="Chicago",
        destination="Dallas",
        pickup_date="2026-09-21",
        delivery_date="2026-09-23",
        offer_state=OfferState.ACCEPTED,
        readiness=Readiness.CONDITIONAL,  # hand-built: provisional state
        driver_id=driver.id,
        truck_id=truck.id,
    )
    warning = twins.verifier.check_dispatch_ready(load)
    assert warning and "conditional" in warning


def test_backwards_dates_refused(twins: DispatcherTwin):
    with pytest.raises(DispatchRefusal):
        twins.book_load(
            "LD-BAD",
            origin="A",
            destination="B",
            pickup_date="2026-09-25",
            delivery_date="2026-09-21",
        )


# -- schedule-fit ternary -----------------------------------------------------------------


def _assigned(twins: DispatcherTwin, ref, driver_id, truck_id, pu, dl):
    load = _booked(twins, ref=ref, pickup_date=pu, delivery_date=dl)
    load, _ = twins.offer_load(load.id, driver_id, truck_id)
    load, _ = twins.accept_offer(load.id)
    load, _ = twins.dispatch_load(load.id)
    return load


def test_overlapping_load_is_conflict_and_refused(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    _assigned(twins, "LD-A", driver.id, truck.id, "2026-09-21", "2026-09-23")
    load_b = _booked(
        twins, ref="LD-B", pickup_date="2026-09-22", delivery_date="2026-09-24"
    )
    with pytest.raises(DispatchRefusal) as exc:
        twins.offer_load(load_b.id, driver.id, truck.id)
    assert "overlapping" in str(exc.value)


def test_back_to_back_load_is_tight_and_allowed(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    _assigned(twins, "LD-A", driver.id, truck.id, "2026-09-21", "2026-09-23")
    load_b = _booked(
        twins, ref="LD-B", pickup_date="2026-09-24", delivery_date="2026-09-26"
    )
    load_b, receipt = twins.offer_load(load_b.id, driver.id, truck.id)
    assert receipt.details["schedule_fit"] == ScheduleFit.TIGHT.value
    assert "warning" in receipt.details  # the squeeze is flagged, not hidden


def test_spaced_load_is_clear(twins: DispatcherTwin):
    driver, truck = _crew(twins)
    _assigned(twins, "LD-A", driver.id, truck.id, "2026-09-21", "2026-09-23")
    load_b = _booked(
        twins, ref="LD-B", pickup_date="2026-09-26", delivery_date="2026-09-28"
    )
    load_b, receipt = twins.offer_load(load_b.id, driver.id, truck.id)
    assert receipt.details["schedule_fit"] == ScheduleFit.CLEAR.value


# -- receipts ------------------------------------------------------------------------


def test_every_mutation_is_countersigned(twins: DispatcherTwin, ledger: DispatchLedger):
    driver, _ = twins.register_driver("Devon K.")
    chain = ledger.receipt_chain()
    assert chain and all(
        r.twin_a == "dispatcher" and r.twin_b == "verifier" for r in chain
    )
    ok, reason = verify_chain(chain)
    assert ok, reason


def test_tampered_receipt_is_detected():
    r = Receipt.create(
        seq=1, load_id="lod_x", action="load.booked", details={"reference": "LD-1"}
    )
    assert r.is_intact()
    tampered = Receipt(
        seq=r.seq,
        ts=r.ts,
        twin_a=r.twin_a,
        twin_b=r.twin_b,
        load_id=r.load_id,
        action=r.action,
        from_state=r.from_state,
        to_state=r.to_state,
        details={"reference": "LD-999"},  # altered
        prev_hash=r.prev_hash,
        hash=r.hash,
    )
    assert not tampered.is_intact()
    ok, reason = verify_chain([tampered])
    assert not ok and "altered" in reason


def test_broken_chain_link_is_detected(twins: DispatcherTwin, ledger: DispatchLedger):
    _crew(twins)
    _booked(twins)
    chain = ledger.receipt_chain()
    assert len(chain) >= 2
    ok, reason = verify_chain([c for i, c in enumerate(chain) if i != 1])  # drop one
    assert not ok
    assert reason  # honest about what failed


def test_verifier_can_audit_chain(twins: DispatcherTwin):
    _crew(twins)
    _booked(twins)
    twins.verifier.check_chain()  # raises nothing when intact


# -- ledger persistence ------------------------------------------------------------------


def test_ledger_survives_reopen(tmp_path: Path):
    db = tmp_path / "persist.db"
    twins_a = DispatcherTwin(DispatchLedger(db))
    driver, truck = _crew(twins_a)
    load = _booked(twins_a)

    twins_b = DispatcherTwin(DispatchLedger(db))
    again = twins_b.ledger.get_load(load.id)
    assert again is not None and again.reference == "LD-1"
    assert again.driver_id is None  # not yet offered
    assert twins_b.ledger.get_driver(driver.id).name == "Maya R."
    assert twins_b.ledger.get_truck(truck.id).unit_number == "T-101"
    ok, reason = verify_chain(twins_b.ledger.receipt_chain())
    assert ok, reason


# -- the board ---------------------------------------------------------------------------


def _seed_week(twins: DispatcherTwin):
    drivers, trucks = [], []
    for name in ["Maya R.", "Devon K.", "Priya S.", "Tom H.", "Alba M."]:
        d, _ = twins.register_driver(name)
        drivers.append(d)
    for unit in ["T-101", "T-102", "T-103", "T-104", "T-105"]:
        t, _ = twins.register_truck(unit)
        trucks.append(t)
    plan = [
        ("LD-2401", "2026-09-21", "2026-09-23"),
        ("LD-2402", "2026-09-22", "2026-09-24"),
        ("LD-2403", "2026-09-23", "2026-09-25"),
        ("LD-2404", "2026-09-21", "2026-09-22"),
        ("LD-2405", "2026-09-24", "2026-09-25"),
        ("LD-2406", "2026-09-26", "2026-09-27"),
    ]
    for i, (ref, pu, dl) in enumerate(plan):
        load = _booked(twins, ref=ref, pickup_date=pu, delivery_date=dl)
        load, _ = twins.offer_load(load.id, drivers[i % 5].id, trucks[i % 5].id)
        twins.accept_offer(load.id)
    return drivers


def test_five_truck_week_on_the_board(twins: DispatcherTwin, ledger: DispatchLedger):
    drivers = _seed_week(twins)
    board = week_board(ledger, "2026-09-21")
    assert set(board) == {d.id for d in drivers}
    maya = board[drivers[0].id]
    assert any("LD-2401" in cell for day in maya.values() for cell in day)
    assert "LD-2401" in ", ".join(maya["2026-09-22"])
    assert board_conflicts(ledger) == []


def test_terminal_loads_leave_the_board(twins: DispatcherTwin, ledger: DispatchLedger):
    drivers = _seed_week(twins)
    first = ledger.list_loads()[0]
    twins.dispatch_load(first.id)
    twins.record_pickup(first.id)
    twins.record_departure(first.id)
    twins.record_delivery(first.id)
    twins.record_invoice(first.id)
    board = week_board(ledger, "2026-09-21")
    assert not any(
        "LD-2401" in cell for day in board[drivers[0].id].values() for cell in day
    )


def test_board_conflicts_detects_imported_overlap(
    twins: DispatcherTwin, ledger: DispatchLedger
):
    """Overlaps the twin pair would refuse can still arrive via imported
    legacy data written straight to the ledger — the board must surface
    them honestly."""
    driver, truck = _crew(twins)
    ledger.add_load(
        Load(
            id=new_id("lod"),
            reference="LEGACY-1",
            pickup_date="2026-09-21",
            delivery_date="2026-09-23",
            driver_id=driver.id,
            truck_id=truck.id,
        )
    )
    ledger.add_load(
        Load(
            id=new_id("lod"),
            reference="LEGACY-2",
            pickup_date="2026-09-22",
            delivery_date="2026-09-24",
            driver_id=driver.id,
            truck_id=truck.id,
        )
    )
    clashes = board_conflicts(ledger)
    assert len(clashes) == 1
    assert clashes[0]["fit"] == ScheduleFit.CONFLICT.value
    assert {clashes[0]["load_a"], clashes[0]["load_b"]} == {"LEGACY-1", "LEGACY-2"}


def test_render_board_text(twins: DispatcherTwin, ledger: DispatchLedger):
    _seed_week(twins)
    text = render_board_text(ledger, "2026-09-21")
    assert "DISPATCH BOARD" in text
    assert "LD-2401" in text
    assert "Maya R." in text
    assert "no schedule conflicts." in text


# -- doctrines in code --------------------------------------------------------------------


def test_no_metering_hooks_anywhere():
    """The no-metering law is structural: no per-seat/per-vehicle/
    per-insight counters may exist in the dispatch package."""
    pkg = Path(__file__).resolve().parents[1] / "core" / "levi" / "dispatch"
    assert pkg.is_dir()
    banned = (
        "per_seat",
        "per-seat",
        "per_vehicle",
        "per-vehicle",
        "per_insight",
        "seat_price",
        "metered",
        "subscription",
    )
    hits = []
    for py in sorted(pkg.glob("*.py")):
        text = py.read_text().lower()
        for token in banned:
            if token in text:
                hits.append(f"{py.name}: {token}")
    assert not hits, f"metering hooks found: {hits}"


def test_honest_limits_name_the_eld_line():
    limits = honest_limits()
    assert any("ELD" in line for line in limits)
    assert "FMCSA" in ELD_DISCLAIMER and "not an ELD" in ELD_DISCLAIMER


def test_demo_cli_runs_offline(capsys):
    from levi.dispatch.__main__ import main

    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "DISPATCH BOARD" in out
    assert "receipt chain: INTACT" in out
    assert "honest limits:" in out
