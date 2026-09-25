"""Tests for the season engine — work/rest rhythm."""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def run(**kwargs):
    return registry.run("season", kwargs)


def test_registered():
    assert registry.get("season").id == "season"


def test_rest_season_hot_stretch_no_rest():
    # 14 days at 5/day, zero quiet days: hot and rest short.
    r = run(daily_loads=[5] * 14)
    assert r.verdict["season"] == "rest"
    assert r.verdict["quiet_days"] == 0
    assert r.verdict["next_rest_due_days"] == 2
    assert r.verdict["rest_kept"] is False


def test_surge_season_high_load_rest_kept():
    loads = [9, 9, 9, 9, 9, 0, 0] * 2  # avg ~6.43/day, rest kept
    r = run(daily_loads=loads)
    assert r.verdict["season"] == "surge"
    assert r.verdict["rest_kept"] is True
    assert r.verdict["next_rest_due_days"] == 0


def test_steady_season():
    r = run(daily_loads=[2, 1, 3, 0, 2, 1, 0, 2, 3, 1, 2, 0, 1, 2])
    assert r.verdict["season"] == "steady"


def test_all_quiet_is_steady_not_surge():
    r = run(daily_loads=[0] * 14)
    assert r.verdict["season"] == "steady"
    assert r.verdict["avg_daily_load"] == 0.0


def test_short_list_pads_with_zeros():
    r = run(daily_loads=[5, 5, 5])
    # padded to 14 with zeros: avg low, rest kept -> steady
    assert r.verdict["avg_daily_load"] == round(15 / 14, 2)
    assert r.verdict["season"] == "steady"


def test_custom_thresholds():
    r = run(daily_loads=[4] * 12 + [0, 0], surge_threshold=3.0)
    assert r.verdict["season"] == "surge"


def test_deny_closed():
    with pytest.raises(EngineInputError):
        run(daily_loads="nope")
    with pytest.raises(EngineInputError):
        run(daily_loads=[-1] * 14)
    with pytest.raises(EngineInputError):
        run(daily_loads=[1] * 15)
    with pytest.raises(EngineInputError):
        run(daily_loads=[1] * 14, rest_target_days=0)
    with pytest.raises(EngineInputError):
        run(daily_loads=[1] * 14, surge_threshold=0)


def test_deterministic():
    loads = [3, 0, 5, 2, 1, 0, 4, 3, 2, 1, 6, 0, 2, 3]
    a = run(daily_loads=loads)
    b = run(daily_loads=loads)
    assert a.verdict == b.verdict
