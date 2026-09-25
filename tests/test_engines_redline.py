"""Tests for the redline spend-budget guard engine."""

import pytest

from levi.engines.base import EngineInputError, registry
from levi.engines import redline  # noqa: F401  (self-registers on import)


def _run(**kw):
    return registry.get("redline").run(kw)


def test_registered_on_import():
    assert registry.get("redline").id == "redline"


def test_clear():
    result = _run(spent=20, cap=100)
    assert result.verdict["status"] == "clear"
    assert result.verdict["remaining"] == 80.0
    assert result.confidence == 1.0


def test_at_risk_inside_warn_band():
    # remaining 5 of cap 100 < 10% warn band → at-risk, not clear
    result = _run(spent=95, cap=100)
    assert result.verdict["status"] == "at-risk"
    assert result.verdict["remaining"] == 5.0


def test_would_breach_names_exact_overshoot():
    result = _run(spent=80, cap=100, pending=30)
    assert result.verdict["status"] == "would-breach"
    assert result.verdict["overshoot"] == 10.0
    assert result.verdict["remaining"] == 20.0


def test_deny_over_law_no_grace():
    # One cent over is over. No rounding, no grace.
    result = _run(spent=100.01, cap=100)
    assert result.verdict["status"] == "over"
    assert result.verdict["overshoot"] == 0.01


def test_pending_counts_law():
    # spent alone is fine; the pending spend is what crosses
    result = _run(spent=99.99, cap=100, pending=0.02)
    assert result.verdict["status"] == "would-breach"
    assert result.verdict["overshoot"] == 0.01


def test_honest_math_cents_rounded():
    result = _run(spent=33.33, cap=100)
    assert result.verdict["remaining"] == 66.67


def test_label_passthrough():
    result = _run(spent=10, cap=100, pending=5, label="server box")
    assert result.verdict["label"] == "server box"
    assert "server box" in result.trace[0]


def test_determinism_law():
    a = _run(spent=42, cap=100, pending=7)
    b = _run(spent=42, cap=100, pending=7)
    # ran_at timestamps legitimately differ; verdict + trace must not
    assert a.verdict == b.verdict
    assert a.trace == b.trace
    assert a.confidence == b.confidence


def test_no_negative_law():
    with pytest.raises(EngineInputError):
        _run(spent=-1, cap=100)
    with pytest.raises(EngineInputError):
        _run(spent=10, cap=100, pending=-5)
    with pytest.raises(EngineInputError):
        _run(spent=10, cap=0)
    with pytest.raises(EngineInputError):
        _run(spent=10, cap=-100)


def test_warn_ratio_bounds():
    with pytest.raises(EngineInputError):
        _run(spent=10, cap=100, warn_ratio=0)
    with pytest.raises(EngineInputError):
        _run(spent=10, cap=100, warn_ratio=1.5)


def test_custom_warn_ratio():
    # 20% warn band: remaining 15 of 100 → at-risk
    result = _run(spent=85, cap=100, warn_ratio=0.2)
    assert result.verdict["status"] == "at-risk"


def test_refuses_missing_inputs():
    with pytest.raises(EngineInputError):
        registry.get("redline").run({"spent": 10})


def test_refuses_bool_numbers():
    with pytest.raises(EngineInputError):
        _run(spent=True, cap=100)
