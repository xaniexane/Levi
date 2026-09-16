"""Hermetic tests for levi.promises — tmp HOME, injectable now, no network."""

from datetime import datetime, timezone

import pytest

from levi.promises import PromiseError, PromiseStore, check


def _now(y=2026, m=9, d=15):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path):
    return PromiseStore(home=tmp_path)


def test_full_lifecycle(store):
    p = store.make("remind Chauncey about the dentist", due="2026-09-20")
    assert p["id"] == "p0001"
    assert p["state"] == "pending"
    assert p["due"] == "2026-09-20"
    assert p["actor"] == "levi"

    kept = store.fulfill(p["id"], evidence="reminded at 09:00")
    assert kept["state"] == "kept"
    assert kept["evidence"] == "reminded at 09:00"
    assert kept["resolved_at"]

    # cannot fulfill twice
    with pytest.raises(PromiseError):
        store.fulfill(p["id"])


def test_break_keeps_record(store):
    p = store.make("draft the birthday note", due="2026-09-16")
    broken = store.break_promise(p["id"], why="Chauncey asked me to hold off")
    assert broken["state"] == "broken"
    assert broken["why_broken"] == "Chauncey asked me to hold off"
    # still on the ledger, not deleted
    assert store.get(p["id"])["state"] == "broken"
    assert store.list("broken")


def test_break_needs_a_reason(store):
    p = store.make("something")
    with pytest.raises(PromiseError):
        store.break_promise(p["id"], why="   ")


def test_make_validation(store):
    with pytest.raises(PromiseError):
        store.make("   ")
    with pytest.raises(PromiseError):
        store.make("x", due="not-a-date")
    with pytest.raises(PromiseError):
        store.get("p9999")


def test_overdue_detection_and_grades(store):
    # long lead: created 2026-09-01, due 2026-09-20 (19d lead).
    # at 2026-09-30 → 10d overdue < 38d threshold → CARD.
    store.make("long-lead promise", due="2026-09-20", now=_now(2026, 9, 1))
    # short lead: created 2026-09-15, due 2026-09-16 (1d lead).
    # at 2026-09-30 → 14d overdue > max(2, 2)d threshold → ESCALATE.
    store.make("short-lead promise", due="2026-09-16", now=_now())

    signals = store.check(now=_now(2026, 9, 30))
    assert len(signals) == 2
    # long lead: 30d lead, 15d overdue → threshold 60d → CARD
    long_sig = [s for s in signals if "long-lead" in s["title"]][0]
    assert long_sig["grade"] == "CARD"
    assert set(long_sig) == {"grade", "tag", "title", "body"}
    assert long_sig["tag"] == "promises:overdue"
    # short lead: 1d lead, 14d overdue → threshold max(2,2)=2d → ESCALATE
    short_sig = [s for s in signals if "short-lead" in s["title"]][0]
    assert short_sig["grade"] == "ESCALATE"


def test_no_due_date_never_overdue(store):
    store.make("someday/maybe item")
    assert store.check(now=_now(2027, 1, 1)) == []
    assert store.overdue(now=_now(2027, 1, 1)) == []


def test_due_today_not_overdue(store):
    store.make("due today", due="2026-09-15")
    assert store.overdue(now=_now(2026, 9, 15)) == []
    assert len(store.overdue(now=_now(2026, 9, 16))) == 1


def test_fulfillment_rate_math(store):
    store.fulfill(store.make("a")["id"], evidence="done")
    store.fulfill(store.make("b")["id"], evidence="done")
    store.break_promise(store.make("c")["id"], why="user cancelled")
    store.make("d still pending")
    s = store.status()
    assert (s["kept"], s["pending"], s["broken"], s["total"]) == (2, 1, 1, 4)
    assert s["fulfillment_rate"] == pytest.approx(2 / 3)


def test_empty_state_honesty(store):
    s = store.status()
    assert s["total"] == 0
    assert s["fulfillment_rate"] is None
    assert "no promises recorded" in s["note"]
    assert store.check(now=_now()) == []


def test_unresolved_only_rate_honesty(store):
    store.make("only pending")
    s = store.status()
    assert s["fulfillment_rate"] is None
    assert "none resolved yet" in s["note"]


def test_module_level_check_integration_surface(tmp_path):
    st = PromiseStore(home=tmp_path)
    st.make("overdue one", due="2026-09-01", now=_now())
    signals = check(home=tmp_path, now=_now(2026, 9, 20))
    assert len(signals) == 1
    assert signals[0]["grade"] in ("SILENT", "NUDGE", "CARD", "ESCALATE")


def test_persistence_roundtrip(tmp_path):
    st = PromiseStore(home=tmp_path)
    st.make("persist me", due="2026-09-20")
    st2 = PromiseStore(home=tmp_path)
    assert len(st2.list()) == 1
    assert st2.make("another")["id"] == "p0002"


def test_home_resolution_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "alt"))
    st = PromiseStore()
    st.make("env-home promise")
    assert (tmp_path / "alt" / ".levi" / "promises" / "promises.json").exists()
