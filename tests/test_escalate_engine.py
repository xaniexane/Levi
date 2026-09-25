"""Tests for the escalate engine — the confidence-based escalation router."""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def _run(**kwargs):
    base = {"confidence": 0.7, "stakes": "moderate", "reversible": True}
    base.update(kwargs)
    return registry.run("escalate", base)


def test_engine_registered():
    assert "escalate" in {e.id for e in registry.list()}


def test_critical_always_asks_operator():
    r = _run(stakes="critical", confidence=0.99, reversible=True)
    assert r.verdict["decision"] == "ask_operator"
    assert any("rule 1" in step for step in r.trace)


def test_irreversible_high_stakes_asks_operator():
    r = _run(stakes="high", reversible=False, confidence=0.9)
    assert r.verdict["decision"] == "ask_operator"
    assert any("rule 2" in step for step in r.trace)


def test_low_confidence_contained_goes_to_brain():
    r = _run(confidence=0.2, stakes="low", reversible=True)
    assert r.verdict["decision"] == "consult_brain"


def test_low_confidence_exposed_goes_to_operator():
    r = _run(confidence=0.2, stakes="high", reversible=True)
    assert r.verdict["decision"] == "ask_operator"
    r = _run(confidence=0.2, retry_cost="high")
    assert r.verdict["decision"] == "ask_operator"


def test_safe_and_confident_handles_local():
    r = _run(confidence=0.95, stakes="low", reversible=True)
    assert r.verdict["decision"] == "handle_local"
    r = _run(confidence=0.8, stakes="moderate", reversible=True)
    assert r.verdict["decision"] == "handle_local"


def test_middle_ground_consults_brain():
    r = _run(confidence=0.7, stakes="moderate", reversible=False)
    assert r.verdict["decision"] == "consult_brain"


def test_unreachable_operator_defers_to_queue():
    r = _run(stakes="critical", operator_available=False, confidence=0.99)
    assert r.verdict["decision"] == "defer_queue"
    assert any("rule 6" in step for step in r.trace)


def test_deny_closed_inputs():
    with pytest.raises(EngineInputError):
        registry.run("escalate", {})
    with pytest.raises(EngineInputError):
        _run(confidence=1.5)
    with pytest.raises(EngineInputError):
        _run(confidence="high")
    with pytest.raises(EngineInputError):
        _run(stakes="extreme")
    with pytest.raises(EngineInputError):
        _run(reversible="yes")
    with pytest.raises(EngineInputError):
        _run(retry_cost="medium")
    with pytest.raises(EngineInputError):
        _run(operator_available=1)


def test_deterministic():
    inputs = {"confidence": 0.65, "stakes": "high", "reversible": True}
    r1 = registry.run("escalate", inputs)
    r2 = registry.run("escalate", inputs)
    assert r1.verdict == r2.verdict
    assert r1.trace == r2.trace


def test_confidence_calibrated_and_traced():
    r = _run(confidence=0.95, stakes="low", reversible=True)
    assert 0.0 <= r.confidence <= 1.0
    assert r.trace  # full audit trail, never empty
    r = _run(stakes="critical", confidence=0.9, reversible=True)
    assert r.confidence >= 0.95  # absolute rules admit no margin doubt
