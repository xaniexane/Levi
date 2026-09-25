"""Tests for levi.persona.seasons — temporal personality modulation."""

from __future__ import annotations

from datetime import datetime

from levi.persona.seasons import (
    TONES,
    describe,
    seasonal_weights,
    streak_bend,
)

BASE = {t: 0.5 for t in TONES}


def test_tones_are_the_eight_canonical_axes():
    assert set(TONES) == {
        "warmth",
        "brevity",
        "playfulness",
        "formality",
        "reflection",
        "curiosity",
        "momentum",
        "restraint",
    }


def test_pure_and_bounded():
    # Midnight: brevity should bend DOWN relative to a midday baseline.
    night = seasonal_weights(BASE, datetime(2026, 3, 15, 23, 0), 0)
    day = seasonal_weights(BASE, datetime(2026, 3, 15, 10, 0), 0)
    assert night["brevity"] < day["brevity"]  # night is less terse
    assert night["reflection"] > day["reflection"]  # night more reflective
    for w in night.values():
        assert 0.0 <= w <= 1.0
    # Deterministic: same inputs, same outputs.
    assert seasonal_weights(BASE, datetime(2026, 3, 15, 23, 0), 0) == night


def test_unknown_axes_pass_through():
    out = seasonal_weights({**BASE, "mystery": 0.7}, datetime(2026, 1, 1, 12))
    assert out["mystery"] == 0.7
    assert len(out) == len(BASE) + 1


def test_seasonal_bends_differ():
    spring = seasonal_weights(BASE, datetime(2026, 4, 1, 12), 0)
    winter = seasonal_weights(BASE, datetime(2026, 1, 1, 12), 0)
    assert spring["curiosity"] > winter["curiosity"]
    assert winter["restraint"] > spring["restraint"]


def test_streak_nudges_familiarity_then_plateaus():
    b0 = streak_bend(0)
    b3 = streak_bend(3)
    b7 = streak_bend(7)
    b30 = streak_bend(30)
    assert b0["warmth"] <= b3["warmth"] <= b7["warmth"]
    assert b7["warmth"] == b30["warmth"]  # plateau
    assert b3["formality"] < b0["formality"]  # less formal with familiarity
    # Silence decays, never punishes below a floor.
    b_neg = streak_bend(-3)
    assert b_neg["warmth"] < b0["warmth"]
    assert b_neg["warmth"] >= 0.95


def test_describe_names_part_and_season():
    assert describe(datetime(2026, 7, 1, 6, 30))["part_of_day"] == "dawn"
    assert describe(datetime(2026, 7, 1, 6, 30))["season"] == "summer"
    assert describe(datetime(2026, 12, 1, 3, 0))["part_of_day"] == "deep night"
    assert describe(datetime(2026, 12, 1, 3, 0))["season"] == "winter"
    assert describe(datetime(2026, 10, 1, 19, 0))["season"] == "autumn"
