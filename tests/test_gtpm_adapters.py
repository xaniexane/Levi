"""Adapter acceptance: delegate_scan executes real scan-mind sub-runs.

Hermetic: LEVI_GTPM_DIR is pointed at tmp_path; a socket-blocking guard
proves zero network use. Regression suite for the B6 contract conflict:
delegate_scan must execute scan cycles itself and never call back into
synthesis.delegate_goals (the circular route the beginning team flagged).
"""

import json
import socket
import types

import pytest

from levi.gtpm import adapters
from levi.gtpm.adapters import build_supervisory_program, delegate_scan, gtpm_dir


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_GTPM_DIR", str(tmp_path / "gtpm"))


def _block_network():
    real = socket.socket

    def _raise(*a, **k):
        raise AssertionError("network access attempted during delegate_scan")

    socket.socket = _raise  # type: ignore[assignment]
    return real


def _cfg(**kw):
    d = {"scan_budget_ms": 100, "offline_enforced": True}
    d.update(kw)
    return types.SimpleNamespace(**d)


def test_never_reenters_synthesis_delegate_goals(monkeypatch):
    """The B6 circularity, guarded: even with delegate_goals armed to
    explode, the scan route executes without touching it."""
    import levi.synthesis.agent as agent

    def _boom(*a, **k):
        raise AssertionError("delegate_scan called back into synthesis")

    monkeypatch.setattr(agent, "delegate_goals", _boom)
    out = delegate_scan(["watch the backup schedules"], config=_cfg(), max_steps=1)
    assert out["workers"] == 1
    assert out["workers_ok"] == 1


def test_merged_receipt_shape_matches_synthesis_contract():
    out = delegate_scan(["a", "b"], config=_cfg(), max_steps=1)
    assert out["coordinator"] == "gtpm.adapters.delegate_scan"
    assert out["mind"] == "scan"
    assert out["workers"] == 2
    assert out["workers_ok"] == 2
    assert len(out["sub_receipts"]) == 2
    sub = out["sub_receipts"][0]
    assert sub["goal"] == "a"
    assert sub["cycles"] == 1
    assert sub["faults"] == []
    assert sub["watchdog_ok"] is True
    assert sub["ok"] is True
    assert len(sub["image_hashes"]) == 1


def test_scan_commits_supervisory_intents_through_gate():
    out = delegate_scan(["watch the backup schedules"], config=_cfg(), max_steps=1)
    commits = out["sub_receipts"][0]["commits"]
    intents = {c["intent"] for c in commits}
    # watch (normal) + seal (latch) + edge (one_shot) all stage on cycle 1
    assert {"supervise_goal", "goal_latched", "announce_goal"} <= intents
    assert all(c["ok"] for c in commits)
    # the goal text rides into the committed args, resolved from the image
    watch = next(c for c in commits if c["intent"] == "supervise_goal")
    assert watch["args"]["goal"] == "watch the backup schedules"


def test_max_steps_bounds_cycles_per_goal():
    out = delegate_scan(["g"], config=_cfg(), max_steps=2)
    assert out["sub_receipts"][0]["cycles"] == 2
    out = delegate_scan(["g"], config=_cfg(), max_steps=99)
    assert out["sub_receipts"][0]["cycles"] == 6
    out = delegate_scan(["g"], config=_cfg(), max_steps=0)
    assert out["sub_receipts"][0]["cycles"] == 1


def test_empty_goals_is_vacuous_not_an_error():
    out = delegate_scan([], config=_cfg())
    assert out["workers"] == 0
    assert out["workers_ok"] == 0
    assert out["sub_receipts"] == []


def test_non_string_goal_fails_closed():
    with pytest.raises(ValueError):
        delegate_scan([None], config=_cfg())
    with pytest.raises(ValueError):
        delegate_scan([{"goal": "x"}], config=_cfg())


def test_offline_interlock_trips_when_not_enforced():
    out = delegate_scan(["g"], config=_cfg(offline_enforced=False), max_steps=1)
    sub = out["sub_receipts"][0]
    assert sub["commits"] == []
    assert any(f["type"] == "INTERLOCK" for f in sub["faults"])
    assert sub["ok"] is False
    assert out["workers_ok"] == 0


def test_supervisory_program_interlock_is_rung_zero():
    program = build_supervisory_program()
    first = program["rungs"][0]
    assert first["name"] == "interlock_offline"
    assert first["safety"] is True


def test_policy_gate_fail_closed_mapping():
    gate = adapters.policy_gate()
    assert gate({"intent": "x", "risk": 1}) is True
    assert gate({"intent": "y", "risk": 4}) is False


def test_determinism_across_runs():
    first = delegate_scan(["watch the schedules"], config=_cfg(), max_steps=2)
    second = delegate_scan(["watch the schedules"], config=_cfg(), max_steps=2)
    for key in ("commits", "faults", "image_hashes", "watchdog_ok", "ok"):
        assert first["sub_receipts"][0][key] == second["sub_receipts"][0][key]


def test_runs_offline_and_writes_scan_receipts():
    real = _block_network()
    try:
        out = delegate_scan(["watch the schedules"], config=_cfg(), max_steps=2)
    finally:
        socket.socket = real  # type: ignore[assignment]
    assert out["workers_ok"] == 1
    lines = (
        (gtpm_dir() / "receipts.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    kinds = {json.loads(line)["kind"] for line in lines}
    assert "scan" in kinds
    assert len(lines) == 2  # one receipt per cycle
    goals = {json.loads(line)["goal"] for line in lines}
    assert goals == {"watch the schedules"}
