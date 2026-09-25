"""Tests for the ternary signal model (dormant / gathering / breakout)."""

from levi.demandpulse import ternary


def test_dormant_below_floor():
    sig = ternary.classify("widgets", [0, 1, 2, 1])
    assert sig.state == ternary.DORMANT
    assert sig.label == "INFERENCE"
    assert sig.basis  # basis always present


def test_empty_history_is_dormant_not_exception():
    sig = ternary.classify("widgets", [])
    assert sig.state == ternary.DORMANT
    assert "no observations" in sig.basis


def test_gathering_is_the_third_state():
    # Above the floor, below the breakout bar, no spike: neither hot nor
    # quiet — the state competitor binaries leave invisible.
    sig = ternary.classify("widgets", [1, 3, 4, 5])
    assert sig.state == ternary.GATHERING
    assert sig.velocity == 5 - 4


def test_breakout_on_bar():
    sig = ternary.classify("widgets", [1, 2, 9])
    assert sig.state == ternary.BREAKOUT


def test_breakout_on_spike_multiple():
    sig = ternary.classify("widgets", [3, 3, 10])  # 10 >= 3x3
    assert sig.state == ternary.BREAKOUT


def test_no_spike_off_weak_base():
    # 3x off a base below the floor is not a breakout — it's gathering.
    sig = ternary.classify("widgets", [1, 1, 3])
    assert sig.state == ternary.GATHERING


def test_deterministic():
    first = ternary.classify("widgets", [2, 4, 5])
    second = ternary.classify("widgets", [2, 4, 5])
    assert first.to_record() == second.to_record()


def test_classify_all_sorts_by_subject():
    out = ternary.classify_all({"b": [0, 0, 1], "a": [9, 9, 9]})
    assert [s.subject for s in out] == ["a", "b"]
    assert out[0].state == ternary.BREAKOUT
    assert out[1].state == ternary.DORMANT


def test_record_shape():
    rec = ternary.classify("widgets", [1, 3, 4]).to_record()
    assert set(rec) == {"subject", "state", "label", "basis", "counts", "velocity"}
    assert rec["state"] in ternary.STATES
