"""Hermetic tests for levi.decisions — tmp HOME, injectable now, no network."""

from datetime import datetime, timezone

import pytest

from levi.decisions import DecisionError, DecisionJournal, check


def _now(y=2026, m=9, d=15):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def journal(tmp_path):
    return DecisionJournal(home=tmp_path)


def test_full_lifecycle(journal):
    d = journal.decide(
        "use SQLite for the ledger", "stdlib-only, local", revisit="2026-10-15"
    )
    assert d["id"] == "d0001"
    assert d["state"] == "active"
    assert d["revisit"] == "2026-10-15"

    r = journal.reaffirm(d["id"], note="still stdlib-only; no reason to change")
    assert len(r["reaffirmations"]) == 1
    assert r["reaffirmations"][0]["note"].startswith("still stdlib-only")
    assert r["state"] == "active"

    retired = journal.retire(d["id"], why="project pivoted to Postgres")
    assert retired["state"] == "retired"
    assert retired["retired_reason"] == "project pivoted to Postgres"
    # composted, not deleted
    assert journal.get(d["id"])["state"] == "retired"


def test_retire_needs_a_reason(journal):
    d = journal.decide("t", "r", revisit="2026-10-01")
    with pytest.raises(DecisionError):
        journal.retire(d["id"], why=" ")


def test_reaffirm_needs_a_note(journal):
    d = journal.decide("t", "r", revisit="2026-10-01")
    with pytest.raises(DecisionError):
        journal.reaffirm(d["id"], note="")


def test_cannot_retire_twice(journal):
    d = journal.decide("t", "r", revisit="2026-10-01")
    journal.retire(d["id"], why="done")
    with pytest.raises(DecisionError):
        journal.retire(d["id"], why="again")


def test_cannot_reaffirm_retired(journal):
    d = journal.decide("t", "r", revisit="2026-10-01")
    journal.retire(d["id"], why="done")
    with pytest.raises(DecisionError):
        journal.reaffirm(d["id"], note="still holds")


def test_decide_validation(journal):
    with pytest.raises(DecisionError):
        journal.decide("", "reasoning", revisit="2026-10-01")
    with pytest.raises(DecisionError):
        journal.decide("title", "reasoning", revisit="not-a-date")
    with pytest.raises(DecisionError):
        journal.get("d9999")


def test_due_for_revisit(journal):
    journal.decide("due yesterday", "r", revisit="2026-09-14")
    journal.decide("due today", "r", revisit="2026-09-15")
    journal.decide("due tomorrow", "r", revisit="2026-09-16")
    journal.decide("far future", "r", revisit="2027-01-01")

    due = journal.due_for_revisit(now=_now(2026, 9, 15))
    assert {d["title"] for d in due} == {"due yesterday", "due today"}

    # retired decisions never surface
    ret = journal.decide("retired but due", "r", revisit="2026-09-01")
    journal.retire(ret["id"], why="obsolete")
    assert "retired but due" not in {
        d["title"] for d in journal.due_for_revisit(now=_now(2026, 9, 15))
    }


def test_check_cards(journal):
    journal.decide("keep the evening hunt", "calmer signal", revisit="2026-09-15")
    signals = journal.check(now=_now(2026, 9, 15))
    assert len(signals) == 1
    sig = signals[0]
    assert sig["grade"] == "CARD"
    assert sig["tag"] == "decisions:revisit"
    assert set(sig) == {"grade", "tag", "title", "body"}
    assert "does this still hold" in sig["body"]


def test_check_empty_is_silent(journal):
    assert journal.check(now=_now(2026, 9, 15)) == []


def test_status_honest(journal):
    s = journal.status()
    assert s["total"] == 0
    assert "no decisions recorded" in s["note"]

    journal.decide("a", "r", revisit="2026-09-14")
    journal.decide("b", "r", revisit="2027-01-01")
    s2 = journal.status(now=_now(2026, 9, 15))
    assert (s2["active"], s2["retired"], s2["total"]) == (2, 0, 2)
    assert s2["due_for_revisit"] == 1


def test_module_level_check(tmp_path):
    j = DecisionJournal(home=tmp_path)
    j.decide("revisit me", "why", revisit="2026-09-01")
    signals = check(home=tmp_path, now=_now(2026, 9, 15))
    assert len(signals) == 1
    assert signals[0]["grade"] == "CARD"


def test_home_resolution_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "alt"))
    j = DecisionJournal()
    j.decide("env-home decision", "why", revisit="2026-10-01")
    assert (tmp_path / "alt" / ".levi" / "decisions" / "decisions.json").exists()
