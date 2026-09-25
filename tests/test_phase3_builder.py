"""Acceptance suite for phase3.builder (C10) — T1..T7.

Own tiny socket-blocking fixture below; nothing imported from the
beginning team's synthesis/offline.py.
"""

from __future__ import annotations

import socket

import pytest

from levi.phase3.builder import (
    Builder,
    Rank,
    RungStub,
    Spool,
    advance,
    apply_delta,
    attempt_build,
    fetch_assets,
    make_delta,
    new_region,
    payload_bytes,
    validate_addition,
)


@pytest.fixture()
def no_sockets(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network attempted during offline test")

    monkeypatch.setattr(socket, "socket", blocked)
    yield


def _good_op(eid: str, n: int = 0) -> dict:
    return {
        "kind": "add",
        "entity_type": "room",
        "entity_id": eid,
        "props": {"name": f"room-{eid}", "n": n},
        "rung": 0,
    }


def _region_with_builders(region_id: str = "r") -> tuple:
    region = new_region(region_id, "clearing")
    return region, RungStub()


# -- T1: rank gating ---------------------------------------------------
def test_t1_builds_above_rank_refused():
    region, rung = _region_with_builders()
    refusals = 0
    for i in range(60):
        mason = Builder(agent_id=f"v{i}", rank=Rank.VISITOR if i % 2 else Rank.RESIDENT)
        out = attempt_build(mason, region, [_good_op(f"e{i}")], rung)
        assert out["ok"] is False
        assert "lacks build capability" in out["reason"]
        refusals += 1
    assert refusals == 60


def test_t1_earned_advancement_grants_capability():
    region, rung = _region_with_builders()
    mason = Builder(agent_id="earner")
    assert advance(mason, 5, lambda w: True) is True
    assert mason.rank == Rank.RESIDENT
    assert advance(mason, 15, lambda w: True) is True
    assert mason.rank == Rank.BUILDER
    out = attempt_build(mason, region, [_good_op("e1")], rung)
    assert out["ok"] is True
    assert "e1" in region.state


# -- T2: schema validation ---------------------------------------------
def test_t2_schema_violations_rejected_pre_apply():
    region, rung = _region_with_builders()
    mason = Builder(agent_id="checker", rank=Rank.BUILDER)
    rejected = applied = 0
    for i in range(100):
        if i < 20:
            op = _good_op(f"g{i}") | {"entity_type": "dragon"}  # illegal type
        elif i < 30:
            op = _good_op(f"g{i}") | {"kind": "teleport"}  # illegal op
        elif i < 40:
            op = dict(_good_op(f"g{i}"))  # rung denied (deny-by-default)
            del op["rung"]
        else:
            op = _good_op(f"g{i}")
        out = attempt_build(mason, region, [op], rung)
        if out["ok"]:
            applied += 1
        else:
            rejected += 1
            assert out["reason"]
    assert rejected == 40
    assert applied == 60
    # zero violations in the world
    for eid, ent in region.state.items():
        assert ent["type"] in region.schema["entity_types"], eid


# -- T3: delta economy -------------------------------------------------
def test_t3_payload_proportional_to_delta_not_world():
    region, rung = _region_with_builders("big")
    big_ops = [_good_op(f"ent-{i}", i) for i in range(10_000)]
    # apply in chunks to keep deltas sane
    for j in range(0, 10_000, 1000):
        apply_delta(region, make_delta(region, big_ops[j : j + 1000], "scaler", rung))
    assert len(region.state) == 10_000
    world_bytes = region.state_bytes()
    change = [_good_op(f"ent-{i}", 999) | {"kind": "modify"} for i in range(50)]
    delta = make_delta(region, change, "scaler", rung)
    payload = payload_bytes(delta)
    assert payload * 20 < world_bytes, (payload, world_bytes)


# -- T4: lazy assets ---------------------------------------------------
def test_t4_only_rendered_assets_cross():
    region, rung = _region_with_builders("assets")
    mason = Builder(agent_id="lazy", rank=Rank.BUILDER)
    op = _good_op("hall")
    op["asset_refs"] = {f"asset-{i}": f"sha256:{i:04d}" for i in range(20)}
    out = attempt_build(mason, region, [op], rung)
    assert out["ok"] is True
    delta = make_delta(region, [op], "lazy", rung)
    local_store = {f"sha256:{i:04d}": f"bytes-{i}" for i in range(20)}
    crossed: list = []
    fetched = fetch_assets(
        delta, {"asset-3", "asset-7", "asset-19"}, local_store, crossed
    )
    assert set(fetched) == {"asset-3", "asset-7", "asset-19"}
    assert len(crossed) == 3  # unrendered assets never crossed


# -- T5: offline queue -------------------------------------------------
def test_t5_queued_deltas_apply_in_order():
    staging, rung = _region_with_builders("spool-stage")
    spool = Spool(link_up=False)
    for i in range(30):
        delta = make_delta(staging, [_good_op(f"q{i}")], "spooler", rung)
        apply_delta(staging, delta)  # advance staging so bases are sequential
        spool.enqueue(delta)
    region, _ = _region_with_builders("spool-stage")
    assert spool.flush(region) == 0  # link down: nothing moves
    assert region.version == 0
    spool.link_up = True
    assert spool.flush(region) == 30
    assert region.version == 30
    assert spool.applied == list(range(30))  # FIFO order
    assert all(f"q{i}" in region.state for i in range(30))


# -- T6: determinism ---------------------------------------------------
def _build_sequence(region_id: str) -> bytes:
    region, rung = _region_with_builders(region_id)
    for i in range(25):
        apply_delta(region, make_delta(region, [_good_op(f"d{i}", i)], "det", rung))
    return region.canonical_state()


def test_t6_same_deltas_same_bytes():
    assert _build_sequence("a") == _build_sequence("b")


# -- T7: offline -------------------------------------------------------
def test_t7_battery_with_sockets_disabled(no_sockets):
    region, rung = _region_with_builders("off")
    mason = Builder(agent_id="off", rank=Rank.BUILDER)
    out = attempt_build(mason, region, [_good_op("o1")], rung)
    assert out["ok"] is True
    delta = make_delta(region, [_good_op("o2")], "off", rung)
    spool = Spool(link_up=False)
    spool.enqueue(delta)
    spool.link_up = True
    assert spool.flush(region) == 1
    assert validate_addition(region, {"kind": "teleport"}, rung)
