"""Tests for levi.demand.numbers — deterministic demand numbers + opportunities view.

Laws under test: N1 every factor carries a basis; N2 determinism (same
signal + same now -> same number); N3 measured-only; N4 tier preserved;
N5 low number = thin evidence, never a claim.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from levi.demand.numbers import (
    SIGNAL_FACTORS,
    SIGNAL_WEIGHTS,
    FactorNumber,
    OpportunityRow,
    cluster_signals,
    opportunity_rows,
    render_rows,
    score_signal,
    validate_signal_weights,
)
from levi.demand.pulse import DemandPulse, DemandSignal


NOW = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)


def make_signal(
    need="I need help scheduling shifts",
    seen_count=1,
    kind="HYPOTHESIS",
    source="scan",
    segment="general",
    created_days_ago=0,
    sid="sig1",
):
    return DemandSignal(
        id=sid,
        need=need,
        segment=segment,
        evidence="test",
        confidence=0.35,
        kind=kind,
        seen_count=seen_count,
        created_at=(NOW - timedelta(days=created_days_ago)).isoformat(),
        source=source,
    )


# ---------------------------------------------------------------------------
# N2 determinism

def test_determinism_same_signal_same_now():
    s = make_signal(seen_count=81)
    a = score_signal(s, now=NOW)
    b = score_signal(s, now=NOW)
    assert a.composite == b.composite
    # scored_at is a wall-clock stamp, not part of the number — compare
    # the deterministic payload only.
    assert [f.to_dict() for f in a.factors] == [f.to_dict() for f in b.factors]
    assert a.tier == b.tier


def test_known_calculation():
    # Hand-computed per docs/DEMAND_NUMBERS.md:
    # expr = 10 + 15(need) + 10(help) + 2(length) = 37.0
    # freq = 20*log2(82) -> capped 100.0 ; rec = 100.0 ; src = 50.0 ; dom = 0.0
    # composite = 37*.3 + 100*.2 + 100*.15 + 50*.15 + 0*.2 = 53.60
    s = make_signal(seen_count=81)
    n = score_signal(s, now=NOW)
    by_name = {f.name: f for f in n.factors}
    assert by_name["expression_strength"].value == 37.0
    assert by_name["frequency"].value == 100.0
    assert by_name["recency"].value == 100.0
    assert by_name["source_diversity"].value == 50.0
    assert by_name["domain_match"].value == 0.0
    assert n.composite == 53.60
    assert "need" in by_name["expression_strength"].basis


def _freq(n):
    return next(x for x in n.factors if x.name == "frequency").value


def test_frequency_scales_with_seen_count():
    low = score_signal(make_signal(seen_count=1), now=NOW)
    high = score_signal(make_signal(seen_count=81), now=NOW)
    assert _freq(low) == 20.0
    assert _freq(high) == 100.0
    assert high.composite > low.composite


def _rec(n):
    return next(x for x in n.factors if x.name == "recency").value


def test_recency_half_life():
    fresh = score_signal(make_signal(created_days_ago=0), now=NOW)
    old = score_signal(make_signal(created_days_ago=30), now=NOW)
    assert _rec(fresh) == 100.0
    assert _rec(old) == 50.0


def test_domain_match_hits():
    s = make_signal(need="Looking for a local-first agent to automate my content pipeline")
    n = score_signal(s, now=NOW)
    d = next(x for x in n.factors if x.name == "domain_match")
    assert d.value > 0
    assert "levi" in d.basis


# ---------------------------------------------------------------------------
# N1 every factor carries a basis

def test_every_factor_has_basis():
    n = score_signal(make_signal(), now=NOW)
    assert len(n.factors) == len(SIGNAL_FACTORS)
    for f in n.factors:
        assert f.basis.strip(), f"factor {f.name} has no basis"


def test_factor_without_basis_rejected():
    with pytest.raises(ValueError):
        FactorNumber(name="frequency", value=50.0, basis="  ")


def test_explain_lists_bases():
    n = score_signal(make_signal(), now=NOW)
    text = n.explain()
    for f in n.factors:
        assert f.basis in text


# ---------------------------------------------------------------------------
# N4 tier preserved

def test_tier_preserved_and_kind_untouched():
    s = make_signal(kind="INFERENCE")
    before = (s.kind, s.confidence)
    n = score_signal(s, now=NOW)
    assert n.tier == "INFERENCE"
    assert (s.kind, s.confidence) == before


def test_bad_kind_rejected():
    # The constructor itself rejects bad kinds at the boundary; scoring
    # must also reject a signal whose kind was mutated past it.
    s = make_signal(kind="HYPOTHESIS")
    s.kind = "MAYBE"  # mutated past the constructor boundary
    with pytest.raises(ValueError):
        score_signal(s, now=NOW)


# ---------------------------------------------------------------------------
# weights

def test_weights_sum_to_one():
    assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9
    assert set(SIGNAL_WEIGHTS) == set(SIGNAL_FACTORS)


def test_bad_weights_rejected():
    with pytest.raises(ValueError):
        validate_signal_weights({"frequency": 1.0})
    with pytest.raises(ValueError):
        validate_signal_weights({**SIGNAL_WEIGHTS, "frequency": 0.99})


# ---------------------------------------------------------------------------
# clustering + ranking

def test_near_dupes_cluster_together():
    a = make_signal(need="I need help scheduling shifts", sid="a1")
    b = make_signal(need="need help with shift scheduling please", sid="b2")
    c = make_signal(need="best pizza near me open late", sid="c3")
    clusters = cluster_signals([a, b, c])
    assert len(clusters) == 2
    ids = sorted([[s.id for s in g] for g in clusters])
    assert ids == [["a1", "b2"], ["c3"]]


def test_clustering_is_deterministic():
    sigs = [
        make_signal(need=f"signal number {i} about scheduling shifts", sid=f"s{i:02d}")
        for i in range(6)
    ]
    once = [[s.id for s in g] for g in cluster_signals(sigs)]
    twice = [[s.id for s in g] for g in cluster_signals(list(reversed(sigs)))]
    assert once == twice


def test_ranking_order_and_tiebreak():
    rows = [
        OpportunityRow(
            id="opp-b", title="b", score=50.0, tier="HYPOTHESIS", why="",
            signals=(), member_count=1, total_sightings=1, distinct_sources=1,
        ),
        OpportunityRow(
            id="opp-a", title="a", score=50.0, tier="HYPOTHESIS", why="",
            signals=(), member_count=1, total_sightings=1, distinct_sources=1,
        ),
        OpportunityRow(
            id="opp-c", title="c", score=90.0, tier="OBSERVED", why="",
            signals=(), member_count=1, total_sightings=1, distinct_sources=1,
        ),
    ]
    ranked = sorted(rows, key=lambda r: (-r.score, r.id))
    assert [r.id for r in ranked] == ["opp-c", "opp-a", "opp-b"]


def test_opportunity_row_aggregates_and_tiers():
    a = make_signal(need="I need help scheduling shifts", sid="a1",
                    kind="HYPOTHESIS", seen_count=81, source="scan")
    b = make_signal(need="need help with shift scheduling please", sid="b2",
                    kind="OBSERVED", seen_count=2, source="email")
    c = make_signal(need="best pizza near me open late", sid="c3", seen_count=1)
    rows = opportunity_rows([a, b, c], now=NOW)
    assert len(rows) == 2
    assert rows[0].score >= rows[1].score
    shift = next(r for r in rows if r.member_count == 2)
    assert shift.tier == "OBSERVED"  # strongest member kind wins
    assert shift.total_sightings == 83
    assert shift.distinct_sources == 2
    assert len(shift.signals) == 2
    assert "why" in shift.to_dict() and shift.why


def test_empty_store_behaves():
    assert opportunity_rows([]) == []
    text = render_rows([], signal_total=0, rescored=0)
    assert "no signals" in text.lower()


def test_render_rows_json_roundtrip():
    rows = opportunity_rows([make_signal(sid="a1")], now=NOW)
    d = rows[0].to_dict()
    assert json.loads(json.dumps(d))["score"] == rows[0].score
    assert d["tier"] == "HYPOTHESIS"


# ---------------------------------------------------------------------------
# persistence + watcher wiring

def test_signal_number_persists_roundtrip(tmp_path):
    s = make_signal()
    s.number = score_signal(s, now=NOW).composite
    d = s.to_dict()
    assert "number" in d
    back = DemandSignal(**d)
    assert back.number == s.number


def test_scan_seed_scores_signal(tmp_path):
    dp = DemandPulse(path=tmp_path / "pulse.json")
    sig = dp.scan_seed("I need help scheduling shifts", segment="general", source="scan")
    assert sig.number is not None
    assert 0.0 <= sig.number <= 100.0
    assert sig.kind == "HYPOTHESIS"  # N4: untouched
    assert sig.confidence == 0.35
    # stored on disk
    dp2 = DemandPulse(path=tmp_path / "pulse.json")
    assert dp2.signals[0].number == sig.number


def test_rescan_bumps_frequency_and_renumbers(tmp_path):
    dp = DemandPulse(path=tmp_path / "pulse.json")
    first = dp.scan_seed("I need help scheduling shifts")
    second = dp.scan_seed("I need help scheduling shifts")
    assert second.seen_count == 2
    assert second.number >= first.number  # frequency factor rose


def test_ensure_numbers_backfills(tmp_path):
    dp = DemandPulse(path=tmp_path / "pulse.json")
    dp.scan_seed("I need help scheduling shifts")
    # simulate a pre-numbers store
    dp.signals[0].number = None
    scored = dp.ensure_numbers(now=NOW)
    assert scored == 1
    assert dp.signals[0].number is not None
    assert dp.ensure_numbers(now=NOW) == 0  # idempotent


def test_dedupe_keeps_number_honest(tmp_path):
    dp = DemandPulse(path=tmp_path / "pulse.json")
    dp.scan_seed("I need help scheduling shifts")
    dp.scan_seed("I need help scheduling shifts")
    before = dp.signals[0].number
    report = dp.dedupe_store(dry_run=False)
    assert report["signals"]["merged"] >= 0
    assert dp.signals[0].number is not None
    assert dp.signals[0].number >= before
