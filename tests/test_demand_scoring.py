"""Hermetic tests for the DemandPulse five-factor scoring engine.

No HOME writes (DemandPulse is constructed with a tmp_path), no network,
no randomness: every assertion is deterministic.
"""

import pytest
import json as _json

from levi.demand import scoring
from levi.demand.pulse import DemandPulse
from levi.demand.scoring import (
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    FACTORS,
    FactorScore,
    ScoreCard,
    composite_score,
    parse_weights,
    rank_cards,
    score_card,
    tier_for,
    validate_factors,
    validate_weights,
)


def _factors(**over):
    base = {
        "demand": (80, "surveyed 40 users, 32 expressed need"),
        "market_size": (70, "TAM estimate from industry report"),
        "competition_gap": (60, "3 incumbents, none serve segment X"),
        "trend_velocity": (50, "search interest doubling YoY"),
        "entry_feasibility": (40, "needs 2 engineers, 3 months"),
    }
    base.update(over)
    return base


def test_factor_order_and_default_weights():
    assert FACTORS == (
        "demand",
        "market_size",
        "competition_gap",
        "trend_velocity",
        "entry_feasibility",
    )
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-12
    assert DEFAULT_WEIGHTS == {
        "demand": 0.30,
        "market_size": 0.25,
        "competition_gap": 0.20,
        "trend_velocity": 0.15,
        "entry_feasibility": 0.10,
    }


def test_weighted_math_is_exact():
    # 80*.3 + 70*.25 + 60*.2 + 50*.15 + 40*.1 = 65.0
    card = score_card("o1", "T", _factors())
    assert card.composite == 65.0
    assert card.tier == "watch"
    assert card.alert is False  # 65 < 75


def test_determinism():
    a = score_card("o1", "T", _factors())
    b = score_card("o1", "T", _factors())
    assert a.composite == b.composite
    assert a.tier == b.tier


def test_tier_boundaries():
    assert tier_for(75.0) == "high"
    assert tier_for(100.0) == "high"
    assert tier_for(74.99) == "watch"
    assert tier_for(50.0) == "watch"
    assert tier_for(49.99) == "low"
    assert tier_for(0.0) == "low"


def test_threshold_alert_and_custom_threshold():
    hi = _factors(
        demand=(100, "b"),
        market_size=(100, "b"),
        competition_gap=(100, "b"),
        trend_velocity=(100, "b"),
        entry_feasibility=(100, "b"),
    )
    assert score_card("o1", "T", hi).alert is True
    assert score_card("o1", "T", hi, threshold=100.0).alert is True
    mid = score_card("o1", "T", _factors())  # composite 65.0
    assert mid.alert is False
    assert score_card("o1", "T", _factors(), threshold=65.0).alert is True
    assert score_card("o1", "T", _factors(), threshold=65.01).alert is False
    with pytest.raises(ValueError, match="threshold"):
        score_card("o1", "T", _factors(), threshold=100.01)


def test_basis_required():
    with pytest.raises(ValueError, match="basis is required"):
        FactorScore(name="demand", value=80, basis="   ")


def test_value_range_rejected():
    with pytest.raises(ValueError, match="out of range"):
        FactorScore(name="demand", value=101, basis="b")
    with pytest.raises(ValueError, match="out of range"):
        FactorScore(name="demand", value=-1, basis="b")


def test_unknown_factor_rejected():
    with pytest.raises(ValueError, match="unknown factor"):
        FactorScore(name="vibes", value=50, basis="b")


def test_missing_and_extra_factors_rejected():
    f = _factors()
    del f["demand"]
    with pytest.raises(ValueError, match="missing"):
        validate_factors(f)
    f2 = _factors(extra=(50, "b"))
    with pytest.raises(ValueError, match="extra"):
        validate_factors(f2)


def test_weight_validation():
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weights({**DEFAULT_WEIGHTS, "demand": 0.5})
    bad = dict(DEFAULT_WEIGHTS)
    del bad["demand"]
    with pytest.raises(ValueError, match="exactly"):
        validate_weights(bad)
    neg = dict(DEFAULT_WEIGHTS)
    neg["demand"] = -0.1
    neg["market_size"] = 0.65
    with pytest.raises(ValueError, match="outside"):
        validate_weights(neg)
    # custom valid weights change the composite deterministically
    w = {
        "demand": 1.0,
        "market_size": 0.0,
        "competition_gap": 0.0,
        "trend_velocity": 0.0,
        "entry_feasibility": 0.0,
    }
    card = score_card("o1", "T", _factors(), weights=w)
    assert card.composite == 80.0


def test_parse_weights_cli_spec():
    w = parse_weights("0.3,0.25,0.2,0.15,0.1")
    assert w == validate_weights(DEFAULT_WEIGHTS)
    with pytest.raises(ValueError):
        parse_weights("0.5,0.5")
    with pytest.raises(ValueError):
        parse_weights("a,b,c,d,e")


def test_factor_input_forms():
    card = score_card(
        "o1",
        "T",
        {
            "demand": FactorScore("demand", 80, "b"),
            "market_size": {"value": 70, "basis": "b"},
            "competition_gap": (60, "b"),
            "trend_velocity": [50, "b"],
            "entry_feasibility": (40, "b"),
        },
    )
    assert card.composite == 65.0


def test_ranking_order_and_tiebreak():
    lo = score_card("b-id", "Lo", _factors(demand=(10, "b")))
    hi = score_card("a-id", "Hi", _factors(demand=(100, "b")))
    mid = score_card("c-id", "Mid", _factors())
    ranked = rank_cards([lo, hi, mid])
    assert [c.opportunity_id for c in ranked] == ["a-id", "c-id", "b-id"]
    # ties break by opportunity_id ascending, deterministically
    t1 = score_card("zz", "T1", _factors())
    t2 = score_card("aa", "T2", _factors())
    assert [c.opportunity_id for c in rank_cards([t1, t2])] == ["aa", "zz"]


def test_explain_is_auditable():
    card = score_card("o1", "Honest Opp", _factors())
    text = card.explain()
    assert "composite=65.00" in text
    assert "tier=watch" in text
    for f in FACTORS:
        assert f in text
    assert "surveyed 40 users" in text
    assert "not measured data" in text


def test_roundtrip_dict():
    card = score_card("o1", "T", _factors(), notes="n")
    back = ScoreCard.from_dict(card.to_dict())
    assert back.composite == card.composite
    assert back.tier == card.tier
    assert back.alert == card.alert
    assert back.notes == "n"
    assert [f.basis for f in back.factors] == [f.basis for f in card.factors]


def test_pulse_integration_persists(tmp_path):
    path = tmp_path / "dp.json"
    dp = DemandPulse(path=path)
    sig = dp.scan_seed("people need offline-first billing", segment="trades")
    card = dp.score_five_factor(sig.id, "Offline billing", _factors())
    assert card.composite == 65.0
    # reload from disk
    dp2 = DemandPulse(path=path)
    assert len(dp2.score_cards) == 1
    assert dp2.score_cards[0].composite == 65.0
    assert dp2.top_score_cards()[0].title == "Offline billing"
    status = dp2.format_status()
    assert "five-factor" in status
    assert "Offline billing" in status


def test_pulse_rejects_basisless_card(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    bad = _factors(demand=(80, ""))
    with pytest.raises(ValueError, match="basis is required"):
        dp.score_five_factor("sig", "Bad", bad)
    assert dp.score_cards == []


def test_default_threshold_constant():
    assert DEFAULT_THRESHOLD == 75.0
    assert scoring.DEFAULT_THRESHOLD == 75.0


# -- boundary validation (hardening) -----------------------------------------


def test_coerce_factor_rejects_malformed_input():
    from levi.demand.scoring import _coerce_factor

    with pytest.raises(ValueError, match="needs 'value' and 'basis'"):
        _coerce_factor("demand", {"value": 80})  # missing basis
    with pytest.raises(ValueError, match="needs 'value' and 'basis'"):
        _coerce_factor("demand", {"basis": "x"})  # missing value
    with pytest.raises(ValueError, match="must be a FactorScore"):
        _coerce_factor("demand", 80)
    with pytest.raises(ValueError, match="must be a FactorScore"):
        _coerce_factor("demand", "80,basis")
    with pytest.raises(ValueError, match="exactly \\(value, basis\\)"):
        _coerce_factor("demand", (80, "basis", "extra"))


def test_tier_for_rejects_non_finite():
    for bad in ("high", None, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="finite number"):
            tier_for(bad)


def test_composite_score_rejects_garbage():
    card = score_card("id1", "t", _factors())
    with pytest.raises(ValueError):
        composite_score(["not", "factors"], card.weights)
    with pytest.raises(ValueError):
        composite_score(card.factors, [("demand", 0.3)])


def test_score_card_rejects_blank_ids():
    with pytest.raises(ValueError):
        score_card("", "title", _factors())
    with pytest.raises(ValueError):
        score_card("id1", "  ", _factors())


def test_rank_cards_rejects_garbage():
    with pytest.raises(ValueError):
        rank_cards("not a list")
    with pytest.raises(ValueError):
        rank_cards([{"composite": 1}])


# -- DemandPulse boundaries ---------------------------------------------------


def test_pulse_scan_seed_rejects_empty(tmp_path):
    pulse = DemandPulse(path=tmp_path / "dp.json")
    for bad in ("", "   ", None, 123):
        with pytest.raises(ValueError):
            pulse.scan_seed(bad)


def test_pulse_score_opportunity_rejects_garbage(tmp_path):
    pulse = DemandPulse(path=tmp_path / "dp.json")
    with pytest.raises(ValueError):
        pulse.score_opportunity("", "title")
    with pytest.raises(ValueError):
        pulse.score_opportunity("d1", "")
    with pytest.raises(ValueError, match="must be a number"):
        pulse.score_opportunity("d1", "t", demand_score="high")
    with pytest.raises(ValueError, match="must be a number"):
        pulse.score_opportunity("d1", "t", serviceability=float("nan"))
    # out-of-range numerics are REJECTED, never silently clamped
    with pytest.raises(ValueError, match="must be in \\[0, 1\\]"):
        pulse.score_opportunity("d1", "t", demand_score=5.0)
    with pytest.raises(ValueError, match="must be in \\[0, 1\\]"):
        pulse.score_opportunity("d1", "t", startup_cost=-2.0)
    opp = pulse.score_opportunity("d1", "t")
    assert opp.demand_score == 0.5 and opp.startup_cost == 0.3


def test_pulse_top_n_rejects_garbage(tmp_path):
    pulse = DemandPulse(path=tmp_path / "dp.json")
    for bad in (0, -1, "5", 2.5, True):
        with pytest.raises(ValueError):
            pulse.top_opportunities(bad)
        with pytest.raises(ValueError):
            pulse.top_score_cards(bad)


def test_pulse_corrupt_file_warns_and_starts_empty(tmp_path):
    path = tmp_path / "dp.json"
    path.write_text("{corrupt", encoding="utf-8")
    with pytest.warns(UserWarning, match="unreadable"):
        pulse = DemandPulse(path=path)
    assert pulse.signals == [] and pulse.opportunities == []


def test_pulse_skips_corrupt_entries_not_whole_file(tmp_path):
    path = tmp_path / "dp.json"
    good_signal = {
        "id": "s1",
        "need": "need x",
        "segment": "general",
        "evidence": "",
        "confidence": 0.4,
        "kind": "HYPOTHESIS",
        "created_at": "2026-01-01T00:00:00",
    }
    bad_signal = {"id": "", "need": "", "confidence": "high"}
    path.write_text(
        _json.dumps({"signals": [good_signal, bad_signal], "opportunities": []})
    )
    pulse = DemandPulse(path=path)
    assert [s.id for s in pulse.signals] == ["s1"]


def test_pulse_score_five_factor_rejects_blank_ids(tmp_path):
    pulse = DemandPulse(path=tmp_path / "dp.json")
    with pytest.raises(ValueError):
        pulse.score_five_factor("", "t", _factors())
    with pytest.raises(ValueError):
        pulse.score_five_factor("d1", "", _factors())


# -- hardened input contracts ------------------------------------------------


def test_validate_factors_requires_mapping():
    for bad in (None, 42, "demand", [("demand", (80, "x"))], {"demand"}):
        with pytest.raises(ValueError, match="must be a mapping"):
            validate_factors(bad)


def test_validate_weights_requires_mapping():
    for bad in (42, "0.3", [("demand", 0.3)], {("demand", 0.3)}):
        with pytest.raises(ValueError, match="must be a mapping"):
            validate_weights(bad)
    assert validate_weights(None) == dict(DEFAULT_WEIGHTS)


def test_composite_score_rejects_wrong_factor_set():
    good = [
        FactorScore(name, v, "basis note long enough")
        for name, v in (
            ("demand", 80),
            ("market_size", 70),
            ("competition_gap", 60),
            ("trend_velocity", 50),
            ("entry_feasibility", 40),
        )
    ]
    w = validate_weights(None)
    with pytest.raises(ValueError, match="exactly"):
        composite_score(good[:4], w)  # missing one factor
    with pytest.raises(ValueError, match="exactly"):
        composite_score(good + [good[0]], w)  # duplicate
    with pytest.raises(ValueError, match="weights must cover exactly"):
        composite_score(good, {"demand": 1.0})  # missing weights -> no KeyError
    assert composite_score(good, w) == pytest.approx(65.0, abs=0.01)


def test_parse_weights_type_and_conversion_diagnostics():
    with pytest.raises(ValueError, match="must be a string"):
        parse_weights(None)
    with pytest.raises(ValueError, match="must be a string"):
        parse_weights(0.3)
    with pytest.raises(ValueError, match="needs 5 comma-separated"):
        parse_weights("0.3,0.25")
    with pytest.raises(ValueError, match="non-numeric"):
        parse_weights("0.3,0.25,0.2,0.15,abc")
