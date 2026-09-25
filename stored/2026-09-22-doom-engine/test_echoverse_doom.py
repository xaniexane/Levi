"""Tests for the Echoverse doom engine (play-to-lose narrative mechanics).

Deterministic: every run uses explicit seeds; no test depends on wall
time or randomness beyond the seeded stream. Hermetic: tmp home dirs
only for persistence tests.
"""

import os
import stat

import pytest

from levi.echoverse import doom
from levi.echoverse.doom import (
    CheckResult,
    DoomArrivedError,
    DoomNotSealedError,
    DoomSealedError,
    Voyage,
    doom_dir,
    load_voyage,
)


def _sealed_voyage(hero="Hero", doom_ticks=5, seed=7) -> Voyage:
    v = Voyage(hero, doom_ticks=doom_ticks, seed=seed)
    v.seal_doom("the harbor that was never home")
    return v


# ---------------------------------------------------------------------------
# Clock: advances monotonically, never reverses.
# ---------------------------------------------------------------------------


def test_clock_advances_monotonically_and_never_reverses():
    v = _sealed_voyage(doom_ticks=5)
    seen = [v.clock]
    for _ in range(5):
        v.check(0.5)
        seen.append(v.clock)
    assert seen == [0, 1, 2, 3, 4, 5]  # strictly increasing: never reverses


def test_doom_reached_exactly_when_clock_fills():
    v = _sealed_voyage(doom_ticks=3)
    assert not v.doomed
    v.check(0.5)
    assert not v.doomed
    v.check(0.5)
    assert not v.doomed
    result = v.check(0.5)
    assert result.doomed is True
    assert v.doomed
    assert v.clock == 3
    with pytest.raises(DoomArrivedError):
        v.check(0.5)


def test_clock_never_advances_past_doom():
    v = _sealed_voyage(doom_ticks=2)
    v.check(0.5)
    v.check(0.5)
    assert v.clock == 2
    with pytest.raises(DoomArrivedError):
        v.check(0.5)
    assert v.clock == 2  # the refused check did not touch the clock


# ---------------------------------------------------------------------------
# Echo: deeds feed reputation; reputation shifts check odds.
# ---------------------------------------------------------------------------


def test_marks_feed_echo():
    v = _sealed_voyage()
    assert v.echo == 0.0
    v.record_mark("shared bread with a stranger", 2.0)
    v.record_mark("broke a sworn oath", -5.0)
    assert v.echo == pytest.approx(-3.0)
    assert len(v.marks) == 2
    assert v.marks[0].index == 0
    assert v.marks[1].index == 1


def test_echo_shifts_check_odds_in_expected_direction():
    # Same seed -> same roll stream; only the echo differs.
    pos_wins = neg_wins = base_wins = 0
    trials = 300
    for trial in range(trials):
        base = _sealed_voyage(hero="base", doom_ticks=10**9, seed=trial)
        pos = _sealed_voyage(hero="pos", doom_ticks=10**9, seed=trial)
        neg = _sealed_voyage(hero="neg", doom_ticks=10**9, seed=trial)
        pos.record_mark("a bright deed", 10.0)  # echo +10 -> shift +0.25
        neg.record_mark("a dark deed", -10.0)  # echo -10 -> shift -0.25
        base_wins += base.check(0.5).success
        pos_wins += pos.check(0.5).success
        neg_wins += neg.check(0.5).success
    assert pos_wins > base_wins > neg_wins


def test_check_records_deed_after_resolution():
    v = _sealed_voyage(seed=11)
    before_echo = v.echo
    result = v.check(0.5, deed="faced the storm", weight=3.0)
    # The deed fed the echo only after this check resolved.
    assert result.shift == pytest.approx(before_echo / doom.ECHO_SCALE)
    assert v.echo == pytest.approx(before_echo + 3.0)
    assert v.marks[-1].deed == "faced the storm"


def test_shift_is_bounded():
    v = _sealed_voyage(doom_ticks=10**9, seed=3)
    v.record_mark("legend", 10_000.0)
    result = v.check(0.5)
    assert result.shift == pytest.approx(doom.MAX_SHIFT)
    v2 = _sealed_voyage(doom_ticks=10**9, seed=3)
    v2.record_mark("infamy", -10_000.0)
    result2 = v2.check(0.5)
    assert result2.shift == pytest.approx(-doom.MAX_SHIFT)


# ---------------------------------------------------------------------------
# Sealed doom: fixed at the start, never changed mid-run.
# ---------------------------------------------------------------------------


def test_doom_sealed_cannot_be_changed():
    v = Voyage("Hero", doom_ticks=3, seed=1)
    v.seal_doom("the harbor that was never home")
    assert v.sealed
    assert v.doom_text == "the harbor that was never home"
    with pytest.raises(DoomSealedError):
        v.seal_doom("a different ending")


def test_check_requires_sealed_doom():
    v = Voyage("Hero", doom_ticks=3, seed=1)
    with pytest.raises(DoomNotSealedError):
        v.check(0.5)
    with pytest.raises(DoomNotSealedError):
        _ = v.doom_text


def test_doom_text_readable_after_seal():
    v = _sealed_voyage()
    assert v.doom_text == "the harbor that was never home"


# ---------------------------------------------------------------------------
# Determinism: same seed + same calls = same run.
# ---------------------------------------------------------------------------


def test_determinism_same_seed_same_run():
    def run(seed):
        v = _sealed_voyage(hero="A", doom_ticks=4, seed=seed)
        out = []
        out.append(v.check(0.4, deed="first deed", weight=1.5).success)
        out.append(v.check(0.6, deed="second deed", weight=-2.0).success)
        out.append(v.check(0.5).success)
        out.append(v.check(0.9, deed="last deed", weight=4.0).success)
        return out, [m.weight for m in v.marks], v.clock, v.echo

    a = run(42)
    b = run(42)
    assert a == b


def test_different_seeds_may_differ():
    def outcomes(seed):
        v = _sealed_voyage(doom_ticks=10**9, seed=seed)
        return [v.check(0.5).success for _ in range(10)]

    assert outcomes(1) != outcomes(999)


# ---------------------------------------------------------------------------
# Persistence: caller-supplied home, 0600 files, stream preserved.
# ---------------------------------------------------------------------------


def test_save_load_roundtrip_preserves_roll_stream(tmp_path):
    v = _sealed_voyage(hero="Saver", doom_ticks=5, seed=21)
    v.check(0.5, deed="early deed", weight=2.0)
    v.check(0.7)
    path = v.save(tmp_path)
    assert path.exists()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600

    loaded = load_voyage(tmp_path, "Saver", 21)
    assert loaded.hero == "Saver"
    assert loaded.clock == 2
    assert loaded.sealed
    assert loaded.doom_text == "the harbor that was never home"
    assert loaded.echo == pytest.approx(2.0)
    assert len(loaded.marks) == 1  # only the first check carried a deed

    # The loaded voyage continues the identical roll stream.
    expected = v.check(0.5)
    got = loaded.check(0.5)
    assert (got.success, got.roll, got.clock) == (
        expected.success,
        expected.roll,
        expected.clock,
    )


def test_save_uses_caller_supplied_home_only(tmp_path):
    v = _sealed_voyage(hero="Homer", seed=5)
    path = v.save(tmp_path)
    assert str(path).startswith(str(tmp_path))
    assert doom_dir(tmp_path).exists()


# ---------------------------------------------------------------------------
# Validation.
# ---------------------------------------------------------------------------


def test_validation():
    with pytest.raises(ValueError):
        Voyage("", doom_ticks=3, seed=1)
    with pytest.raises(ValueError):
        Voyage("H", doom_ticks=0, seed=1)
    v = _sealed_voyage()
    with pytest.raises(ValueError):
        v.check(1.5)
    v2 = Voyage("H", doom_ticks=3, seed=1)
    with pytest.raises(ValueError):
        v2.seal_doom("")


def test_result_shape():
    v = _sealed_voyage(seed=9)
    result = v.check(0.5)
    assert isinstance(result, CheckResult)
    assert 0.0 <= result.roll < 1.0
    assert isinstance(result.success, bool)
    assert result.clock == 1
