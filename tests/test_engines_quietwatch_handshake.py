"""Tests for the quietwatch and handshake engines.

quietwatch: SELCAL-pattern selective calling — silence is the default,
a registered call sign wakes it. handshake: Bell-103-pattern capability
negotiation — tone, offer, acknowledgment, or a polite close.
"""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def test_both_engines_registered():
    ids = {e.id for e in registry.list()}
    assert {"quietwatch", "handshake"} <= ids


# ── quietwatch ────────────────────────────────────────────────────


def test_quietwatch_silent_by_default():
    result = registry.run(
        "quietwatch",
        {
            "calls": [{"id": "alpha", "pattern": "alpha base"}],
            "transcript": ["static", "unrelated traffic", "more static"],
        },
    )
    assert result.verdict["awake"] is False
    assert result.verdict["hits"] == []
    assert result.verdict["lines_scanned"] == 3
    assert result.confidence == 1.0


def test_quietwatch_hears_its_call_sign():
    result = registry.run(
        "quietwatch",
        {
            "calls": [{"id": "alpha", "pattern": "alpha base"}],
            "transcript": ["static", "alpha base, come in", "over"],
        },
    )
    assert result.verdict["awake"] is True
    assert result.verdict["hits"] == [
        {"call": "alpha", "line": 1, "text": "alpha base, come in"}
    ]


def test_quietwatch_match_is_case_insensitive_and_first_line_kept():
    result = registry.run(
        "quietwatch",
        {
            "calls": [{"id": "alpha", "pattern": "ALPHA BASE"}],
            "transcript": ["Alpha Base calling", "alpha base again"],
        },
    )
    assert result.verdict["hits"] == [
        {"call": "alpha", "line": 0, "text": "Alpha Base calling"}
    ]


def test_quietwatch_accepts_a_string_transcript():
    result = registry.run(
        "quietwatch",
        {
            "calls": [{"id": "beta", "pattern": "beta"}],
            "transcript": "line one\nbeta here\nline three",
        },
    )
    assert result.verdict["awake"] is True
    assert result.verdict["hits"][0]["line"] == 1


def test_quietwatch_deterministic():
    inputs = {
        "calls": [{"id": "alpha", "pattern": "alpha"}],
        "transcript": ["x", "alpha", "y"],
    }
    first = registry.run("quietwatch", inputs).verdict
    second = registry.run("quietwatch", inputs).verdict
    assert first == second


def test_quietwatch_deny_closed():
    with pytest.raises(EngineInputError):
        registry.run("quietwatch", {"calls": [], "transcript": []})
    with pytest.raises(EngineInputError):
        registry.run("quietwatch", {"calls": [{"id": "a", "pattern": "p"}]})
    with pytest.raises(EngineInputError):
        registry.run(
            "quietwatch",
            {
                "calls": [{"id": "a", "pattern": "p"}, {"id": "a", "pattern": "q"}],
                "transcript": [],
            },
        )
    with pytest.raises(EngineInputError):
        registry.run(
            "quietwatch",
            {"calls": [{"id": "a", "pattern": "p"}], "transcript": [42]},
        )


# ── handshake ─────────────────────────────────────────────────────


def test_handshake_agrees_on_initiator_preference():
    result = registry.run(
        "handshake",
        {
            "initiator": {"id": "levi", "capabilities": ["text/v1", "text/v0"]},
            "responder": {"id": "relay", "capabilities": ["text/v0", "beep/v0"]},
        },
    )
    verdict = result.verdict
    assert verdict["agreed"] == "text/v0"
    assert verdict["shared"] == ["text/v0"]
    assert "tone" in result.trace[0] and "ack" in result.trace[-1]


def test_handshake_no_common_language_closes_politely():
    result = registry.run(
        "handshake",
        {
            "initiator": {"id": "levi", "capabilities": ["text/v1"]},
            "responder": {"id": "relay", "capabilities": ["beep/v0"]},
        },
    )
    verdict = result.verdict
    assert verdict["agreed"] is None
    assert verdict["shared"] == []
    assert "no common language" in result.trace[-1]


def test_handshake_deterministic():
    inputs = {
        "initiator": {"id": "a", "capabilities": ["x", "y"]},
        "responder": {"id": "b", "capabilities": ["y", "z"]},
    }
    first = registry.run("handshake", inputs).verdict
    second = registry.run("handshake", inputs).verdict
    assert first == second


def test_handshake_deny_closed():
    with pytest.raises(EngineInputError):
        registry.run("handshake", {"initiator": {"id": "a", "capabilities": ["x"]}})
    with pytest.raises(EngineInputError):
        registry.run(
            "handshake",
            {
                "initiator": {"id": "a", "capabilities": []},
                "responder": {"id": "b", "capabilities": ["x"]},
            },
        )
    with pytest.raises(EngineInputError):
        registry.run(
            "handshake",
            {
                "initiator": {"id": "a", "capabilities": ["x", "x"]},
                "responder": {"id": "b", "capabilities": ["x"]},
            },
        )
