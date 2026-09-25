"""Hermetic tests for the DemandPulse signal-strength layer.

Laws under test:
  L1 no naked scores (basis + confidence + sensitivity required)
  L2 deterministic (identical inputs -> identical card/advisory)
  L3 real signals only (evidence preserved verbatim; low confidence flagged)
  L4 risks surfaced, never silently subtracted
  L5 advisory honesty (fusion math always disclosed)
  L6 stdlib only / pure functions (no I/O, no network in this file)

No HOME writes, no network, no randomness.
"""

import pytest

from levi.demand import scoring, signal_strength as ss
from levi.demand.signal_strength import (
    DIMENSIONS,
    DEFAULT_DIMENSION_WEIGHTS,
    AdvisorReport,
    DimensionScore,
    RecommendedAction,
    Risk,
    StrengthCard,
    UpgradeDirective,
    WatchCondition,
    advise,
    rank_advisories,
    strength_card,
    strength_composite,
    validate_dimension_weights,
    validate_dimensions,
)


def _dims(**over):
    base = {
        "timing_window": (80, "window open 6-12 months", 0.8, "closes if incumbent ships"),
        "monetization_path": (70, "subscription model proven nearby", 0.7, "changes if pricing tests fail"),
        "defensibility": (60, "data moat from scan corpus", 0.6, "drops if API opens up"),
        "resource_fit": (90, "stdlib-only, runs on his hardware", 0.9, "drops if GPU needed"),
        "evidence_strength": (75, "3 independent sightings", 0.75, "weakens if sightings stale"),
        "action_clarity": (85, "next step is a prototype", 0.85, "blurs if scope creeps"),
    }
    base.update(over)
    return base


def _score_card(oid="o1", title="Test Opp"):
    return scoring.score_card(
        oid, title,
        {
            "demand": (80, "surveyed need"),
            "market_size": (70, "TAM report"),
            "competition_gap": (60, "gap in segment X"),
            "trend_velocity": (50, "search doubling"),
            "entry_feasibility": (40, "2 engineers"),
        },
    )


def _strength(oid="o1", title="Test Opp", **kw):
    kw.setdefault("dimensions", _dims())
    return strength_card(oid, title, **kw)


# --- L1: no naked scores ---------------------------------------------------

def test_dimension_order_and_weights_sum():
    assert DIMENSIONS == (
        "timing_window",
        "monetization_path",
        "defensibility",
        "resource_fit",
        "evidence_strength",
        "action_clarity",
    )
    assert abs(sum(DEFAULT_DIMENSION_WEIGHTS.values()) - 1.0) < 1e-12


def test_missing_basis_rejected():
    with pytest.raises(ValueError):
        DimensionScore(name="timing_window", value=80, basis="  ",
                       confidence=0.8, sensitivity="s")


def test_missing_confidence_rejected():
    with pytest.raises(ValueError):
        _coerce = ss._coerce_dimension(
            "timing_window",
            {"value": 80, "basis": "b", "sensitivity": "s"},
        )


def test_missing_sensitivity_rejected():
    with pytest.raises(ValueError):
        DimensionScore(name="timing_window", value=80, basis="b",
                       confidence=0.8, sensitivity="")


def test_confidence_bounds_and_bool_rejected():
    for bad in (-0.1, 1.1, True, "high"):
        with pytest.raises(ValueError):
            DimensionScore(name="timing_window", value=80, basis="b",
                           confidence=bad, sensitivity="s")


def test_value_out_of_range_rejected():
    for bad in (-1, 101, float("nan")):
        with pytest.raises(ValueError):
            DimensionScore(name="timing_window", value=bad, basis="b",
                           confidence=0.8, sensitivity="s")


def test_unknown_dimension_rejected():
    with pytest.raises(ValueError):
        DimensionScore(name="vibes", value=80, basis="b",
                       confidence=0.8, sensitivity="s")


def test_dimensions_must_cover_exactly_six():
    dims = _dims()
    del dims["defensibility"]
    with pytest.raises(ValueError):
        validate_dimensions(dims)
    dims = _dims()
    dims["extra"] = (50, "b", 0.5, "s")
    with pytest.raises(ValueError):
        validate_dimensions(dims)


def test_tuple_and_mapping_coercion():
    d1 = ss._coerce_dimension("timing_window", (80, "b", 0.8, "s"))
    assert d1.value == 80 and d1.confidence == 0.8 and d1.evidence == ()
    d2 = ss._coerce_dimension(
        "timing_window", (80, "b", 0.8, "s", ["seen in scan A"]))
    assert d2.evidence == ("seen in scan A",)
    d3 = ss._coerce_dimension(
        "timing_window",
        {"value": 80, "basis": "b", "confidence": 0.8, "sensitivity": "s"},
    )
    assert d3.value == 80
    with pytest.raises(ValueError):
        ss._coerce_dimension("timing_window", (80, "b", 0.8))  # too short
    with pytest.raises(ValueError):
        ss._coerce_dimension("timing_window", "not-a-tuple")


def test_evidence_entries_must_be_nonempty_strings():
    with pytest.raises(ValueError):
        DimensionScore(name="timing_window", value=80, basis="b",
                       confidence=0.8, sensitivity="s", evidence=[" "])


def test_risk_action_watch_validation():
    with pytest.raises(ValueError):
        Risk(description="", severity=50, basis="b")
    with pytest.raises(ValueError):
        Risk(description="d", severity=101, basis="b")
    with pytest.raises(ValueError):
        RecommendedAction(action="a", rationale="r", effort="extreme")
    with pytest.raises(ValueError):
        WatchCondition(condition="c", would_change="")


def test_dimension_weights_validation():
    w = validate_dimension_weights(None)
    assert abs(sum(w.values()) - 1.0) < 1e-12
    bad = dict(DEFAULT_DIMENSION_WEIGHTS)
    bad["timing_window"] = 0.5
    with pytest.raises(ValueError):
        validate_dimension_weights(bad)
    with pytest.raises(ValueError):
        validate_dimension_weights({"timing_window": 1.0})


# --- composite math --------------------------------------------------------

def test_strength_composite_exact():
    # 80*.2 + 70*.2 + 60*.15 + 90*.15 + 75*.15 + 85*.15 = 76.5
    card = _strength()
    assert card.strength == 76.5
    assert card.mean_confidence == round(
        (0.8 + 0.7 + 0.6 + 0.9 + 0.75 + 0.85) / 6, 4)


def test_strength_composite_rejects_bad_shapes():
    with pytest.raises(ValueError):
        strength_composite([], DEFAULT_DIMENSION_WEIGHTS)


# --- L2: determinism -------------------------------------------------------

def test_identical_inputs_identical_card():
    a = _strength(as_of="2026-09-24T00:00:00+00:00")
    b = _strength(as_of="2026-09-24T00:00:00+00:00")
    assert a.to_dict() == b.to_dict()
    assert a.explain() == b.explain()


def test_identical_inputs_identical_advisory():
    r1 = advise(_score_card(), _strength())
    r2 = advise(_score_card(), _strength())
    assert r1.to_dict() == r2.to_dict()


# --- L3: real signals only -------------------------------------------------

def test_evidence_preserved_verbatim():
    card = _strength(dimensions=_dims(
        timing_window=(80, "b", 0.8, "s", ["scan A line 12", "scan B line 3"])))
    dim = next(d for d in card.dimensions if d.name == "timing_window")
    assert dim.evidence == ("scan A line 12", "scan B line 3")
    assert "scan A line 12" in card.explain()


def test_low_confidence_flagged_not_hidden():
    card = _strength(dimensions=_dims(
        defensibility=(60, "thin moat read", 0.3, "s")))
    low = card.low_confidence_dimensions
    assert [d.name for d in low] == ["defensibility"]
    assert "LOW CONFIDENCE" in card.explain()
    assert "low confidence" in card.plain_summary().lower()


# --- L4: risks surfaced, never subtracted -----------------------------------

def test_risks_do_not_move_composite():
    plain = _strength()
    risky = _strength(risks=[
        ("incumbent could clone in a quarter", 80, "they ship fast"),
        {"description": "needs his time", "severity": 40, "basis": "he is the bottleneck"},
    ])
    assert risky.strength == plain.strength
    text = risky.explain()
    assert "incumbent could clone" in text
    assert "not subtracted" in text


# --- actions / watches / weakest -------------------------------------------

def test_actions_and_watches_render_and_coerce():
    card = _strength(
        actions=[("ship prototype", "tests the core claim", "low")],
        watch_conditions=[("incumbent ships", "timing_window drops")],
    )
    text = card.explain()
    assert "ship prototype" in text and "incumbent ships" in text
    assert card.actions[0].effort == "low"


def test_weakest_dimensions_sorted():
    card = _strength()
    weakest = card.weakest_dimensions
    values = [d.value for d in weakest]
    assert values == sorted(values)
    assert weakest[0].name == "defensibility"  # 60 is the lowest


def test_plain_summary_speaks_plain():
    card = _strength(actions=[("ship prototype", "why", "low")])
    s = card.plain_summary()
    assert "76/100" in s
    assert "First move: ship prototype" in s
    assert "composite" not in s.lower()


# --- L5: advisory honesty ---------------------------------------------------

def test_advise_fusion_math_with_fit():
    report = advise(_score_card(), _strength(), direction_fit=0.6)
    # b=65/100=0.65, s=76.5/100=0.765
    expected = round(0.50 * 0.65 + 0.30 * 0.765 + 0.20 * 0.6, 4)
    assert report.combined == expected
    assert "0.50*0.6500 + 0.30*0.7650 + 0.20*0.6000" in report.math
    assert report.direction_fit == 0.6
    assert report.verdict_math  # direction verdict math disclosed


def test_advise_without_fit_reweights_and_says_so():
    report = advise(_score_card(), _strength())
    expected = round(0.625 * 0.65 + 0.375 * 0.765, 4)
    assert report.combined == expected
    assert "reweighted" in report.math
    assert report.direction_fit is None


def test_advise_rejects_mismatched_ids_and_types():
    with pytest.raises(ValueError):
        advise(_score_card("o1"), _strength("o2"))
    with pytest.raises(ValueError):
        advise("not-a-card", _strength())
    with pytest.raises(ValueError):
        advise(_score_card(), "not-a-strength-card")
    with pytest.raises(ValueError):
        advise(_score_card(), _strength(), direction_fit=1.5)


def test_directive_focus_order_is_weakest_first():
    report = advise(_score_card(), _strength(
        actions=[("ship prototype", "why", "low")]))
    focus = report.directive.focus_order
    assert focus[0] == "defensibility"  # weakest dimension leads
    assert any(f.startswith("action:") for f in focus)
    assert "defensibility" in report.directive.rationale


def test_rank_advisories_orders_and_restamps():
    r1 = advise(_score_card("o1", "Low"), _strength(
        "o1", "Low", dimensions=_dims(
            timing_window=(10, "b", 0.8, "s"),
            monetization_path=(10, "b", 0.8, "s"),
            defensibility=(10, "b", 0.8, "s"),
            resource_fit=(10, "b", 0.8, "s"),
            evidence_strength=(10, "b", 0.8, "s"),
            action_clarity=(10, "b", 0.8, "s"))))
    r2 = advise(_score_card("o2", "High"), _strength("o2", "High"))
    ranked = rank_advisories([r1, r2])
    assert [r.opportunity_id for r in ranked] == ["o2", "o1"]
    assert [r.directive.rank for r in ranked] == [1, 2]
    # tie-break by opportunity_id is deterministic
    ra = advise(_score_card("oa", "A"), _strength("oa", "A"))
    rb = advise(_score_card("ob", "B"), _strength("ob", "B"))
    assert ra.combined == rb.combined
    tied = rank_advisories([rb, ra])
    assert [r.opportunity_id for r in tied] == ["oa", "ob"]


def test_tier_follows_combined():
    report = advise(_score_card(), _strength(), direction_fit=0.9)
    assert report.tier in ("high", "watch", "low")
    assert report.tier == scoring.tier_for(report.combined * 100.0)


# --- serialization ----------------------------------------------------------

def test_card_round_trip():
    card = _strength(
        risks=[("r", 50, "b")],
        actions=[("a", "why", "high")],
        watch_conditions=[("c", "w")],
        notes="n",
        as_of="2026-09-24T00:00:00+00:00",
    )
    clone = StrengthCard.from_dict(card.to_dict())
    assert clone.to_dict() == card.to_dict()
    assert clone.to_dict()["schema_version"] == "1"


def test_report_serializes_with_schema():
    report = advise(_score_card(), _strength(), direction_fit=0.5)
    d = report.to_dict()
    assert d["schema_version"] == "1"
    assert d["directive"]["focus_order"]
    assert isinstance(report, AdvisorReport)
    assert isinstance(report.directive, UpgradeDirective)
