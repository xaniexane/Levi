"""Tests for the levi.project package (phases runner, capability log, HITL gate).

Hermetic: no network, no user HOME writes — PhaseRunner, CapabilityLog and
HITLGate all take explicit paths, so every test points them at tmp dirs.
The PhaseRunner's internally-created log/hitl helpers are swapped for
tmp-path instances before any method that persists runs.
"""

from pathlib import Path

import pytest

from levi.project import EASY_TOUCH_PHASES, SERVICE_PHASES, PhaseRunner
from levi.project.capability_log import CapabilityLog
from levi.project.hitl import ALWAYS_HITL, HITLGate


# --------------------------------------------------------------------------
# Phase registry
# --------------------------------------------------------------------------

def test_registry_ids_unique():
    ids = [p["id"] for p in SERVICE_PHASES]
    assert len(ids) == len(set(ids))


def test_registry_entries_have_required_fields():
    for p in SERVICE_PHASES:
        for field in ("id", "name", "autonomy", "risk", "desc", "future_skill"):
            assert p.get(field), f"phase {p.get('id')} missing {field}"
        assert p["autonomy"] in ("full", "partial", "hitl"), p["id"]
        assert p["risk"] in ("LOW", "MEDIUM", "HIGH"), p["id"]


def test_easy_touch_alias_is_same_object():
    assert EASY_TOUCH_PHASES is SERVICE_PHASES


def test_p13_p14_unassigned():
    """P13/P14 are deliberately unassigned (module docstring); pin it."""
    ids = {p["id"] for p in SERVICE_PHASES}
    assert "P13" not in ids and "P14" not in ids
    assert "P15" in ids and "P0" in ids


# --------------------------------------------------------------------------
# PhaseRunner state machine
# --------------------------------------------------------------------------

def _runner(tmp_path, **kw):
    """Hermetic PhaseRunner: state + log + hitl all in tmp."""
    r = PhaseRunner(tmp_path / "state.json", **kw)
    r.log = CapabilityLog(tmp_path / "cap.json")
    r.hitl = HITLGate(tmp_path / "hitl.json")
    return r


def test_runner_fresh_defaults(tmp_path):
    r = _runner(tmp_path)
    assert r.state.current_phase == "P0"
    assert r.state.completed == []
    assert r.state.public_url == ""


def test_set_url_trims_and_validates(tmp_path):
    r = _runner(tmp_path)
    r.set_url("  https://example.com  ")
    assert r.state.public_url == "https://example.com"
    with pytest.raises(ValueError):
        r.set_url("example.com")
    with pytest.raises(ValueError):
        r.set_url("ftp://example.com")
    r.set_url("")
    assert r.state.public_url == ""


def test_complete_advances_to_next_incomplete(tmp_path):
    r = _runner(tmp_path)
    assert r.complete("P0") == "Completed P0. Current → P1"
    # idempotent: re-completing doesn't duplicate
    r.complete("P0")
    assert r.state.completed == ["P0"]
    with pytest.raises(ValueError):
        r.complete("P13")


def test_complete_case_insensitive(tmp_path):
    r = _runner(tmp_path)
    r.complete("p1")
    assert "P1" in r.state.completed


def test_complete_all_phases_holds_current_at_last(tmp_path):
    r = _runner(tmp_path)
    for p in SERVICE_PHASES:
        r.complete(p["id"])
    assert len(r.state.completed) == len(SERVICE_PHASES)
    assert r.state.current_phase == SERVICE_PHASES[-1]["id"]


def test_run_phase_unknown_lists_known(tmp_path):
    r = _runner(tmp_path)
    out = r.run_phase("P99")
    assert out.startswith("Unknown phase P99")
    assert "P0" in out and "P15" in out


def test_run_phase_p0_logs_completed_audit(tmp_path):
    r = _runner(tmp_path)
    out = r.run_phase("P0")
    assert "Capability audit" in out
    entries = r.log.list_entries(5)
    assert any(e.phase == "P0" and e.result == "completed" for e in entries)


def test_run_phase_hitl_phase_blocks_and_cards(tmp_path):
    r = _runner(tmp_path)
    out = r.run_phase("P7")  # partial + hitl_domain=subscription
    assert "HUMAN APPROVAL REQUIRED" in out
    assert "DOCUMENTATION-ONLY" in out
    assert "P7" not in r.state.completed
    blocked = [e for e in r.log.list_entries(5) if e.phase == "P7"]
    assert blocked and blocked[0].result == "blocked"
    assert len(r.hitl.list_pending()) == 1


def test_phase_info_case_insensitive(tmp_path):
    r = _runner(tmp_path)
    assert r.phase_info("p2")["name"] == "Baseline reconstruction"
    assert r.phase_info("P99") is None


def test_status_marks_progress(tmp_path):
    r = _runner(tmp_path)
    r.set_url("https://example.com")
    r.complete("P0")
    out = r.status()
    assert "✓ P0" in out
    assert "→ P1" in out
    assert "https://example.com" in out


def test_add_log_note_requires_text(tmp_path):
    r = _runner(tmp_path)
    with pytest.raises(ValueError):
        r.add_log_note("   ")
    msg = r.add_log_note("archaeology: nav has 5 items", phase="P1")
    assert msg.startswith("Logged [")
    assert r.log.list_entries(1)[0].phase == "P1"


def test_state_survives_reload(tmp_path):
    _runner(tmp_path).set_url("https://a.example")
    r = _runner(tmp_path)
    r.set_url("https://b.example")
    r.complete("P0")
    r2 = _runner(tmp_path)
    assert r2.state.public_url == "https://b.example"
    assert r2.state.completed == ["P0"]
    assert r2.state.current_phase == "P1"


def test_runner_does_not_touch_home(tmp_path, monkeypatch):
    """Proof of hermeticity: HOME is redirected and stays empty."""
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    r = _runner(tmp_path)
    r.set_url("https://x.example")
    r.run_phase("P0")
    r.complete("P0")
    assert list(fake_home.iterdir()) == []


# --------------------------------------------------------------------------
# CapabilityLog
# --------------------------------------------------------------------------

def test_caplog_rejects_garbage(tmp_path):
    cl = CapabilityLog(tmp_path / "cap.json")
    with pytest.raises(ValueError):
        cl.log(task="")
    with pytest.raises(ValueError):
        cl.log(task="x", result="bogus")
    with pytest.raises(ValueError):
        cl.log(task="x", complexity="extreme")
    with pytest.raises(ValueError):
        cl.log(task="x", automatable="maybe")
    with pytest.raises(ValueError):
        cl.log(task="x", tools=["ok", 3])


def test_caplog_limit_clamped_not_unbounded(tmp_path):
    cl = CapabilityLog(tmp_path / "cap.json")
    for i in range(5):
        cl.log(task=f"t{i}")
    # non-positive limits fall back to the default window, never unbounded
    assert len(cl.list_entries(0)) == 5
    assert len(cl.list_entries(-3)) == 5
    # newest first
    got = cl.list_entries(2)
    assert [e.task for e in got] == ["t4", "t3"]


def test_caplog_skill_candidates_dedupe_in_order(tmp_path):
    cl = CapabilityLog(tmp_path / "cap.json")
    cl.log(task="a", future_skill="SK1")
    cl.log(task="b")
    cl.log(task="c", future_skill="SK1")
    cl.log(task="d", future_skill="SK2")
    assert cl.skill_candidates() == ["SK1", "SK2"]


def test_caplog_persists_and_reloads(tmp_path):
    p = tmp_path / "cap.json"
    CapabilityLog(p).log(task="remember me", phase="P2", output_summary="ok")
    cl = CapabilityLog(p)
    assert len(cl.list_entries()) == 1
    assert cl.list_entries()[0].task == "remember me"


# --------------------------------------------------------------------------
# HITLGate
# --------------------------------------------------------------------------

def test_hitl_propose_validation_and_risk_normalization(tmp_path):
    h = HITLGate(tmp_path / "hitl.json")
    with pytest.raises(ValueError):
        h.propose(what="", why="y", changes="c")
    with pytest.raises(ValueError):
        h.propose(what="w", why="y", changes="c", domain="")
    with pytest.raises(ValueError):
        h.propose(what="w", why="y", changes="c", cost=5)
    with pytest.raises(ValueError):
        h.propose(what="w", why="y", changes="c", risk="SEVERE")
    req = h.propose(what="w", why="y", changes="c", risk="high", domain="money")
    assert req.risk == "HIGH"
    assert req.status == "pending"
    assert "HUMAN APPROVAL REQUIRED" in req.format_card()
    assert "Silence is NOT approval" in req.format_card()


def test_hitl_decide_flow_and_aliases(tmp_path):
    h = HITLGate(tmp_path / "hitl.json")
    r1 = h.propose(what="w", why="y", changes="c")
    assert h.decide(r1.id, "YES").status == "approved"
    r2 = h.propose(what="w", why="y", changes="c")
    assert h.decide(r2.id, "deny").status == "denied"
    r3 = h.propose(what="w", why="y", changes="c")
    assert h.decide(r3.id, "edit").status == "edited"
    assert h.list_pending() == []
    assert len(h.history) == 3
    with pytest.raises(KeyError):
        h.decide("nope", "approve")
    with pytest.raises(ValueError):
        r4 = h.propose(what="w", why="y", changes="c")
        h.decide(r4.id, "maybe")
    # decided requests are retrievable from history
    assert h.get(r1.id).status == "approved"
    assert h.get("missing") is None


def test_hitl_requires_hitl_policy():
    for d in ALWAYS_HITL:
        assert HITLGate.requires_hitl(d) is True
    assert HITLGate.requires_hitl("dns_subdomain") is True  # substring match
    assert HITLGate.requires_hitl("general", "MEDIUM") is True
    assert HITLGate.requires_hitl("general", "HIGH") is True
    assert HITLGate.requires_hitl("general", "LOW") is False
    assert HITLGate.requires_hitl("general") is False


def test_hitl_persists_pending_and_history(tmp_path):
    p = tmp_path / "hitl.json"
    h = HITLGate(p)
    req = h.propose(what="w", why="y", changes="c")
    h.decide(req.id, "approve", note="ok")
    pending_req = h.propose(what="w2", why="y", changes="c")
    h2 = HITLGate(p)
    assert len(h2.history) == 1 and h2.history[0].status == "approved"
    assert list(h2.pending) == [pending_req.id]
    assert h2.format_pending() != "No pending HITL requests."
