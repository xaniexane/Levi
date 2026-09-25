"""Substrate contract tests: the one bloodstream's own guarantees.

Honestly named: behavioral regression tests for the coordinator-owned
contract. They pin the interpenetration semantics every organ relies on:
shared pool, strictest-ceiling inheritance, and challenge quarantine —
including the upheld-forever rule (an upheld challenge is never released
by a later dismissal).
"""

import pytest

from levi.revival.omega import substrate as sub


def test_upheld_challenge_holds_forever_despite_later_dismissal():
    s = sub.SharedSubstrate()
    r = s.record_receipt("echo", "blueprint", {"a": 1})
    c1 = s.challenge("alpha", r.id, "first challenge, stands")
    s.resolve_challenge(c1.id, "upheld", note="bad blueprint")
    assert not s.is_consumable(r.id)
    # a second challenger opens and then withdraws — must NOT release
    c2 = s.challenge("nexus", r.id, "second look")
    s.resolve_challenge(c2.id, "dismissed", note="on reflection, fine")
    assert not s.is_consumable(r.id), "upheld verdict must hold forever"
    assert r.quarantined


def test_dismissed_challenge_releases_when_nothing_else_holds():
    s = sub.SharedSubstrate()
    r = s.record_receipt("echo", "blueprint", {"a": 1})
    c = s.challenge("alpha", r.id, "grounds")
    assert not s.is_consumable(r.id)
    s.resolve_challenge(c.id, "dismissed")
    assert s.is_consumable(r.id)


def test_open_challenge_blocks_release_of_dismissed_sibling():
    s = sub.SharedSubstrate()
    r = s.record_receipt("echo", "blueprint", {"a": 1})
    c1 = s.challenge("alpha", r.id, "first")
    c2 = s.challenge("nexus", r.id, "second")
    s.resolve_challenge(c1.id, "dismissed")
    assert not s.is_consumable(r.id), "open challenge still holds it"
    s.resolve_challenge(c2.id, "dismissed")
    assert s.is_consumable(r.id)


def test_ceiling_inheritance_strictest_wins():
    assert sub.ceiling_for("echo", "skill") == "elevated"
    assert sub.ceiling_for("echo", action_risk="critical") == "critical"
    assert sub.ceiling_for("echo", "nexus") == "standard"
    assert sub.requires_approval("elevated")
    assert not sub.requires_approval("standard")
    assert sub.requires_hitl("critical")
    assert not sub.requires_hitl("elevated")


def test_elevated_receipt_needs_approval():
    s = sub.SharedSubstrate()
    with pytest.raises(ValueError):
        s.record_receipt("alpha", "build", {}, risk="elevated")
    r = s.record_receipt("alpha", "build", {}, risk="elevated",
                         approved_by="test")
    assert r.approved_by == "test"


def test_schedule_pool_roundtrip():
    s = sub.SharedSubstrate()
    item = s.schedule("daemon", "symbiotic_loop", "2000-01-01T00:00:00+00:00",
                      {"prompt": "x"})
    due = s.due_jobs(now="2026-09-22T12:00:00+00:00")
    assert [j.id for j in due] == [item.id]
    s.mark_job(item.id, "done")
    assert s.due_jobs(now="2026-09-22T12:00:00+00:00") == []


def test_challenge_unknown_receipt_raises():
    s = sub.SharedSubstrate()
    with pytest.raises(KeyError):
        s.challenge("alpha", "rcpt_nope", "grounds")


def test_save_load_roundtrip(tmp_path):
    s = sub.SharedSubstrate()
    r = s.record_receipt("echo", "blueprint", {"a": 1})
    s.record_learning("daemon", "loops halt on quarantine")
    s.record_genome("skill", "risk-tiered registry")
    p = str(tmp_path / "sub.json")
    s.save(p)
    s2 = sub.SharedSubstrate.load(p)
    assert s2.get_receipt(r.id).payload == {"a": 1}
    assert len(s2.learnings()) == 1
    assert len(s2.genome()) == 1
