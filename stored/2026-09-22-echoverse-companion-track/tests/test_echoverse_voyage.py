"""Tests for the Echoverse voyage engine — the fated-outcome core.

Chauncey's concepts under test: a sealed fated outcome, a voyage
walked beat by beat on taken / not-taken / wild branches, a journal of
lived beats, earned rapport scored from lived beats, and arrival as
the destination — not a loss.

Deterministic: every run uses explicit seeds; no test depends on wall
time or randomness. Hermetic: tmp home dirs only for persistence tests.
"""

import os
import stat

import pytest

from levi.echoverse.voyage import (
    BRANCHES,
    NOT_TAKEN,
    TAKEN,
    WILD,
    FateArrivedError,
    FateNotSealedError,
    FateSealedError,
    Voyage,
    load_voyage,
    voyage_dir,
)


def _sealed_voyage(hero="Hero", beats=5, seed=7) -> Voyage:
    v = Voyage(hero, beats=beats, seed=seed)
    v.seal_fate("the harbor that was never home")
    return v


# ---------------------------------------------------------------------------
# The fated outcome: sealed once, never changed.
# ---------------------------------------------------------------------------


def test_fate_seals_once_and_cannot_change():
    v = Voyage("Hero", beats=3, seed=1)
    assert v.sealed is False
    v.seal_fate("the lighthouse at the world's edge")
    assert v.sealed is True
    assert v.fate == "the lighthouse at the world's edge"
    with pytest.raises(FateSealedError):
        v.seal_fate("a different ending")


def test_fate_text_must_be_non_empty():
    v = Voyage("Hero", beats=3, seed=1)
    with pytest.raises(ValueError):
        v.seal_fate("")


def test_fate_unreadable_before_sealed():
    v = Voyage("Hero", beats=3, seed=1)
    with pytest.raises(FateNotSealedError):
        _ = v.fate


def test_voyage_needs_hero_and_positive_beats():
    with pytest.raises(ValueError):
        Voyage("", beats=3, seed=1)
    with pytest.raises(ValueError):
        Voyage("Hero", beats=0, seed=1)


# ---------------------------------------------------------------------------
# Beats: taken / not-taken / wild — his canonical branches.
# ---------------------------------------------------------------------------


def test_branches_are_his_canonical_three():
    assert set(BRANCHES) == {"taken", "not-taken", "wild"}
    assert (TAKEN, NOT_TAKEN, WILD) == ("taken", "not-taken", "wild")


def test_beats_walk_on_each_branch_and_land_in_journal():
    v = _sealed_voyage(beats=3)
    b1 = v.walk_beat(TAKEN, "took the north road")
    b2 = v.walk_beat(NOT_TAKEN, "left the south road behind")
    b3 = v.walk_beat(WILD, "a storm chose for us")
    assert [b.branch for b in (b1, b2, b3)] == [TAKEN, NOT_TAKEN, WILD]
    assert [b.text for b in v.journal] == [
        "took the north road",
        "left the south road behind",
        "a storm chose for us",
    ]
    assert v.branch_counts == {"taken": 1, "not-taken": 1, "wild": 1}
    assert v.beats_walked == 3


def test_unknown_branch_rejected():
    v = _sealed_voyage(beats=2)
    with pytest.raises(ValueError):
        v.walk_beat("sideways", "not one of his branches")


def test_empty_beat_text_rejected():
    v = _sealed_voyage(beats=2)
    with pytest.raises(ValueError):
        v.walk_beat(TAKEN, "   ")


def test_beats_cannot_be_walked_before_the_fate_is_sealed():
    v = Voyage("Hero", beats=3, seed=1)
    with pytest.raises(FateNotSealedError):
        v.walk_beat(TAKEN, "too soon")


# ---------------------------------------------------------------------------
# Arrival: the destination, not a loss.
# ---------------------------------------------------------------------------


def test_arrival_comes_exactly_when_the_voyage_is_walked_out():
    v = _sealed_voyage(beats=3)
    assert v.arrived is False
    v.walk_beat(TAKEN, "one")
    v.walk_beat(NOT_TAKEN, "two")
    assert v.arrived is False
    v.walk_beat(WILD, "three")
    assert v.arrived is True
    # Arrival reveals the sealed fate — the destination reached.
    assert v.fate == "the harbor that was never home"
    assert v.state()["arrived"] is True


def test_walking_past_arrival_raises_and_keeps_the_journal_intact():
    v = _sealed_voyage(beats=2)
    v.walk_beat(TAKEN, "one")
    v.walk_beat(TAKEN, "two")
    with pytest.raises(FateArrivedError):
        v.walk_beat(TAKEN, "one too many")
    assert v.beats_walked == 2
    assert len(v.journal) == 2


# ---------------------------------------------------------------------------
# Earned rapport: scored from lived beats, explicit rubric.
# ---------------------------------------------------------------------------


def test_rapport_is_earned_from_lived_beats():
    v = _sealed_voyage(beats=4)
    assert v.rapport == 0
    v.walk_beat(TAKEN, "one")
    assert v.rapport == 1
    v.walk_beat(WILD, "two")
    v.walk_beat(NOT_TAKEN, "three")
    assert v.rapport == 3
    # The rubric is a plain count of lived beats — readable, no flattery.
    assert v.rapport == len(v.journal)


# ---------------------------------------------------------------------------
# Determinism: same seed + same calls = same voyage.
# ---------------------------------------------------------------------------


def test_determinism_same_seed_same_voyage():
    def run():
        v = _sealed_voyage(beats=3, seed=42)
        v.walk_beat(TAKEN, "the road")
        v.walk_beat(WILD, "the storm")
        return [(b.id, b.branch, b.text) for b in v.journal]

    assert run() == run()


def test_beat_ids_derive_from_seed_branch_and_text():
    v1 = _sealed_voyage(beats=2, seed=11)
    v2 = _sealed_voyage(beats=2, seed=12)
    b1 = v1.walk_beat(TAKEN, "same words")
    b2 = v2.walk_beat(TAKEN, "same words")
    assert b1.id != b2.id  # different seed, different voyage


# ---------------------------------------------------------------------------
# Persistence: caller-supplied home, 0600 files.
# ---------------------------------------------------------------------------


def test_save_load_round_trip_preserves_the_voyage(tmp_path):
    v = _sealed_voyage(hero="Wayfarer", beats=3, seed=9)
    v.walk_beat(TAKEN, "first light")
    v.walk_beat(WILD, "the turn")
    path = v.save(tmp_path)
    assert path.exists()

    w = load_voyage(tmp_path, "Wayfarer", 9)
    assert w.hero == "Wayfarer"
    assert w.sealed is True
    assert w.fate == "the harbor that was never home"
    assert [b.text for b in w.journal] == ["first light", "the turn"]
    assert [b.id for b in w.journal] == [b.id for b in v.journal]
    assert w.rapport == v.rapport
    assert w.arrived == v.arrived


def test_saved_files_are_private(tmp_path):
    v = _sealed_voyage(beats=2)
    path = v.save(tmp_path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_voyage_dir_lives_under_caller_supplied_home(tmp_path):
    d = voyage_dir(tmp_path)
    assert str(d).startswith(str(tmp_path))
    assert d.parts[-3:] == (".levi", "echoverse", "voyages")


def test_state_is_a_plain_readable_summary():
    v = _sealed_voyage(beats=4, seed=3)
    v.walk_beat(TAKEN, "one")
    v.walk_beat(NOT_TAKEN, "two")
    s = v.state()
    assert s == {
        "hero": "Hero",
        "beats": 4,
        "beats_walked": 2,
        "sealed": True,
        "arrived": False,
        "rapport": 2,
        "branch_counts": {"taken": 1, "not-taken": 1, "wild": 0},
    }
