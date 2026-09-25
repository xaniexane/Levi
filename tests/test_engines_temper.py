"""Tests for the temper engine — honest confidence over evidence."""

import math

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def run(**kwargs):
    return registry.run("temper", kwargs)


def test_registered():
    assert registry.get("temper").id == "temper"


def test_settled_claim():
    r = run(
        claim="water boils at 100C at sea level",
        corroborations=8,
        contradictions=0,
        source_count=10,
        days_old=2,
    )
    assert r.verdict["standing"] == "settled"
    assert r.verdict["net_support"] == 8
    assert r.confidence > 0.8


def test_contradictions_weigh_double():
    r = run(
        claim="x",
        corroborations=4,
        contradictions=2,
        source_count=6,
        days_old=0,
    )
    # net = 4 - 2*2 = 0 -> provisional
    assert r.verdict["net_support"] == 0
    assert r.verdict["standing"] == "provisional"


def test_unfounded():
    r = run(claim="x", corroborations=1, contradictions=3, source_count=4, days_old=0)
    assert r.verdict["standing"] == "unfounded"


def test_leaning_band():
    r = run(claim="x", corroborations=3, contradictions=0, source_count=3, days_old=0)
    assert r.verdict["standing"] == "leaning"


def test_stale_evidence_decays():
    fresh = run(
        claim="x", corroborations=8, contradictions=0, source_count=8, days_old=0
    )
    stale = run(
        claim="x", corroborations=8, contradictions=0, source_count=8, days_old=180
    )
    assert stale.confidence < fresh.confidence
    # half-life math: strength same, decay 0.5 at 180d
    strength = 1.0 / (1.0 + math.exp(-8 / 2.0))
    expected = round(0.5 * 0.3 + 0.7 * strength * 0.5, 3)
    assert stale.confidence == expected


def test_deny_closed():
    with pytest.raises(EngineInputError):
        run(claim="")  # empty claim refused
    with pytest.raises(EngineInputError):
        run(claim="x", corroborations=-1)  # negative refused
    with pytest.raises(EngineInputError):
        run(claim="x", corroborations=5, contradictions=5, source_count=9)  # inflated
    with pytest.raises(EngineInputError):
        run(claim="x", base_confidence=1.5)  # out of range


def test_deterministic():
    a = run(claim="x", corroborations=6, contradictions=1, source_count=7)
    b = run(claim="x", corroborations=6, contradictions=1, source_count=7)
    assert a.verdict == b.verdict and a.confidence == b.confidence
