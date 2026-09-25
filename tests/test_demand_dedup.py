"""Tests for DemandPulse dedup: normalization, near-dup guard, idempotent
scan/score paths, and the one-shot dedupe_store maintenance pass.

The honesty contract under test: repeats are occurrence metadata
(seen_count), never evidence — confidence and kind are untouched by a
repeat, and paraphrases outside the token-containment guard are NOT
merged (documented gap, not a bug).
"""

import pytest

from levi.demand.dedup import (
    NEAR_DUP_CONTAINMENT,
    find_duplicate,
    near_duplicate,
    normalize_text,
)
from levi.demand.pulse import DemandPulse


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


# -- normalization -----------------------------------------------------------


def test_normalize_text_collapses_variants():
    assert normalize_text("Need  Shifts—Help!") == "need shifts help"
    assert normalize_text("  need shifts help\n") == "need shifts help"
    assert normalize_text("NEED SHIFTS HELP") == "need shifts help"


def test_normalize_text_empty():
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


# -- near-dup guard ----------------------------------------------------------


def test_near_duplicate_exact():
    assert near_duplicate("need shifts help", "need shifts help") is True


def test_near_duplicate_contained_subset():
    # "need shifts help" is fully contained in the longer phrasing
    assert (
        near_duplicate(
            "need shifts help", "i need help scheduling shifts"
        )
        is True
    )


def test_near_duplicate_distinct_needs_not_merged():
    # only 2/3 of the smaller set is shared -> below the 0.8 bar
    assert (
        near_duplicate("need shifts help", "need tutoring help") is False
    )


def test_near_duplicate_paraphrase_gap_documented():
    # vocabulary swap: the guard honestly does NOT catch this
    assert (
        near_duplicate("need shift help", "require rota assistance") is False
    )


def test_near_duplicate_empty_never_matches():
    assert near_duplicate("", "need shifts help") is False
    assert near_duplicate("", "") is True  # both empty: exact match


def test_find_duplicate_prefers_exact_then_earliest():
    cands = [("a", "i need help scheduling shifts"), ("b", "need shifts help")]
    assert find_duplicate("need shifts help", cands) == "b"  # exact wins
    cands = [("a", "i need help scheduling shifts")]
    assert find_duplicate("need shifts help", cands) == "a"  # near-dupe
    assert find_duplicate("need tutoring help", cands) is None
    assert NEAR_DUP_CONTAINMENT == 0.8


# -- scan_seed idempotency ----------------------------------------------------


def test_scan_seed_twice_is_one_signal(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    first = dp.scan_seed("need shifts help")
    second = dp.scan_seed("need shifts help")
    assert len(dp.signals) == 1
    assert second.id == first.id
    assert second.seen_count == 2
    # repeats are not evidence: confidence untouched
    assert second.confidence == 0.35
    assert second.kind == "HYPOTHESIS"


def test_scan_seed_case_whitespace_variant_is_dupe(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    dp.scan_seed("Need  Shifts Help!")
    dp.scan_seed("need shifts help")
    assert len(dp.signals) == 1
    assert dp.signals[0].seen_count == 2


def test_scan_seed_near_dupe_merges(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    dp.scan_seed("I need help scheduling shifts")
    dp.scan_seed("need shifts help")
    assert len(dp.signals) == 1
    assert dp.signals[0].seen_count == 2


def test_scan_seed_is_segment_scoped(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    dp.scan_seed("need shifts help", segment="general")
    dp.scan_seed("need shifts help", segment="trucking")
    assert len(dp.signals) == 2  # a watched segment never swallows another's


def test_scan_seed_distinct_texts_coexist(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    dp.scan_seed("need shifts help")
    dp.scan_seed("need tutoring help")
    assert len(dp.signals) == 2


def test_seen_count_survives_reload(tmp_path):
    path = tmp_path / "dp.json"
    dp = DemandPulse(path=path)
    dp.scan_seed("need shifts help")
    dp.scan_seed("need shifts help")
    dp2 = DemandPulse(path=path)
    assert len(dp2.signals) == 1
    assert dp2.signals[0].seen_count == 2


# -- score idempotency -------------------------------------------------------


def test_score_five_factor_twice_is_one_card(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("people need offline-first billing", segment="trades")
    first = dp.score_five_factor(sig.id, "Offline billing", _factors())
    second = dp.score_five_factor(sig.id, "Offline billing", _factors())
    assert len(dp.score_cards) == 1
    assert second.opportunity_id == first.opportunity_id


def test_score_five_factor_title_variant_is_one_card(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("x", segment="trades")
    dp.score_five_factor(sig.id, "Shift planner", _factors())
    dp.score_five_factor(sig.id, "shift  planner", _factors())
    assert len(dp.score_cards) == 1


def test_score_five_factor_rescore_keeps_highest(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("x", segment="trades")
    low = dp.score_five_factor(sig.id, "Widget", _factors(demand=(10, "weak")))
    high = dp.score_five_factor(sig.id, "Widget", _factors(demand=(95, "strong")))
    assert len(dp.score_cards) == 1
    assert dp.score_cards[0].composite == high.composite
    assert dp.score_cards[0].composite > low.composite


def test_score_opportunity_twice_is_one(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("x")
    first = dp.score_opportunity(sig.id, "Dispatch-lite")
    second = dp.score_opportunity(sig.id, "Dispatch-lite ")
    assert len(dp.opportunities) == 1
    assert second.id == first.id


# -- one-shot maintenance ----------------------------------------------------


def _legacy_dupe_store(tmp_path):
    """Hand-build a store the way the old code left it: blind appends."""
    from levi.demand.pulse import DemandSignal, Opportunity
    from levi.demand.scoring import score_card

    path = tmp_path / "dp.json"
    dp = DemandPulse(path=path)
    # 3 exact-text dupes (same id, as scan_seed used to produce) + 1 near-dupe
    for _ in range(3):
        dp.signals.append(
            DemandSignal(
                id="aaaabbbb",
                need="need shifts help",
                segment="general",
                evidence="user_or_context_seed",
                confidence=0.35,
                kind="HYPOTHESIS",
            )
        )
    dp.signals.append(
        DemandSignal(
            id="ccccdddd",
            need="I need help scheduling shifts",
            segment="general",
            evidence="user_or_context_seed",
            confidence=0.35,
            kind="HYPOTHESIS",
        )
    )
    dp.signals.append(
        DemandSignal(
            id="eeeeffff",
            need="need shifts help",
            segment="trucking",  # same words, other segment: stays
            evidence="user_or_context_seed",
            confidence=0.35,
            kind="HYPOTHESIS",
        )
    )
    dp.opportunities.append(
        Opportunity(
            id="opp1",
            demand_id="d1",
            title="Local tutoring",
            demand_score=0.6,
            serviceability=0.6,
            startup_cost=0.2,
        )
    )
    dp.opportunities.append(
        Opportunity(
            id="opp1",  # legacy twin id
            demand_id="d1",
            title="Local tutoring",
            demand_score=0.6,
            serviceability=0.6,
            startup_cost=0.2,
        )
    )
    for i, comp in enumerate((40, 90, 60)):
        dp.score_cards.append(
            score_card(
                "card1",
                "Shift planner",
                _factors(demand=(comp, f"round {i}")),
            )
        )
    dp._persist()
    return dp


def test_dedupe_store_collapses_legacy_dupes(tmp_path):
    dp = _legacy_dupe_store(tmp_path)
    report = dp.dedupe_store()
    assert report["signals"] == {"before": 5, "after": 2, "merged": 3}
    assert report["opportunities"] == {"before": 2, "after": 1, "merged": 1}
    assert report["score_cards"] == {"before": 3, "after": 1, "merged": 2}
    # earliest wins; seen_counts fold in; confidence untouched
    general = [s for s in dp.signals if s.segment == "general"]
    assert len(general) == 1
    assert general[0].seen_count == 4
    assert general[0].confidence == 0.35
    assert general[0].kind == "HYPOTHESIS"
    # segment-scoped: the trucking twin survives
    assert [s for s in dp.signals if s.segment == "trucking"][0].seen_count == 1
    # highest composite wins for cards
    assert dp.score_cards[0].composite == 90 * 0.3 + 70 * 0.25 + 60 * 0.2 + 50 * 0.15 + 40 * 0.1


def test_dedupe_store_dry_run_touches_nothing(tmp_path):
    dp = _legacy_dupe_store(tmp_path)
    report = dp.dedupe_store(dry_run=True)
    assert report["dry_run"] is True
    assert report["signals"]["before"] == 5
    assert len(dp.signals) == 5  # untouched
    assert len(dp.score_cards) == 3


def test_dedupe_store_persists(tmp_path):
    path = tmp_path / "dp.json"
    dp = _legacy_dupe_store(tmp_path)
    dp.dedupe_store()
    dp2 = DemandPulse(path=path)
    assert len(dp2.signals) == 2
    assert len(dp2.score_cards) == 1


# -- score-card segment rule: dedupe by (title, segment), never title alone --


def test_score_card_segment_defaults_to_general():
    from levi.demand.scoring import score_card

    card = score_card("opp1", "Shift planner", _factors())
    assert card.segment == "general"


def test_score_card_carries_explicit_segment():
    from levi.demand.scoring import score_card

    card = score_card("opp1", "Shift planner", _factors(), segment="enterprise")
    assert card.segment == "enterprise"


def test_old_stored_card_without_segment_loads_as_general():
    from levi.demand.scoring import ScoreCard

    raw = {
        "opportunity_id": "abc123",
        "title": "Shift planner",
        "factors": [
            {"name": "demand", "value": 80, "basis": "surveyed 40 users"},
            {"name": "market_size", "value": 70, "basis": "TAM estimate"},
            {"name": "competition_gap", "value": 60, "basis": "3 incumbents"},
            {"name": "trend_velocity", "value": 50, "basis": "doubling YoY"},
            {"name": "entry_feasibility", "value": 40, "basis": "2 engineers"},
        ],
        "weights": {
            "demand": 0.30,
            "market_size": 0.25,
            "competition_gap": 0.20,
            "trend_velocity": 0.15,
            "entry_feasibility": 0.10,
        },
        "threshold": 75.0,
        "notes": "",
        # no "segment" key: pre-segment stored form
    }
    card = ScoreCard.from_dict(raw)
    assert card.segment == "general"
    assert "segment" in card.to_dict()


def test_score_five_factor_populates_segment_from_demand(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    sig = dp.scan_seed("I need help scheduling shifts", segment="enterprise")
    card = dp.score_five_factor(sig.id, "Shift planner", _factors())
    assert card.segment == "enterprise"


def test_dedupe_store_keeps_same_title_across_segments(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    s1 = dp.scan_seed("need shifts a", segment="general")
    s2 = dp.scan_seed("need shifts b", segment="enterprise")
    dp.score_five_factor(s1.id, "Shift planner", _factors())
    dp.score_five_factor(s2.id, "Shift planner", _factors())
    report = dp.dedupe_store()
    assert report["score_cards"]["after"] == 2
    segments = {c.segment for c in dp.score_cards}
    assert segments == {"general", "enterprise"}


def test_dedupe_store_collapses_same_title_and_segment(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    s1 = dp.scan_seed("need shifts a", segment="general")
    s2 = dp.scan_seed("need shifts b", segment="general")
    low = dp.score_five_factor(s1.id, "Shift planner", _factors())
    high = dp.score_five_factor(
        s2.id, "Shift planner", _factors(demand=(100, "surveyed 400 users"))
    )
    assert high.composite > low.composite
    report = dp.dedupe_store()
    assert report["score_cards"]["after"] == 1
    assert dp.score_cards[0].composite == pytest.approx(high.composite)
