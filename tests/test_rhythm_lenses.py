"""Tests for the rhythm lenses (time-of-day expression cadences)."""

from datetime import datetime

from levi.personas import rhythm_lenses
from levi.personas.lenses import Lens


def test_four_rhythms_registered():
    assert set(rhythm_lenses.RHYTHM_LENSES) == {"dawn", "day", "dusk", "night"}


def test_law_present():
    law = rhythm_lenses.RHYTHM_LAW
    assert "never overrides safety" in law
    assert "LEVI stays LEVI" in law
    assert "only how" in law


def test_lookup_and_default():
    assert rhythm_lenses.get_rhythm_lens("dusk").name == "Dusk"
    assert rhythm_lenses.get_rhythm_lens("nope") is None
    assert rhythm_lenses.resolve_rhythm("nope").id == rhythm_lenses.DEFAULT_RHYTHM
    assert rhythm_lenses.resolve_rhythm("night").id == "night"


def test_as_lens_roundtrip():
    lens = rhythm_lenses.get_rhythm_lens("dawn").as_lens()
    assert isinstance(lens, Lens)
    assert lens.id == "dawn"
    assert lens.text_fields()


def test_resolve_by_hour():
    assert rhythm_lenses.resolve(datetime(2026, 9, 27, 6, 0)).id == "dawn"
    assert rhythm_lenses.resolve(datetime(2026, 9, 27, 12, 0)).id == "day"
    assert rhythm_lenses.resolve(datetime(2026, 9, 27, 19, 0)).id == "dusk"
    assert rhythm_lenses.resolve(datetime(2026, 9, 27, 0, 0)).id == "night"
    assert rhythm_lenses.resolve(datetime(2026, 9, 27, 4, 59)).id == "night"


def test_quiet_hours_and_weekend_tint():
    assert rhythm_lenses.is_quiet_hours(datetime(2026, 9, 27, 1, 0))
    assert not rhythm_lenses.is_quiet_hours(datetime(2026, 9, 27, 14, 0))
    # 2026-09-27 is a Sunday
    assert rhythm_lenses.weekend_tint(datetime(2026, 9, 27, 14, 0)) is not None
    assert rhythm_lenses.weekend_tint(datetime(2026, 9, 28, 14, 0)) is None  # Monday


def test_no_mask_violations():
    bad = rhythm_lenses.mask_violations()
    assert bad == {}, f"mask violations found: {bad}"


def test_hours_documented():
    for r in rhythm_lenses.list_rhythm_lenses():
        assert "local" in r.hours
