"""Tests for the synthesis agentic loop: perceive → reason → act → verify → receipt.

Rules-only brain policy throughout (no torch needed). Home-directory paths
are redirected to tmp fixtures so tests never touch the operator's real
``~/.levi/synthesis/`` state.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from levi.synthesis import agent as agent_mod
from levi.synthesis.config import SynthesisConfig


@pytest.fixture
def synth_home(tmp_path, monkeypatch):
    home = tmp_path / "synth"
    home.mkdir()
    monkeypatch.setattr(agent_mod, "_synthesis_home", lambda: home)
    return home


@pytest.fixture
def rules_cfg():
    return SynthesisConfig(brain_policy="rules-only")


def _last_receipt(home: Path) -> dict:
    lines = (home / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])


def test_run_goal_benign_completes_with_receipt(synth_home, rules_cfg):
    receipt = agent_mod.run_goal(
        "remember that test apples are red", config=rules_cfg, max_steps=4
    )
    assert receipt.ok is True
    assert receipt.steps_taken >= 1
    assert receipt.substrate == "rules-engine"
    assert receipt.verdict  # the reason step deliberated
    assert any(t["tool"] == "memory_write" and t["ok"] for t in receipt.tool_calls)
    persisted = _last_receipt(synth_home)
    assert persisted["goal"] == "remember that test apples are red"
    assert persisted["ok"] is True


def test_gated_tool_blocked_without_consent(synth_home, rules_cfg, tmp_path):
    target = Path.home() / ".levi" / "agent_workspace" / "gate_probe_no_consent.txt"
    if target.exists():
        target.unlink()
    receipt = agent_mod.run_goal(
        "create a file called gate_probe_no_consent.txt containing the words no consent probe",
        config=rules_cfg,
        max_steps=4,
        consent=False,
    )
    assert receipt.ok is False
    assert len(receipt.gates_hit) >= 1  # the block is recorded, not hidden
    assert not target.exists()  # nothing consequential executed


def test_gated_tool_allowed_with_consent(synth_home, rules_cfg):
    target = Path.home() / ".levi" / "agent_workspace" / "gate_probe_consent.txt"
    if target.exists():
        target.unlink()
    try:
        receipt = agent_mod.run_goal(
            "create a file called gate_probe_consent.txt containing the words consent probe",
            config=rules_cfg,
            max_steps=4,
            consent=True,  # the explicit Permission step
        )
        assert receipt.ok is True
        assert target.exists()
        # NOTE: the deterministic local planner parses the filename but writes
        # placeholder content ("Line 1...") — content fidelity is a known
        # planner limitation, not a permission question. This test proves the
        # gate: with consent the tool executes; without it (previous test) it
        # is blocked and nothing is written.
        assert target.stat().st_size > 0
    finally:
        if target.exists():
            target.unlink()


def test_delegate_goals_merges_receipts(synth_home, rules_cfg):
    merged = agent_mod.delegate_goals(
        ["remember that test delegates alpha", "remember that test delegates beta"],
        config=rules_cfg,
        max_steps=4,
    )
    assert merged["workers"] == 2
    assert merged["workers_ok"] == 2
    assert len(merged["sub_receipts"]) == 2
    assert all(r["ok"] for r in merged["sub_receipts"])
    assert (synth_home / "delegations.jsonl").exists()


def test_schedule_and_tick(synth_home, rules_cfg):
    entry = agent_mod.schedule_goal(
        "remember that test schedule ran", every_seconds=3600
    )
    assert entry["goal"] == "remember that test schedule ran"
    ran = agent_mod.tick_schedules(config=rules_cfg, max_steps=4)
    assert len(ran) == 1
    assert ran[0]["ok"] is True
    schedules = agent_mod.list_schedules()
    assert len(schedules) == 1
    assert schedules[0]["last_ok"] is True
    assert isinstance(schedules[0]["next_run"], float)
    assert schedules[0]["next_run"] > time.time()
    # Second tick before the interval: nothing runs.
    ran_again = agent_mod.tick_schedules(config=rules_cfg, max_steps=4)
    assert ran_again == []


def test_agent_runs_offline(synth_home, rules_cfg):
    from levi.synthesis import offline as offline_mod

    with offline_mod.OfflineGuard():
        receipt = agent_mod.run_goal(
            "remember that test offline held", config=rules_cfg, max_steps=4
        )
    assert receipt.ok is True  # no OfflineViolation escaped


def test_receipts_roundtrip(synth_home, rules_cfg):
    agent_mod.run_goal("remember that test roundtrip", config=rules_cfg, max_steps=4)
    receipts = agent_mod.read_receipts(limit=3)
    assert len(receipts) >= 1
    assert receipts[-1]["goal"] == "remember that test roundtrip"


def test_synthesis_home_honors_levi_synthesis_dir(tmp_path, monkeypatch, rules_cfg):
    # The agent's state home must follow LEVI_SYNTHESIS_DIR, like the
    # config does — no monkeypatch of _synthesis_home here.
    env_home = tmp_path / "envsyn"
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(env_home))
    receipt = agent_mod.run_goal(
        "remember that test env dir", config=rules_cfg, max_steps=4
    )
    assert receipt.ok is True
    persisted = json.loads(
        (env_home / "receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert persisted["goal"] == "remember that test env dir"


def test_run_goal_rejects_empty():
    with pytest.raises(ValueError):
        agent_mod.run_goal("   ", config=SynthesisConfig(brain_policy="rules-only"))


# -- middle-team contract (B1–B9) ---------------------------------------------


def test_receipt_kind_defaults_to_goal(synth_home, rules_cfg):
    receipt = agent_mod.run_goal(
        "remember that test kind default", config=rules_cfg, max_steps=4
    )
    assert receipt.kind == "goal"
    persisted = _last_receipt(synth_home)
    assert persisted["kind"] == "goal"


def test_governance_frame_frozen_in_receipt(synth_home, rules_cfg):
    receipt = agent_mod.run_goal(
        "remember that test governance", config=rules_cfg, max_steps=4
    )
    gov = receipt.governance
    assert gov["goal"] == "remember that test governance"
    assert gov["consent"] is False
    assert gov["brain_policy"] == "rules-only"
    assert gov["scan_budget_ms"] == 100
    assert "frozen_at" in gov
    persisted = _last_receipt(synth_home)
    assert persisted["governance"]["consent"] is False


def test_write_receipt_entry_preserves_kind(synth_home):
    agent_mod.write_receipt_entry({"kind": "scan", "cycle": 7, "verdict": "hold"})
    receipts = agent_mod.read_receipts(limit=5)
    kinds = [r["kind"] for r in receipts]
    assert "scan" in kinds
    entry = next(r for r in receipts if r["kind"] == "scan")
    assert entry["cycle"] == 7
    assert "logged_at" in entry


def test_delegate_goals_rejects_unknown_mind(synth_home, rules_cfg):
    with pytest.raises(ValueError):
        agent_mod.delegate_goals(
            ["remember that test x"], config=rules_cfg, mind="oracle"
        )


def test_delegate_goals_scan_route_honest_when_unavailable(synth_home, rules_cfg):
    # Simulate a missing middle-team package: the 'scan' route must fail
    # honestly, not pretend to delegate.
    import sys

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(sys.modules, "levi.gtpm.adapters", None)
    try:
        with pytest.raises(RuntimeError, match="unavailable"):
            agent_mod.delegate_goals(
                ["remember that test scan"], config=rules_cfg, mind="scan"
            )
    finally:
        monkeypatch.undo()


def test_delegate_goals_scan_route_executes_scan_mind(synth_home, rules_cfg):
    # Contract B6 resolved: the middle-team adapter executes real scan-mind
    # sub-runs directly instead of re-entering delegate_goals(mind="scan").
    # The route must return executed receipts, not raise.
    result = agent_mod.delegate_goals(
        ["remember that test scan"], config=rules_cfg, mind="scan"
    )
    assert result["coordinator"] == "gtpm.adapters.delegate_scan"
    assert result["mind"] == "scan"
    assert result["workers"] == 1
    assert result["workers_ok"] == 1
    sub = result["sub_receipts"][0]
    assert sub["goal"] == "remember that test scan"
    assert sub["ok"] is True
    assert sub["faults"] == []


def test_tick_writes_cycle_receipt_and_freezes_frame(synth_home, rules_cfg):
    entry = agent_mod.schedule_goal(
        "remember that test tick receipt", every_seconds=3600
    )
    original_next_run = entry["next_run"]
    ran = agent_mod.tick_schedules(config=rules_cfg, max_steps=4)
    assert len(ran) == 1
    assert ran[0]["skipped"] is False
    assert ran[0]["ok"] is True
    tick_receipt = _last_receipt(synth_home)
    assert tick_receipt["kind"] == "tick"
    assert tick_receipt["due"] == 1
    assert tick_receipt["skipped"] == 0
    assert tick_receipt["budget_ms"] == 100
    assert tick_receipt["summaries"][0]["goal"] == "remember that test tick receipt"
    # The freeze: the entry's next_run advanced past what it was.
    assert agent_mod.list_schedules()[0]["next_run"] > original_next_run


def test_tick_budget_exhaustion_skips_honestly(synth_home, rules_cfg):
    agent_mod.schedule_goal("remember that test budget a", every_seconds=3600)
    agent_mod.schedule_goal("remember that test budget b", every_seconds=3600)
    tiny = SynthesisConfig(brain_policy="rules-only", scan_budget_ms=1)
    ran = agent_mod.tick_schedules(config=tiny, max_steps=4)
    assert len(ran) == 2
    skipped = [r for r in ran if r["skipped"]]
    assert len(skipped) >= 1  # the first may fit; the rest honestly skip
    for r in skipped:
        assert "budget" in r["reason"]
    tick_receipt = _last_receipt(synth_home)
    assert tick_receipt["kind"] == "tick"
    assert tick_receipt["skipped"] == len(skipped)
    # Skipped entries keep their original next_run: they run on the next tick.
    for entry in agent_mod.list_schedules():
        if entry["goal"] in {r["goal"] for r in skipped}:
            assert "last_run" not in entry
