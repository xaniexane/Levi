"""Tests for levi.identity.reim (compost) and levi.identity.riem (compress)."""

from levi.identity.reim import REIM
from levi.identity.riem import RIEM


def _failure_outcome():
    return {
        "identity": "parent#0",
        "success": False,
        "score": 0.3,
        "notes": "drifted past threshold during evaluation",
        "failures": ["param drift: tempo overflow past threshold"],
    }


def test_compost_extracts_signature_and_cause():
    lessons = REIM().compost(_failure_outcome())
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["kind"] == "failure"
    assert len(lesson["failure_signature"]) == 16
    assert lesson["cause"] == "param-drift"
    assert lesson["severity"] == "high"
    assert "drift" in lesson["notes_excerpt"]  # raw info retained


def test_compost_success_is_reinforcement():
    lessons = REIM().compost(
        {"identity": "x", "success": True, "score": 0.9, "notes": "", "failures": []}
    )
    assert lessons[0]["kind"] == "reinforcement"
    assert lessons[0]["cause"] == "none"


def test_compost_deterministic():
    assert REIM().compost(_failure_outcome()) == REIM().compost(_failure_outcome())


def test_compress_deterministic():
    lessons = REIM().compost(_failure_outcome())
    a = RIEM().compress(lessons, {"signatures": {}})
    b = RIEM().compress(lessons, {"signatures": {}})
    assert a == b


def test_high_severity_promotes_immediately():
    lessons = REIM().compost(_failure_outcome())  # high severity
    deltas = RIEM().compress(lessons, {"signatures": {}})
    assert deltas["promoted_count"] == 1
    promoted = deltas["promoted"][0]
    # lossless-of-signal: signature + cause retained
    assert promoted["failure_signature"] == lessons[0]["failure_signature"]
    assert promoted["cause"] == lessons[0]["cause"]
    assert deltas["trait_adjustments"]


def test_single_low_severity_lesson_drops_without_corroboration():
    outcome = {
        "identity": "x",
        "success": False,
        "score": 0.65,  # medium
        "notes": "",
        "failures": ["mysterious wobble with no clear keyword match zzz"],
    }
    lessons = REIM().compost(outcome)
    assert lessons[0]["severity"] == "medium"
    deltas = RIEM().compress(lessons, {"signatures": {}})
    assert deltas["promoted_count"] == 0
    assert deltas["dropped"] == 1


def test_corroboration_promotes():
    outcome = {
        "identity": "x",
        "success": False,
        "score": 0.65,
        "notes": "",
        "failures": ["mysterious wobble with no clear keyword match zzz"],
    }
    lessons = REIM().compost(outcome)
    sig = lessons[0]["failure_signature"]
    deltas = RIEM().compress(lessons + lessons, {"signatures": {sig: 0}})
    assert deltas["promoted_count"] == 1
    assert deltas["promoted"][0]["corroboration"] >= 2


def test_compress_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        RIEM().compress("not-a-list", {})
    with pytest.raises(ValueError):
        REIM().compost("not-a-dict")
