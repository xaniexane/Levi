"""Tests for the muster engine: readiness roll-call over named stations."""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def _run(**inputs):
    return registry.run("muster", inputs)


def test_muster_registers():
    ids = {e.id for e in registry.list()}
    assert "muster" in ids


def test_muster_all_ready():
    result = _run(
        checks=[
            {"id": "db", "status": "ready"},
            {"id": "cache", "status": "ready"},
        ]
    )
    assert result.verdict["roll"] == "ready"
    assert result.verdict["score"] == 1.0
    assert result.verdict["blocking"] == []
    assert result.verdict["warns"] == []
    assert result.verdict["checked"] == 2
    assert result.confidence == 1.0


def test_muster_down_holds_strict_by_default():
    result = _run(
        checks=[
            {"id": "db", "status": "ready"},
            {"id": "queue", "status": "down"},
        ]
    )
    assert result.verdict["roll"] == "standdown"
    assert result.verdict["blocking"] == ["queue"]
    assert result.verdict["score"] == 0.5


def test_muster_down_degraded_when_not_strict():
    result = _run(
        strict=False,
        checks=[
            {"id": "db", "status": "ready"},
            {"id": "queue", "status": "down"},
        ],
    )
    assert result.verdict["roll"] == "degraded"
    assert result.verdict["blocking"] == ["queue"]


def test_muster_warn_without_down_is_degraded():
    result = _run(
        checks=[
            {"id": "db", "status": "ready"},
            {"id": "cache", "status": "warn"},
        ]
    )
    assert result.verdict["roll"] == "degraded"
    assert result.verdict["warns"] == ["cache"]
    assert result.verdict["score"] == 0.75  # warn counts half


def test_muster_weights_shape_the_score():
    result = _run(
        checks=[
            {"id": "db", "status": "ready", "weight": 3.0},
            {"id": "cache", "status": "down", "weight": 1.0},
        ]
    )
    assert result.verdict["roll"] == "standdown"
    assert result.verdict["score"] == 0.75  # 3/4 earned


def test_muster_blocking_keeps_input_order():
    result = _run(
        checks=[
            {"id": "zeta", "status": "down"},
            {"id": "alpha", "status": "down"},
            {"id": "mid", "status": "ready"},
        ]
    )
    assert result.verdict["blocking"] == ["zeta", "alpha"]


def test_muster_deterministic():
    inputs = {
        "checks": [
            {"id": "a", "status": "ready"},
            {"id": "b", "status": "warn", "weight": 2},
        ]
    }
    first = _run(**inputs).verdict
    second = _run(**inputs).verdict
    assert first == second


def test_muster_describe_lists_schema():
    engine = next(e for e in registry.list() if e.id == "muster")
    assert "checks" in engine.schema
    assert engine.required == ("checks",)


# ── deny-closed ──────────────────────────────────────────────────────


def test_muster_rejects_empty_checks():
    with pytest.raises(EngineInputError):
        _run(checks=[])


def test_muster_rejects_missing_checks():
    with pytest.raises(EngineInputError):
        registry.run("muster", {})


def test_muster_rejects_bad_status():
    with pytest.raises(EngineInputError):
        _run(checks=[{"id": "db", "status": "maybe"}])


def test_muster_rejects_duplicate_ids():
    with pytest.raises(EngineInputError):
        _run(
            checks=[
                {"id": "db", "status": "ready"},
                {"id": "db", "status": "ready"},
            ]
        )


def test_muster_rejects_negative_weight():
    with pytest.raises(EngineInputError):
        _run(checks=[{"id": "db", "status": "ready", "weight": -1}])


def test_muster_rejects_non_bool_strict():
    with pytest.raises(EngineInputError):
        _run(strict="yes", checks=[{"id": "db", "status": "ready"}])
