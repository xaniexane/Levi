"""Tests for automation maintenance windows (parse + gate + next)."""

from __future__ import annotations

from datetime import datetime

import pytest

from levi.automation.windows import (
    WindowError,
    gate,
    parse_window,
    parse_windows,
)


def dt(weekday_iso: str, hm: str) -> datetime:
    # 2026-09-21 is a Monday; offset by weekday (0=Mon..6=Sun)
    day = (
        21
        + {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}[
            weekday_iso
        ]
    )
    h, m = (int(p) for p in hm.split(":"))
    return datetime(2026, 9, day, h, m)


def test_simple_window():
    w = parse_window("Mon-Fri 09:00-17:00")
    assert w.contains(dt("Wed", "12:00"))
    assert not w.contains(dt("Wed", "18:00"))
    assert not w.contains(dt("Sat", "12:00"))


def test_overnight_wrap_spans_midnight():
    w = parse_window("Mon 22:00-06:00")
    assert w.contains(dt("Mon", "23:00"))
    assert w.contains(dt("Tue", "05:59"))  # Monday's window extends past midnight
    assert not w.contains(dt("Tue", "06:00"))
    assert not w.contains(dt("Mon", "21:59"))
    assert not w.contains(dt("Tue", "23:00"))  # Tuesday is not in the day set


def test_whole_day_window():
    w = parse_window("Sat,Sun")
    assert w.contains(dt("Sun", "03:00"))
    assert not w.contains(dt("Mon", "03:00"))


def test_window_set_union():
    ws = parse_windows("Mon-Fri 22:00-06:00; Sat,Sun")
    assert ws.allows(dt("Wed", "23:30"))
    assert ws.allows(dt("Sun", "10:00"))
    assert not ws.allows(dt("Wed", "12:00"))


def test_next_allowed_skips_to_window():
    ws = parse_windows("Mon-Fri 22:00-06:00")
    nxt = ws.next_allowed(dt("Wed", "12:00"))
    assert nxt is not None
    assert ws.allows(nxt)
    assert nxt > dt("Wed", "12:00")
    assert nxt.hour == 22 and nxt.minute == 0


def test_next_allowed_inside_returns_now():
    ws = parse_windows("Mon-Fri 09:00-17:00")
    now = dt("Wed", "10:00")
    assert ws.next_allowed(now) == now


def test_gate_allowed_and_deferred():
    ok = gate("nightly-backup", "Mon-Fri 22:00-06:00", dt("Wed", "23:00"))
    assert ok["decision"] == "allowed"
    held = gate("nightly-backup", "Mon-Fri 22:00-06:00", dt("Wed", "12:00"))
    assert held["decision"] == "deferred"
    assert held["next_allowed"] is not None


def test_gate_denies_unparseable_spec():
    bad = gate("flow", "Mon-Friday 99:99", dt("Wed", "12:00"))
    assert bad["decision"] == "denied"
    assert "unparseable" in str(bad["reason"])


@pytest.mark.parametrize(
    "spec",
    ["", "Funday 09:00-17:00", "Mon 25:00-26:00", "Mon 09:00-09:00", "Mon-Fri"],
)
def test_malformed_specs_rejected_or_handled(spec):
    if spec in ("", "Funday 09:00-17:00", "Mon 25:00-26:00", "Mon 09:00-09:00"):
        with pytest.raises(WindowError):
            parse_window(spec)
    else:  # "Mon-Fri" with no time part means the whole days
        assert parse_window(spec).contains(dt("Wed", "03:00"))
