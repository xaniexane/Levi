"""Hermetic tests for ``levi.drift`` — goal-drift instrument.

Synthetic activity data only. ``now`` is injected; tmp LEVI_HOME;
no network, no real ``~/.levi``.

Run:  python3 -m pytest tests/test_drift.py -q
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.drift import (  # noqa: E402
    WINDOW_DAYS,
    DriftTracker,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    h = tmp_path / "levi_home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return DriftTracker()


def _log(tracker, days_ago, tags, note):
    tracker.log_activity(tags, note, ts=NOW - timedelta(days=days_ago, hours=1))


def test_card_fires_on_real_divergence(tracker):
    tracker.set_goal(
        "ship-book", "Finish the book draft", tags=["deep-work", "writing"]
    )
    # 2 writing-ish activities, 12 novelty/admin activities: real drift.
    _log(tracker, 1, ["deep-work"], "drafted chapter 1")
    _log(tracker, 3, ["writing"], "edited intro")
    for i in range(12):
        _log(tracker, i % 13, ["novelty"], f"doomscrolled feed item {i}")
    card = tracker.weekly_card(now=NOW)
    assert card is not None
    assert card["grade"] == "CARD"
    assert card["tag"] == "[drift]"
    assert "ship-book" in card["drifting_goals"]
    # Evidence is concrete, not vague: counts and examples present.
    assert "12 activities" in card["body"]
    assert "novelty" in card["body"]
    assert "doomscrolled feed item 0" in card["body"]
    assert "0%" in card["body"] or "14%" in card["body"] or "2 of 14" in card["body"]


def test_stays_silent_on_alignment(tracker):
    tracker.set_goal("ship-book", "Finish the book draft", tags=["deep-work"])
    for i in range(10):
        _log(tracker, i % 13, ["deep-work"], f"draft session {i}")
    assert tracker.weekly_card(now=NOW) is None


def test_silent_when_too_little_data(tracker):
    tracker.set_goal("ship-book", "Finish the book draft", tags=["deep-work"])
    _log(tracker, 1, ["novelty"], "one random thing")
    # Fewer than MIN_ACTIVITIES: must not claim drift on silence.
    assert tracker.weekly_card(now=NOW) is None


def test_silent_with_no_goals(tracker):
    for i in range(10):
        _log(tracker, i % 13, ["novelty"], f"thing {i}")
    assert tracker.weekly_card(now=NOW) is None


def test_old_activity_outside_window_ignored(tracker):
    tracker.set_goal("ship-book", "Finish the book draft", tags=["deep-work"])
    _log(tracker, 30, ["novelty"], "old novelty")  # outside 14-day window
    for i in range(10):
        _log(tracker, i % 13, ["deep-work"], f"session {i}")
    assert tracker.weekly_card(now=NOW) is None


def test_partial_alignment_below_threshold_fires(tracker):
    tracker.set_goal("fitness", "Stay fit", tags=["exercise"])
    # share 1/10 = 10% < 20% threshold, with significant "novelty" elsewhere.
    _log(tracker, 1, ["exercise"], "one run")
    for i in range(9):
        _log(tracker, i % 13, ["novelty"], f"scroll {i}")
    card = tracker.weekly_card(now=NOW)
    assert card is not None
    assert card["grade"] == "CARD"
    assert card["activity_count"] == 10
    assert card["window_days"] == WINDOW_DAYS


def test_no_card_when_drift_tags_not_voluminous(tracker):
    # Goal missed its share but nothing else has volume either -> honest silence.
    tracker.set_goal("fitness", "Stay fit", tags=["exercise"])
    for i, tag in enumerate(["a", "b", "c", "d", "e"]):
        _log(tracker, i, [tag], f"scattered {i}")
    assert tracker.weekly_card(now=NOW) is None


def test_goal_redefinition_and_drop(tracker):
    g = tracker.set_goal("g1", "first", tags=["x"])
    assert g["tags"] == ["x"]
    g2 = tracker.set_goal("g1", "second", tags=["y"])
    assert g2["statement"] == "second"
    assert tracker.drop_goal("g1") is True
    assert tracker.drop_goal("g1") is False


def test_log_activity_requires_tags(tracker):
    with pytest.raises(ValueError):
        tracker.log_activity([], "no tags")


def test_module_level_wrappers_resolve_home_at_call_time(tmp_path, monkeypatch):
    import levi.drift as drift_mod

    h = tmp_path / "home1"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    drift_mod.set_goal("g", "stmt", tags=["deep-work"])
    h2 = tmp_path / "home2"
    h2.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h2))
    assert drift_mod.weekly_card(now=NOW) is None  # fresh home: no goals, silent
