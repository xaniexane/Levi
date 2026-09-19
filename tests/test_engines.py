"""Tests for the engines substrate and the three builtin engines."""

import pytest

from levi.engines import registry
from levi.engines.base import Engine, EngineInputError, EngineRegistry


def test_builtin_engines_registered():
    ids = {e.id for e in registry.list()}
    assert {"triage", "cadence", "weigh"} <= ids


def test_unknown_engine_names_available():
    with pytest.raises(KeyError) as exc:
        registry.run("nope", {})
    assert "triage" in str(exc.value)


def test_duplicate_registration_refused():
    reg = EngineRegistry()
    reg.register(Engine(id="x", name="X", description="x", handler=lambda i: None))
    with pytest.raises(ValueError):
        reg.register(Engine(id="x", name="X", description="x"))


def test_missing_required_inputs_refused():
    with pytest.raises(EngineInputError):
        registry.run("triage", {})
    with pytest.raises(EngineInputError):
        registry.run("triage", {"options": [{"id": "a", "scores": {}}]})


def test_triage_picks_weighted_winner():
    result = registry.run(
        "triage",
        {
            "options": [
                {"id": "a", "scores": {"cost": 10, "speed": 1}},
                {"id": "b", "scores": {"cost": 5, "speed": 10}},
            ],
            "weights": {"cost": 3, "speed": 1},
        },
    )
    assert result.verdict["winner"] == "a"
    assert result.verdict["ranking"][0]["id"] == "a"
    assert result.verdict["margin"] > 0
    assert 0.5 <= result.confidence <= 1.0
    assert result.trace


def test_triage_tie_breaks_deterministically():
    inputs = {
        "options": [
            {"id": "b", "scores": {"x": 1}},
            {"id": "a", "scores": {"x": 1}},
        ]
    }
    r1 = registry.run("triage", inputs)
    r2 = registry.run("triage", inputs)
    assert r1.verdict["winner"] == "a"
    assert r1.verdict["tied"] is True
    assert r1.verdict == r2.verdict


def test_triage_constant_criterion_named():
    result = registry.run(
        "triage",
        {
            "options": [
                {"id": "a", "scores": {"same": 7, "diff": 3}},
                {"id": "b", "scores": {"same": 7, "diff": 9}},
            ]
        },
    )
    assert result.verdict["winner"] == "b"
    assert any("constant" in t and "'same'" in t for t in result.trace)


def test_triage_negative_weight_refused():
    with pytest.raises(EngineInputError):
        registry.run(
            "triage",
            {
                "options": [
                    {"id": "a", "scores": {"x": 1}},
                    {"id": "b", "scores": {"x": 2}},
                ],
                "weights": {"x": -1},
            },
        )


def test_cadence_rhythm_read():
    result = registry.run(
        "cadence",
        {
            "events": [
                "2026-09-15T08:00:00Z",
                "2026-09-16T08:05:00Z",
                "2026-09-17T07:55:00Z",
            ],
            "period_hours": 24.0,
            "now": "2026-09-17T08:00:00Z",
        },
    )
    v = result.verdict
    assert v["event_count"] == 3
    assert v["on_time_streak"] == 3
    assert v["missed_beats"] == 0
    assert v["overdue"] is False
    assert v["next_due"].startswith("2026-09-18T07:55")
    assert 0.9 <= result.confidence <= 1.0


def test_cadence_detects_drift():
    result = registry.run(
        "cadence",
        {
            "events": [
                "2026-09-10T08:00:00Z",
                "2026-09-11T08:00:00Z",
                "2026-09-14T08:00:00Z",  # 72h gap: two beats missed
            ],
            "period_hours": 24.0,
            "now": "2026-09-16T08:00:00Z",
        },
    )
    v = result.verdict
    assert v["missed_beats"] == 2
    assert v["overdue"] is True
    assert v["drift_hours"] > 0


def test_cadence_single_event_honest_zero():
    result = registry.run(
        "cadence",
        {"events": ["2026-09-17T08:00:00Z"], "now": "2026-09-17T09:00:00Z"},
    )
    assert result.verdict["detected_period_hours"] is None
    assert result.confidence == 0.0


def test_cadence_bad_timestamp_refused():
    with pytest.raises(EngineInputError):
        registry.run("cadence", {"events": ["not-a-time"]})


def test_weigh_lean_for():
    result = registry.run(
        "weigh",
        {
            "proposition": "Ship the triage engine",
            "for_evidence": [
                {"point": "deterministic and tested", "weight": 3.0},
                {"point": "small surface", "weight": 1.0},
            ],
            "against_evidence": [{"point": "another thing to maintain", "weight": 1.0}],
        },
    )
    v = result.verdict
    assert v["lean"] == "for"
    assert v["margin"] > 0
    assert "deterministic and tested" in v["decisive_for"]
    assert result.confidence > 0.5


def test_weigh_balanced_on_coin_flip():
    result = registry.run(
        "weigh",
        {
            "proposition": "Flip?",
            "for_evidence": [{"point": "heads", "weight": 1.0}],
            "against_evidence": [{"point": "tails", "weight": 1.0}],
        },
    )
    assert result.verdict["lean"] == "balanced"
    assert result.confidence == 0.5


def test_weigh_no_evidence_balanced():
    result = registry.run("weigh", {"proposition": "Empty?"})
    assert result.verdict["lean"] == "balanced"
    assert result.verdict["margin"] == 0.0


def test_weigh_empty_proposition_refused():
    with pytest.raises(EngineInputError):
        registry.run("weigh", {"proposition": ""})


def test_engine_result_round_trip():
    result = registry.run(
        "weigh",
        {
            "proposition": "X",
            "for_evidence": [{"point": "p", "weight": 5.0}],
            "against_evidence": [{"point": "q", "weight": 1.0}],
        },
    )
    d = result.to_dict()
    assert d["engine_id"] == "weigh"
    assert d["verdict"]["lean"] == "for"
    assert isinstance(d["trace"], list)
