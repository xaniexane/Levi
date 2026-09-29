"""Proof for the keel engine: the nine declared laws, machine-checked."""

import pytest

from levi.engines.base import EngineInputError, registry
from levi.engines.keel import KEEL_ENGINE


def _reading(rid, verdict, score):
    return {"id": rid, "verdict": verdict, "score": score}


def _run(readings, **kw):
    kw.setdefault("line", "steady")
    kw.setdefault("line_score", 0.60)
    kw.setdefault("band", 0.10)
    kw.setdefault("persistence", 3)
    return KEEL_ENGINE.run({"readings": readings, **kw})


def test_engine_is_registered():
    assert registry.get("keel") is KEEL_ENGINE


def test_hold_when_nothing_challenges():
    result = _run([_reading("r1", "steady", 0.65), _reading("r2", "steady", 0.70)])
    assert result.verdict["decision"] == "hold"
    assert result.verdict["line_out"] == "steady"
    assert result.verdict["tacks"] == 0


def test_tack_on_persistent_band_clear():
    readings = [
        _reading("r1", "surge", 0.75),
        _reading("r2", "surge", 0.80),
        _reading("r3", "surge", 0.72),
    ]
    result = _run(readings)  # threshold 0.70, three in a row clears it
    assert result.verdict["decision"] == "tack"
    assert result.verdict["line_out"] == "surge"
    assert result.verdict["tacks"] == 1
    dispositions = {d["id"]: d for d in result.verdict["readings"]}
    assert dispositions["r3"]["tacked_to"] == "surge"


def test_gust_is_never_a_shift():
    # loud readings, but not enough consecutive to tack
    readings = [
        _reading("r1", "surge", 0.95),
        _reading("r2", "surge", 0.95),
        _reading("r3", "steady", 0.61),
    ]
    result = _run(readings)
    assert result.verdict["decision"] == "hold"
    assert result.verdict["line_out"] == "steady"


def test_streak_resets_on_shortfall():
    # a sub-band reading breaks the streak; count resumes after
    readings = [
        _reading("r1", "surge", 0.80),
        _reading("r2", "surge", 0.80),
        _reading("r3", "surge", 0.69),  # below 0.70 threshold: streak resets
        _reading("r4", "surge", 0.80),
        _reading("r5", "surge", 0.80),
        _reading("r6", "surge", 0.80),
    ]
    result = _run(readings)
    assert result.verdict["tacks"] == 1
    assert result.verdict["shudders"] == 1
    by_id = {d["id"]: d for d in result.verdict["readings"]}
    assert by_id["r3"]["disposition"] == "shudder"
    assert by_id["r3"]["streak_after"] == 0
    assert by_id["r6"]["streak_after"] == 0  # reset by the tack itself


def test_every_reading_carries_evidence():
    result = _run([_reading("r1", "surge", 0.69), _reading("r2", "steady", 0.61)])
    for entry in result.verdict["readings"]:
        assert "margin" in entry
        assert "streak_after" in entry
        assert "measured_against_line" in entry
        assert entry["measured_against_line"] == "steady"


def test_determinism():
    readings = [_reading("r1", "surge", 0.80), _reading("r2", "steady", 0.61)]
    first = _run(readings)
    second = _run(readings)
    first_verdict = dict(first.verdict)
    second_verdict = dict(second.verdict)
    assert first_verdict == second_verdict
    assert first.trace == second.trace


def test_deny_closed_bad_line():
    with pytest.raises(EngineInputError):
        _run([], line="")
    with pytest.raises(EngineInputError):
        _run([], line_score=1.5)
    with pytest.raises(EngineInputError):
        _run([], line_score=True)


def test_deny_closed_bad_readings():
    with pytest.raises(EngineInputError):
        _run([{"id": "r1", "verdict": "surge"}])  # missing score
    with pytest.raises(EngineInputError):
        _run(
            [
                {"id": "r1", "verdict": "surge", "score": 0.9},
                {"id": "r1", "verdict": "rest", "score": 0.9},
            ]
        )  # duplicate id
    with pytest.raises(EngineInputError):
        _run([{"id": "r1", "verdict": "surge", "score": 2.0}])  # score out of range
    with pytest.raises(EngineInputError):
        _run("not-a-list")


def test_deny_closed_bad_band_and_persistence():
    with pytest.raises(EngineInputError):
        _run([], band=-0.1)
    with pytest.raises(EngineInputError):
        _run([], persistence=0)
    with pytest.raises(EngineInputError):
        _run([], persistence=True)


def test_bound_law_refuses_half_runs():
    many = [_reading(f"r{i}", "steady", 0.6) for i in range(5)]
    with pytest.raises(EngineInputError):
        _run(many, max_readings=4)
    result = _run(many, max_readings=5)
    assert result.verdict["total"] == 5


def test_confidence_tracks_the_line():
    result = _run(
        [
            _reading("r1", "surge", 0.75),
            _reading("r2", "surge", 0.80),
            _reading("r3", "surge", 0.72),
        ]
    )
    assert result.confidence == pytest.approx(0.72)  # score that set the new line
