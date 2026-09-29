"""Tests for the braid engine: arbitration over engine verdicts.

Each law in braid.py's docstring is proved here, not just exercised.
"""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def _v(engine, verdict, confidence=0.8):
    return {"engine": engine, "verdict": verdict, "confidence": confidence}


def _run(**inputs):
    return registry.run("braid", inputs)


def test_braid_registers():
    ids = {e.id for e in registry.list()}
    assert "braid" in ids


def test_unanimity_law():
    result = _run(
        question="pack tonight?",
        verdicts=[_v("triage", "yes"), _v("weigh", "yes"), _v("gavel", "yes")],
    )
    assert result.verdict["outcome"] == "consensus"
    assert result.verdict["verdict"] == "yes"
    assert result.verdict["agreeing"] == ["gavel", "triage", "weigh"]
    assert result.verdict["dissenting"] == []


def test_conflict_honesty_and_dissent_surface_laws():
    result = _run(
        question="pack tonight?",
        verdicts=[
            _v("triage", "yes", 0.9),
            _v("weigh", "yes", 0.7),
            _v("gavel", "no", 0.6),
        ],
    )
    assert result.verdict["outcome"] == "majority"
    assert result.verdict["verdict"] == "yes"
    assert result.verdict["agreeing"] == ["triage", "weigh"]
    assert result.verdict["dissenting"] == ["gavel"]  # named, never averaged
    assert "gavel" in " ".join(result.trace)
    # confidence = mean of the majority side only, disclosed in verdict
    assert result.verdict["confidence"] == round((0.9 + 0.7) / 2, 3)


def test_hold_on_deadlock_law():
    result = _run(
        question="which launch?",
        verdicts=[_v("triage", "a"), _v("weigh", "b"), _v("gavel", "c")],
    )
    assert result.verdict["outcome"] == "deadlocked"
    assert result.verdict["verdict"] is None
    assert result.verdict["agreeing"] == []
    assert result.verdict["dissenting"] == ["gavel", "triage", "weigh"]
    assert result.confidence == 0.0


def test_even_split_deadlocks_not_majority():
    result = _run(
        question="ship?",
        verdicts=[_v("a", "yes"), _v("b", "yes"), _v("c", "no"), _v("d", "no")],
    )
    assert result.verdict["outcome"] == "deadlocked"


def test_determinism_law():
    kwargs = dict(
        question="pack tonight?",
        verdicts=[_v("triage", "yes"), _v("weigh", "no"), _v("gavel", "yes")],
    )
    first = _run(**kwargs)
    second = _run(**kwargs)
    # ran_at is the audit timestamp (wall clock), not part of the verdict.
    assert first.verdict == second.verdict
    assert first.confidence == second.confidence
    assert first.trace == second.trace


def test_verdicts_can_be_structured_not_just_strings():
    result = _run(
        question="roll call",
        verdicts=[
            _v("muster", {"roll": "ready", "score": 1.0}),
            _v("season", {"roll": "ready", "score": 1.0}),
        ],
    )
    assert result.verdict["outcome"] == "consensus"
    assert result.verdict["verdict"] == {"roll": "ready", "score": 1.0}


def test_deny_closed_empty_verdicts():
    with pytest.raises(EngineInputError):
        _run(question="q", verdicts=[])


def test_deny_closed_duplicate_engine():
    with pytest.raises(EngineInputError):
        _run(question="q", verdicts=[_v("triage", "yes"), _v("triage", "no")])


def test_deny_closed_bad_confidence():
    with pytest.raises(EngineInputError):
        _run(question="q", verdicts=[_v("triage", "yes", 1.5)])


def test_deny_closed_unserializable_verdict():
    with pytest.raises(EngineInputError):
        _run(question="q", verdicts=[_v("triage", object())])


def test_deny_closed_missing_question():
    with pytest.raises(EngineInputError):
        _run(verdicts=[_v("triage", "yes")])


def test_deny_closed_max_verdicts_guard():
    with pytest.raises(EngineInputError):
        _run(
            question="q",
            verdicts=[_v(f"e{i}", "yes") for i in range(5)],
            max_verdicts=4,
        )
