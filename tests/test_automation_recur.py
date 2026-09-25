"""Tests for levi.automation.recur — recurrence phrase parsing."""

from datetime import datetime, timedelta

import pytest

from levi.automation.recur import (
    MODULE_NAME,
    PROVIDES,
    RecurError,
    parse,
    register_capabilities,
)
from levi.interop.registry import Registry


def test_parse_every_6h():
    rec = parse("every 6h", now=datetime(2026, 9, 21, 12, 0))
    assert rec.to_interval_seconds() == 21600
    assert rec.describe() == "every 6 hours"


def test_parse_bare_words():
    assert parse("hourly").to_interval_seconds() == 3600
    assert parse("daily").kind == "daily_at"
    assert parse("weekly").kind == "weekly_on"
    assert parse("monthly").kind == "monthly_on"


def test_parse_every_day_week_month():
    # "every day"/"every week" are anchored intervals; months are calendar-based
    assert parse("every day").to_interval_seconds() == 86400
    assert parse("every week").to_interval_seconds() == 604800
    assert parse("every month").kind == "monthly_on"
    assert parse("every hour").to_interval_seconds() == 3600


def test_interval_next_after():
    anchor = datetime(2026, 9, 21, 12, 0)
    rec = parse("every 2h", now=anchor)
    assert rec.next_after(anchor + timedelta(hours=3)) == anchor + timedelta(hours=4)
    # strictly after: exactly on a tick goes to the next one
    assert rec.next_after(anchor + timedelta(hours=2)) == anchor + timedelta(hours=4)
    # before the anchor returns the anchor itself
    assert rec.next_after(anchor - timedelta(minutes=1)) == anchor


def test_daily_at():
    rec = parse("daily at 06:45")
    assert rec.describe() == "daily at 06:45"
    assert rec.next_after(datetime(2026, 9, 21, 5, 0)) == datetime(2026, 9, 21, 6, 45)
    assert rec.next_after(datetime(2026, 9, 21, 7, 0)) == datetime(2026, 9, 22, 6, 45)


def test_daily_at_pm():
    rec = parse("daily at 6:45pm")
    assert (rec.hour, rec.minute) == (18, 45)
    assert rec.next_after(datetime(2026, 9, 21, 17, 0)) == datetime(2026, 9, 21, 18, 45)


def test_weekly_on_monday():
    # 2026-09-21 is a Monday
    monday = datetime(2026, 9, 21)
    rec = parse("weekly on monday at 09:00")
    assert rec.describe() == "weekly on Monday at 09:00"
    # Monday 10:00 -> next Monday 09:00 (same-day past time rolls a week)
    assert rec.next_after(monday + timedelta(hours=10)) == monday + timedelta(
        days=7, hours=9
    )
    # Sunday before -> the coming Monday
    assert rec.next_after(monday - timedelta(days=1)) == monday + timedelta(hours=9)


def test_weekly_on_abbrev():
    rec = parse("weekly on fri")
    assert rec.weekday == 4


def test_monthly_on_the_31st_clamps():
    rec = parse("monthly on the 31st")
    # February 2026 has 28 days -> clamps, never skips the month
    assert rec.next_after(datetime(2026, 2, 10)) == datetime(2026, 2, 28)
    # after Feb 28, March 31 is next
    assert rec.next_after(datetime(2026, 2, 28, 0, 0, 1)) == datetime(2026, 3, 31)


def test_monthly_to_interval_is_none():
    assert parse("monthly on the 3rd").to_interval_seconds() is None


def test_next_n_strictly_increasing():
    rec = parse("every 90m", now=datetime(2026, 9, 21, 12, 0))
    runs = rec.next_n(datetime(2026, 9, 21, 12, 0), 4)
    assert len(runs) == 4
    assert all(b > a for a, b in zip(runs, runs[1:], strict=False))
    assert runs[0] == datetime(2026, 9, 21, 13, 30)


def test_garbage_raises():
    for bad in (
        "sometime-ish",
        "every",
        "daily sometime",
        "weekly on frob",
        "monthly on the 45th",
        "every 0h",
        "every -3d",
    ):
        with pytest.raises(RecurError):
            parse(bad)


def test_register_capabilities():
    reg = Registry()
    register_capabilities(reg)
    assert MODULE_NAME in reg.modules()
    assert PROVIDES[0] in reg.declaration(MODULE_NAME)["provides"]
    reg.check_all()  # must not raise
