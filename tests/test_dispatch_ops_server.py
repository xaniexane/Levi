"""Tests for the encrypted ops server.

Hermetic: tmp home dir, sealed state only. Run from zero:
    cd ~/workspace/levi && python3 -m pytest -q tests/test_dispatch_ops_server.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.dispatch import (
    DispatcherTwin,
    OpsAuth,
    OpsAuthError,
    OpsServer,
)

T0 = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)
PW = "correct horse battery staple"


def test_backend_is_reported(tmp_path) -> None:
    server = OpsServer(PW, tmp_path / "ops")
    assert server.backend in ("fernet", "stdlib-fallback")


def test_oauth_is_delegated_not_minted() -> None:
    # Canon: Cybrus is the security + OAuth layer. The ops server keeps no
    # credentials and mints no tokens; external OAuth lives in the broker.
    assert "cybrus" in OpsAuth.OAUTH_DELEGATE
    assert "oauth" in OpsAuth.OAUTH_DELEGATE


def test_sealed_state_is_opaque_on_disk(tmp_path) -> None:
    server = OpsServer(PW, tmp_path / "ops")
    twin = DispatcherTwin(server.ledger)
    twin.register_driver("Maya R.", phone="555-0100", home_base="Springfield")
    load, _ = twin.book_load("LD-SECRET-1", origin="Springfield", destination="Chicago")
    server.save()

    sealed = (tmp_path / "ops" / "ops_state.sealed").read_bytes()
    assert b"LD-SECRET-1" not in sealed
    assert b"Maya R." not in sealed
    assert b"555-0100" not in sealed


def test_state_round_trip(tmp_path) -> None:
    server = OpsServer(PW, tmp_path / "ops")
    twin = DispatcherTwin(server.ledger)
    twin.register_driver("Maya R.", phone="555-0100", home_base="Springfield")
    load, _ = twin.book_load(
        "LD-200",
        origin="Springfield",
        destination="Chicago",
        pickup_date="2026-09-22",
        delivery_date="2026-09-23",
    )
    driver, _ = twin.register_driver("Maya R.", phone="555-0100", home_base="Springfield")
    truck, _ = twin.register_truck("UNIT-1")
    twin.offer_load(load.id, driver.id, truck.id)
    twin.accept_offer(load.id, rate_cents=180000)
    twin.dispatch_load(load.id)

    server.mark_picked_up(load.id, at=T0)
    server.arrive(load.id, "pickup", "Springfield yard", at=T0)
    server.depart(load.id, "pickup", at=T0 + timedelta(hours=3, minutes=30))
    server.arrive(load.id, "delivery", "Chicago DC", at=T0 + timedelta(hours=9))
    server.receive_pod(load.id, signed_by="J. Doe", document_ref="BOL-7788")
    assert server.detention_due_cents(load.id) == 15000

    # reopen with the same passphrase: events, stops, pods, outbox restored
    reopened = OpsServer(PW, tmp_path / "ops")
    assert reopened.detention_due_cents(load.id) == 15000
    assert reopened.engine.pod_complete(load.id)
    assert reopened.engine.pods[load.id].signed_by == "J. Doe"
    assert len(reopened.engine.events) == len(server.engine.events)
    assert reopened.channel.sent, "simulated outbox should be restored"


def test_wrong_passphrase_fails_closed(tmp_path) -> None:
    server = OpsServer(PW, tmp_path / "ops")
    server.save()
    with pytest.raises(OpsAuthError):
        OpsServer("wrong passphrase", tmp_path / "ops")


def test_empty_passphrase_refused(tmp_path) -> None:
    with pytest.raises(OpsAuthError):
        OpsServer("", tmp_path / "ops")


def test_rank_routes_through_server(tmp_path) -> None:
    server = OpsServer(PW, tmp_path / "ops")
    ranked = server.rank_routes("SGF", "CHI", deadhead_from="MEM", max_routes=2)
    assert [r.total_cents for r in ranked] == [35583 + 14500, 44267 + 14500]
    assert ranked[0].path == ("SGF", "STL", "CHI")
