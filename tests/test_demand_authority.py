"""Tests for DemandPulse autonomous upgrade authority."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from levi.demand.authority import (
    TIER_MAJOR,
    TIER_MID,
    TIER_MINOR,
    Action,
    AuthorityEngine,
    AuthorityRefused,
    classify_action,
    register_executor,
)


@pytest.fixture()
def tmp_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="levi-authority-")
    monkeypatch.setenv("LEVI_HOME", d)
    return Path(d)


def make_engine(tmp_home):
    from levi.demand import authority

    return authority.AuthorityEngine(
        audit_path=tmp_home / "demand" / "authority-audit.jsonl",
        escalation_path=tmp_home / "demand" / "escalations.jsonl",
    )


def live_signal(engine):
    return engine.sense(
        source="test", evidence="time-sensitive window", confidence=0.8, ttl_seconds=3600
    )


def action(kind, target="some-target", **params):
    return Action(id="act-test-1", kind=kind, target=target, params=params)


# --- classification ----------------------------------------------------------


def test_minor_kinds_classify_minor():
    assert classify_action("config-tweak") == TIER_MINOR
    assert classify_action("small-patch") == TIER_MINOR


def test_mid_kinds_classify_mid():
    assert classify_action("dependency-upgrade") == TIER_MID
    assert classify_action("module-improvement") == TIER_MID


def test_major_kinds_classify_major():
    for kind in ("architecture", "security", "founder", "irreversible", "credential"):
        assert classify_action(kind) == TIER_MAJOR


def test_flags_force_major():
    assert classify_action("config-tweak", irreversible=True) == TIER_MAJOR
    assert classify_action("small-patch", security_sensitive=True) == TIER_MAJOR
    assert classify_action("config-tweak", founder_level=True) == TIER_MAJOR
    assert classify_action("config-tweak", scope="network") == TIER_MAJOR


def test_ambiguous_fails_closed():
    # Unknown kind -> MAJOR (escalate), never auto.
    assert classify_action("mystery-kind-xyz") == TIER_MAJOR
    assert classify_action("") == TIER_MAJOR
    assert classify_action("   ") == TIER_MAJOR


# --- trigger gating ----------------------------------------------------------


def test_no_signal_refuses_everything(tmp_home):
    eng = make_engine(tmp_home)
    receipt = eng.run(action("config-tweak"))
    assert receipt.outcome == "refused"
    assert "signal" in receipt.result["reason"]


def test_expired_signal_refuses(tmp_home):
    eng = make_engine(tmp_home)
    sig = eng.sense("test", "x", confidence=0.9, ttl_seconds=-1)
    receipt = eng.run(action("config-tweak"), signal_id=sig.id)
    assert receipt.outcome == "refused"


def test_low_confidence_signal_refuses(tmp_home):
    eng = make_engine(tmp_home)
    sig = eng.sense("test", "x", confidence=0.2, ttl_seconds=3600)
    receipt = eng.run(action("config-tweak"), signal_id=sig.id)
    assert receipt.outcome == "refused"


# --- minor: full auto ---------------------------------------------------------


def test_minor_executes_with_audit_and_receipt(tmp_home):
    eng = make_engine(tmp_home)
    sig = live_signal(eng)
    receipt = eng.run(
        Action(
            id="act-minor",
            kind="config-tweak",
            target="demo",
            params={"key": "k1", "value": "v1"},
        ),
        signal_id=sig.id,
    )
    assert receipt.outcome == "executed"
    assert receipt.tier == TIER_MINOR
    assert receipt.id
    # audit written
    entries = [json.loads(l) for l in (tmp_home / "demand" / "authority-audit.jsonl").read_text().splitlines()]
    assert any(e.get("event") == "executed" and e.get("receipt_id") == receipt.id for e in entries)
    # six gates recorded
    assert set(receipt.gates) >= {"plan", "preview", "permission", "execute", "verify", "receipt"}
    # posture recorded
    assert receipt.posture == "high-deterministic-ambition"


# --- mid: auto with full trail -------------------------------------------------


def test_mid_executes_with_full_trail(tmp_home):
    eng = make_engine(tmp_home)
    sig = live_signal(eng)
    receipt = eng.run(
        Action(id="act-mid", kind="dependency-upgrade", target="levi.scores"),
        signal_id=sig.id,
    )
    assert receipt.outcome == "executed"
    assert receipt.tier == TIER_MID
    assert receipt.gates["permission"]["basis"].startswith("standing grant")


# --- major: NEVER executes ----------------------------------------------------


def test_major_never_executes_and_escalates(tmp_home):
    eng = make_engine(tmp_home)
    sig = live_signal(eng)
    called = []

    # Even a directly passed callable must never run for a major action.
    receipt = eng.run(
        Action(id="act-major", kind="architecture", target="core"),
        signal_id=sig.id,
    )
    assert receipt.outcome == "escalated"
    assert receipt.result["escalation_id"]
    pending = eng.pending_escalations()
    assert len(pending) == 1
    assert pending[0]["action_id"] == "act-major"
    assert called == []


def test_ambiguous_major_escalates(tmp_home):
    eng = make_engine(tmp_home)
    sig = live_signal(eng)
    receipt = eng.run(
        Action(id="act-amb", kind="never-seen-before-kind", target="x"),
        signal_id=sig.id,
    )
    assert receipt.outcome == "escalated"
    assert eng.pending_escalations()


def test_register_executor_refuses_major():
    with pytest.raises(AuthorityRefused):
        register_executor("architecture", lambda a: {"ok": True})


def test_escalation_resolve_roundtrip(tmp_home):
    eng = make_engine(tmp_home)
    sig = live_signal(eng)
    receipt = eng.run(Action(id="act-r", kind="security", target="t"), signal_id=sig.id)
    esc_id = receipt.result["escalation_id"]
    assert eng.resolve_escalation(esc_id, "reviewed by keeper")
    assert eng.pending_escalations() == []
    assert not eng.resolve_escalation(esc_id, "again")  # already resolved


def test_status_shape(tmp_home):
    eng = make_engine(tmp_home)
    live_signal(eng)
    status = eng.status()
    assert status["tiers"]["major"].startswith("NEVER")
    assert status["live_signals"] == 1


def test_signal_survives_engine_restart(tmp_home):
    eng1 = make_engine(tmp_home)
    sig = live_signal(eng1)
    eng2 = make_engine(tmp_home)  # fresh instance, same home
    receipt = eng2.run(action("config-tweak"), signal_id=sig.id)
    assert receipt.outcome == "executed"
