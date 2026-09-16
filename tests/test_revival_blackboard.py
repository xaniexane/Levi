"""Tests for levi.revival.blackboard — Hearsay-II blackboard (hermetic)."""

from __future__ import annotations

import pytest

from levi.revival.blackboard import Blackboard, demo_three_stage


def test_post_and_retrieve_hypothesis():
    bb = Blackboard()
    h = bb.post_hypothesis("t", "content", confidence=0.7, source="ks1")
    assert h.id == 1
    assert bb.hypotheses("t") == [h]
    assert bb.hypotheses("other") == []


def test_hypothesis_validation():
    bb = Blackboard()
    with pytest.raises(ValueError, match="non-empty string"):
        bb.post_hypothesis("", "x")
    with pytest.raises(ValueError, match="confidence"):
        bb.post_hypothesis("t", "x", confidence=1.5)


def test_competing_hypotheses_coexist_never_overwritten():
    bb = Blackboard()
    h1 = bb.post_hypothesis("doc:class", {"label": "incident"}, 0.8, source="ks-a")
    h2 = bb.post_hypothesis("doc:class", {"label": "note"}, 0.6, source="ks-b")
    both = bb.hypotheses("doc:class")
    assert h1 in both and h2 in both and len(both) == 2
    pairs = bb.conflicts()
    assert len(pairs) == 1
    assert tuple(pairs[0]) == (h1, h2) or tuple(pairs[0]) == (h2, h1)
    # best() picks highest confidence, does not delete the loser
    assert bb.best("doc:class") is h1
    assert len(bb.hypotheses("doc:class")) == 2


def test_agreeing_hypotheses_are_not_conflicts():
    bb = Blackboard()
    bb.post_hypothesis("t", "same", 0.5, source="a")
    bb.post_hypothesis("t", "same", 0.9, source="b")
    assert bb.conflicts() == []
    assert bb.best("t").confidence == 0.9


def test_highest_bidder_runs_not_registration_order():
    bb = Blackboard()
    ran = []

    bb.register_ks("low", ["*"], lambda b: ran.append("low"), bid=lambda bb, ks: 0.3)
    bb.register_ks("high", ["*"], lambda b: ran.append("high"), bid=lambda bb, ks: 0.9)
    bb.post_hypothesis("anything", 1, source="test")
    assert bb.run_cycle() == "high"
    assert ran == ["high"]
    bids = bb.bids()
    assert bids["high"] > bids["low"]


def test_default_bid_reacts_to_new_matching_hypotheses():
    bb = Blackboard()
    bb.register_ks("watcher", ["news"], lambda b: None)
    assert bb.bids() == {"watcher": 0.0}
    bb.post_hypothesis("news", "x", source="t")
    assert bb.bids() == {"watcher": 1.0}
    bb.run_cycle()
    assert bb.bids() == {"watcher": 0.0}  # consumed


def test_wildcard_and_predicate_interests():
    bb = Blackboard()
    seen = []
    bb.register_ks("wild", ["*"], lambda b: seen.append("wild"))
    bb.register_ks(
        "pred", [lambda topic: topic.startswith("doc:")], lambda b: seen.append("pred")
    )
    bb.post_hypothesis("doc:x", 1, source="t")
    bb.run_cycle()
    # tie on bid 1.0 -> registration order breaks the tie deterministically
    assert seen == ["wild"]


def test_run_until_stops_when_no_bids():
    bb = Blackboard()
    bb.register_ks(
        "idle",
        ["never-posted"],
        lambda b: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    assert bb.run_cycle() is None
    out = bb.run_until()
    assert out["cycles"] == 0 and out["exhausted"] is True


def test_run_until_respects_max_cycles():
    bb = Blackboard()
    # always bids 1.0 regardless of newness: a genuinely insatiable KS
    bb.register_ks(
        "eager",
        ["*"],
        lambda b: b.post_hypothesis("spam", 1, source="eager"),
        bid=lambda bb, ks: 1.0,
    )
    out = bb.run_until(max_cycles=5)
    assert out["cycles"] == 5 and out["exhausted"] is False


def test_ks_registration_validation():
    bb = Blackboard()
    with pytest.raises(ValueError, match="non-empty string"):
        bb.register_ks("", ["*"], lambda b: None)
    with pytest.raises(ValueError, match="callable"):
        bb.register_ks("x", ["*"], "not-callable")
    bb.register_ks("x", ["*"], lambda b: None)
    with pytest.raises(ValueError, match="already registered"):
        bb.register_ks("x", ["*"], lambda b: None)


def test_three_stage_demo_assembles_opportunistically():
    out = demo_three_stage()
    # KSs were registered in reverse pipeline order; bidding must still
    # produce classifier -> enricher -> summarizer
    assert out["run_order"] == ["classifier", "enricher", "summarizer"]
    assert out["exhausted"] is True
    summary = out["summary"]
    assert summary is not None
    assert summary.confidence == 0.9
    assert "incident" in str(summary.content)
    assert "urgent" in str(summary.content)


def test_run_log_records_execution_order():
    bb = Blackboard()
    order = []
    bb.register_ks(
        "a",
        ["*"],
        lambda b: order.append("a"),
        bid=lambda bb, ks: 0.5 if not order else 0.0,
    )
    bb.register_ks(
        "b",
        ["*"],
        lambda b: order.append("b"),
        bid=lambda bb, ks: 0.9 if not order else 0.0,
    )
    bb.post_hypothesis("t", 1, source="test")
    bb.run_until()
    assert order[0] == "b"
    assert bb.run_log[0] == "b"
