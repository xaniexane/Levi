"""Tests for levi.demand.alerts — Copilot-style DemandPulse notifications."""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from levi.demand.alerts import (
    Alert,
    AlertEngine,
    AlertEvent,
    _now_local,
    _resolve_timezone,
    in_quiet_hours,
)
from levi.demand.pulse import DemandPulse


def _local(year=2026, month=9, day=21, hour=12, minute=0):
    return datetime(year, month, day, hour, minute).astimezone()


def _dp_with_content(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("truckers need simpler dispatch logs", segment="trucking")
    opp = dp.score_opportunity(
        sig.id, "Dispatch-lite", demand_score=0.9, serviceability=0.9, startup_cost=0.1
    )
    card = dp.score_five_factor(
        sig.id,
        "Dispatch-lite",
        {
            "demand": (90, "three fleet owners asked this week"),
            "market_size": (80, "regional carriers underserved"),
            "competition_gap": (85, "no offline-first tool exists"),
            "trend_velocity": (70, "ELD complaints rising"),
            "entry_feasibility": (88, "levi stack already fits"),
        },
    )
    assert card.alert  # composite well above 75
    return dp, sig, opp, card


def _engine(tmp_path):
    return AlertEngine(path=tmp_path / "alerts.json")


# ---- quiet hours -----------------------------------------------------------


def test_quiet_hours_wrap_midnight():
    now = _local(hour=23, minute=30)
    assert in_quiet_hours(now, "22:00", "07:00")
    assert not in_quiet_hours(_local(hour=12), "22:00", "07:00")
    assert in_quiet_hours(_local(hour=6, minute=59), "22:00", "07:00")


def test_quiet_hours_no_wrap():
    assert in_quiet_hours(_local(hour=2), "01:00", "05:00")
    assert not in_quiet_hours(_local(hour=12), "01:00", "05:00")


def test_quiet_hours_equal_means_never():
    assert not in_quiet_hours(_local(hour=3), "00:00", "00:00")


def test_bad_hhmm_rejected():
    with pytest.raises(ValueError):
        in_quiet_hours(_local(), "25:00", "07:00")
    with pytest.raises(ValueError):
        Alert(
            id="x",
            type="briefing",
            name="b",
            time="7am",
        )


# ---- alert definition validation --------------------------------------------


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        Alert(id="x", type="pager", name="p")


def test_watch_needs_segment():
    with pytest.raises(ValueError):
        Alert(id="x", type="watch", name="w", segment="")


def test_reminder_needs_message_and_at():
    with pytest.raises(ValueError):
        Alert(id="x", type="reminder", name="r", recurrence="once", at="")
    with pytest.raises(ValueError):
        Alert(
            id="x",
            type="reminder",
            name="r",
            recurrence="once",
            at="2026-09-22T09:00:00",
            message="",
        )


def test_unknown_channel_rejected():
    with pytest.raises(ValueError):
        Alert(id="x", type="briefing", name="b", channels=("smoke-signal",))


# ---- threshold alerts --------------------------------------------------------


def test_threshold_fires_on_hot_card_then_dedups(tmp_path):
    dp, sig, opp, card = _dp_with_content(tmp_path)
    eng = _engine(tmp_path)
    eng.create("threshold", "hot stuff", threshold=75.0)
    first = eng.evaluate(dp, now=_local(hour=12))
    assert any(e.kind == "threshold" and "crossed threshold" in e.title for e in first)
    second = eng.evaluate(dp, now=_local(hour=13))
    assert [e for e in second if e.kind == "threshold"] == []


def test_threshold_respects_bar(tmp_path):
    dp, sig, opp, card = _dp_with_content(tmp_path)
    eng = _engine(tmp_path)
    eng.create("threshold", "sky high", threshold=99.0, worth_bar=0.99)
    events = eng.evaluate(dp, now=_local(hour=12))
    assert events == []


# ---- watch alerts ------------------------------------------------------------


def test_watch_fires_on_segment_signal(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    eng = _engine(tmp_path)
    eng.create("watch", "trucking watch", segment="trucking")
    assert eng.evaluate(dp, now=_local(hour=12)) == []
    sig = dp.scan_seed("need cheaper reefer fuel", segment="trucking")
    events = eng.evaluate(dp, now=_local(hour=12))
    assert len(events) == 1
    assert sig.id in events[0].dedup_key
    assert "HYPOTHESIS" in events[0].lines[0]
    # other segments stay silent
    dp.scan_seed("need better coffee", segment="general")
    assert eng.evaluate(dp, now=_local(hour=13)) == []


# ---- briefing -----------------------------------------------------------------


def test_briefing_fires_once_per_day_after_time(tmp_path):
    dp, sig, opp, card = _dp_with_content(tmp_path)
    eng = _engine(tmp_path)
    eng.create("briefing", "morning", time="07:00", recurrence="daily")
    assert eng.evaluate(dp, now=_local(hour=6, minute=59)) == []
    first = eng.evaluate(dp, now=_local(hour=7, minute=30))
    assert len(first) == 1 and first[0].kind == "briefing"
    assert "Dispatch-lite" in "\n".join(first[0].lines)
    assert eng.evaluate(dp, now=_local(hour=18)) == []
    assert len(eng.evaluate(dp, now=_local(day=22, hour=8))) == 1


# ---- reminders ------------------------------------------------------------------


def test_one_shot_reminder_fires_once(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    eng = _engine(tmp_path)
    eng.create(
        "reminder",
        "call back",
        recurrence="once",
        at="2026-09-21T15:00:00",
        message="Call the fleet owner",
        quiet_start="00:00",
        quiet_end="00:00",  # never quiet
    )
    assert eng.evaluate(dp, now=_local(hour=14)) == []
    events = eng.evaluate(dp, now=_local(hour=15, minute=5))
    assert len(events) == 1
    assert events[0].lines == ["Call the fleet owner"]
    assert eng.evaluate(dp, now=_local(hour=16)) == []


# ---- quiet hours hold, then flush -------------------------------------------------


def test_quiet_hours_hold_and_flush(tmp_path):
    dp, sig, opp, card = _dp_with_content(tmp_path)
    eng = _engine(tmp_path)
    outbox = tmp_path / "outbox.jsonl"
    eng.create(
        "threshold",
        "night owl",
        threshold=75.0,
        channels=("file",),
        quiet_start="22:00",
        quiet_end="07:00",
    )
    receipt = eng.run(dp, now=_local(hour=23), outbox=outbox)
    assert receipt["held"] >= 1 and receipt["delivered"] == 0
    assert not outbox.exists()  # nothing delivered during quiet hours
    receipt2 = eng.run(dp, now=_local(day=22, hour=8), outbox=outbox)
    assert receipt2["flushed"] >= 1
    assert outbox.exists()
    stored = [json.loads(line) for line in outbox.read_text().splitlines()]
    assert stored and stored[0]["held"] is False


# ---- delivery ---------------------------------------------------------------------


def test_push_and_email_report_not_configured(tmp_path):
    eng = _engine(tmp_path)
    event = AlertEvent(
        alert_id="nope",
        alert_name="ghost",
        kind="reminder",
        title="Reminder",
        lines=["hi"],
        dedup_key="k",
    )
    status = eng.deliver(event, channels=("push", "email"), outbox=tmp_path / "o.jsonl")
    assert status == {"push": "not_configured", "email": "not_configured"}


def test_file_channel_appends_jsonl(tmp_path):
    eng = _engine(tmp_path)
    outbox = tmp_path / "o.jsonl"
    event = AlertEvent(
        alert_id="nope",
        alert_name="ghost",
        kind="reminder",
        title="Reminder",
        lines=["hi"],
        dedup_key="k",
    )
    assert eng.deliver(event, channels=("file",), outbox=outbox) == {
        "file": "delivered"
    }
    assert json.loads(outbox.read_text().splitlines()[0])["title"] == "Reminder"


def test_card_rendering_labels_hypothesis(tmp_path):
    event = AlertEvent(
        alert_id="a",
        alert_name="n",
        kind="watch",
        title="t",
        lines=["x [HYPOTHESIS, confidence 0.35]"],
        dedup_key="k",
    )
    card = event.render_card()
    assert "HYPOTHESIS" in card
    assert "verified OBSERVED" in card


# ---- management ----------------------------------------------------------------------


def test_delete_and_disable(tmp_path):
    eng = _engine(tmp_path)
    a = eng.create("briefing", "m", time="07:00")
    assert eng.set_enabled(a.id, False) is True
    assert eng.get(a.id).enabled is False
    assert eng.delete(a.id) is True
    assert eng.get(a.id) is None
    assert eng.delete("missing") is False


def test_store_roundtrip(tmp_path):
    eng = _engine(tmp_path)
    a = eng.create("watch", "w", segment="trucking")
    eng2 = AlertEngine(path=tmp_path / "alerts.json")
    assert eng2.get(a.id) is not None
    assert eng2.get(a.id).segment == "trucking"


# ---- user-timezone anchoring ------------------------------------------------------


def test_now_local_anchored_to_user_timezone():
    now = _now_local()
    assert str(now.tzinfo) == "America/Chicago"


def test_resolve_timezone_env_override_and_invalid_fallback(monkeypatch):
    monkeypatch.setenv("LEVI_TZ", "UTC")
    assert _resolve_timezone() == "UTC"
    monkeypatch.setenv("LEVI_TZ", "Not/AZone")
    # invalid names fall back instead of crashing the unattended sweep
    assert _resolve_timezone() == "America/Chicago"


def test_briefing_due_at_0700_chicago_not_0700_utc(tmp_path):
    # Regression: the sweep host runs UTC, so the 07:00 briefing must be
    # evaluated in America/Chicago. 12:05 UTC == 07:05 Chicago (CDT): due.
    # 07:05 UTC == 02:05 Chicago: not due, and inside quiet hours.
    chicago = ZoneInfo("America/Chicago")
    dp, _, _, _ = _dp_with_content(tmp_path)
    eng = _engine(tmp_path)
    eng.create("briefing", "morning", time="07:00", recurrence="daily")
    due = datetime(2026, 9, 22, 12, 5, tzinfo=timezone.utc).astimezone(chicago)
    assert (due.hour, due.minute) == (7, 5)
    assert len(eng.evaluate(dp, now=due)) == 1
    too_early = datetime(2026, 9, 22, 7, 5, tzinfo=timezone.utc).astimezone(chicago)
    assert (too_early.hour, too_early.minute) == (2, 5)
    assert in_quiet_hours(too_early, "22:00", "07:00")
    assert eng.evaluate(dp, now=too_early) == []
