"""Regression tests for the DemandPulse signal-quality build (2026-09-24).

Covers the junk patterns found in the 100-signal live diagnosis:
  - word-boundary marker matching (housebroken/wanted false hits)
  - third-person headline rejection
  - supply-side offer / template rejection
  - HTML entity normalization
  - genuine specific needs retained
  - origin provenance required and preserved on scan_seed
  - repeated source-item polls do not inflate frequency
  - cross-source near-duplicates corroborate via source_diversity
    (dedup stays scoped to (segment, source) — source labels are
    preserved; the diversity factor harvests the corroboration)
  - junk quarantined, reversible, never deleted
  - scoring calibration: distinct items, reliability multiplier,
    determinism, honest basis

Hermetic: HOME/LEVI_HOME redirected, no network, no randomness.
"""

import pytest

from levi.demand import watcher as wmod
from levi.demand.numbers import score_signal
from levi.demand.pulse import DemandPulse


@pytest.fixture()
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    return tmp_path


def _dp(tmp_path):
    return DemandPulse(path=tmp_path / "dp.json")


# ---------------------------------------------------------------------------
# extraction gates
# ---------------------------------------------------------------------------


def test_word_boundary_broken_not_in_housebroken():
    assert wmod.extract_needs("He is smart, housebroken, and crate trained.") == []


def test_word_boundary_i_want_not_in_wanted():
    assert wmod.extract_needs(
        "I left after 2 months because I wanted to stay closer to home."
    ) == []


def test_third_person_headline_rejected():
    assert wmod.extract_needs(
        "Locals reportedly frustrated with Waymo's self-driving cars."
    ) == []


def test_third_person_broken_rejected():
    assert wmod.extract_needs("At one time his jaw was broken.") == []


def test_third_person_pain_rejected():
    assert wmod.extract_needs(
        "The market has real pain points in onboarding right now."
    ) == []


def test_supply_side_offer_rejected():
    assert wmod.extract_needs(
        "What I can build for you: I want to solve your bottleneck fast."
    ) == []


def test_promo_subject_rejected():
    assert wmod.extract_needs("Still Looking For New Work From Home Jobs?") == []


def test_content_free_request_rejected():
    assert wmod.extract_needs("Happy for any recommendations!") == []
    assert wmod.extract_needs("I need help") == []


def test_html_entities_normalized():
    got = wmod.extract_needs(
        "I don&#39;t want another subscription, I need a one-time invoice tool."
    )
    assert len(got) == 1
    assert "don't" in got[0]
    assert "&#39;" not in got[0]


def test_genuine_specific_needs_retained():
    got = wmod.extract_needs(
        "I need a better dog crate that does not fall apart in a month."
    )
    assert len(got) == 1
    got = wmod.extract_needs(
        "My back is killing me; I am desperate for a mattress that helps "
        "with pain."
    )
    assert len(got) == 1


def test_extraction_deterministic():
    text = "I need a better dog crate that does not fall apart in a month."
    assert wmod.extract_needs(text) == wmod.extract_needs(text)


# ---------------------------------------------------------------------------
# provenance on scan_seed
# ---------------------------------------------------------------------------


def test_scan_seed_accepts_origin_with_observed_evidence(herm, tmp_path):
    dp = _dp(tmp_path)
    sig = dp.scan_seed(
        "I need a better dog crate that does not fall apart.",
        segment="general",
        source="rss",
        origin={"link": "https://example.com/item/1", "feed": "https://ex.com/f"},
    )
    assert sig.evidence == "observed:rss"
    assert sig.origin == {
        "link": "https://example.com/item/1",
        "feed": "https://ex.com/f",
    }
    assert sig.origins == [sig.origin]
    assert sig.kind == "HYPOTHESIS"
    assert sig.confidence == 0.35


def test_scan_seed_without_origin_keeps_seed_evidence(herm, tmp_path):
    dp = _dp(tmp_path)
    sig = dp.scan_seed("I need a better dog crate.")
    assert sig.evidence == "user_or_context_seed"
    assert sig.origin is None
    assert sig.origins == []


def test_scan_seed_rejects_bad_origin(herm, tmp_path):
    dp = _dp(tmp_path)
    with pytest.raises(ValueError):
        dp.scan_seed("I need a dog crate.", origin="not-a-dict")


def test_dupe_merges_origin_without_inflating_frequency(herm, tmp_path):
    dp = _dp(tmp_path)
    first = dp.scan_seed(
        "I need a better dog crate.",
        source="rss",
        origin={"link": "https://example.com/item/1"},
    )
    # Same need, same channel, DIFFERENT source item -> merge, origins grow.
    second = dp.scan_seed(
        "I need a better dog crate!",
        source="rss",
        origin={"link": "https://example.com/item/2"},
    )
    assert second.id == first.id
    assert second.seen_count == 2
    assert len(second.origins) == 2
    # Re-poll of the SAME item -> seen_count bumps (occurrence metadata)
    # but origins do not grow, so the frequency factor is unchanged.
    third = dp.scan_seed(
        "I need a better dog crate?",
        source="rss",
        origin={"link": "https://example.com/item/1"},
    )
    assert third.id == first.id
    assert len(third.origins) == 2
    assert third.number == second.number
    # ... and the number reflects 2 distinct items, not 3 sightings.
    freq = next(
        f for f in dp._score_signal(third).factors if f.name == "frequency"
    )
    assert "2 distinct observed item(s)" in freq.basis


def test_cross_source_keeps_labels_and_corroborates(herm, tmp_path):
    dp = _dp(tmp_path)
    a = dp.scan_seed(
        "I need a better dog crate that lasts.",
        source="rss",
        origin={"link": "https://example.com/item/1"},
    )
    b = dp.scan_seed(
        "I need a better dog crate that lasts.",
        source="hn",
        origin={"link": "https://news.example/item/9"},
    )
    # Dedup stays scoped to (segment, source): labels preserved.
    assert a.id != b.id
    assert {a.source, b.source} == {"rss", "hn"}
    # But the diversity factor counts the cross-channel corroboration.
    div_a = next(
        f for f in dp._score_signal(a).factors if f.name == "source_diversity"
    )
    div_b = next(
        f for f in dp._score_signal(b).factors if f.name == "source_diversity"
    )
    assert div_a.value == 75.0
    assert div_b.value == 75.0
    assert "2 distinct channels" in div_a.basis


# ---------------------------------------------------------------------------
# scoring calibration
# ---------------------------------------------------------------------------


def _sig(**over):
    base = dict(
        id="s1",
        need="I need a better dog crate that does not fall apart in a month.",
        segment="general",
        kind="HYPOTHESIS",
        seen_count=1,
        created_at="2026-09-24T00:00:00+00:00",
        source="rss",
    )
    base.update(over)
    return type("S", (), base)()


def test_frequency_counts_distinct_items_not_repolls():
    one = score_signal(_sig(), distinct_items=1, source_reliability=0.5)
    many = score_signal(_sig(), distinct_items=12, source_reliability=0.5)
    f1 = next(f for f in one.factors if f.name == "frequency")
    f12 = next(f for f in many.factors if f.name == "frequency")
    assert f1.value < f12.value
    assert "12 distinct observed item(s)" in f12.basis
    assert many.composite > one.composite


def test_frequency_legacy_fallback_says_so():
    n = score_signal(_sig(seen_count=81), source_reliability=0.5)
    f = next(x for x in n.factors if x.name == "frequency")
    assert f.value == 100.0
    assert "legacy: no item provenance" in f.basis


def test_reliability_calibration_is_stated():
    low = score_signal(_sig(), distinct_items=4, source_reliability=0.0)
    mid = score_signal(_sig(), distinct_items=4, source_reliability=0.5)
    high = score_signal(_sig(), distinct_items=4, source_reliability=1.0)
    assert low.reliability_multiplier == 0.75
    assert mid.reliability_multiplier == 1.0
    assert high.reliability_multiplier == 1.25
    assert low.composite < mid.composite < high.composite
    assert low.reliability == 0.0 and high.reliability == 1.0


def test_reliability_rejects_garbage():
    for bad in (-0.1, 1.1, float("nan"), "high", True):
        with pytest.raises(ValueError):
            score_signal(_sig(), source_reliability=bad)


def test_scoring_deterministic():
    a = score_signal(_sig(), distinct_items=3, source_reliability=0.7)
    b = score_signal(_sig(), distinct_items=3, source_reliability=0.7)
    assert a.composite == b.composite
    assert [f.value for f in a.factors] == [f.value for f in b.factors]


def test_strong_need_outscores_junk():
    strong = score_signal(
        _sig(
            need="I am desperate for a mattress that helps with my back pain; "
            "willing to pay for one that actually works."
        ),
        distinct_items=5,
        distinct_sources=2,
        source_reliability=0.8,
    )
    weak = score_signal(
        _sig(need="Happy for any recommendations!"),
        distinct_items=1,
        source_reliability=0.5,
    )
    assert strong.composite > weak.composite
    assert strong.composite > 50.0


def test_source_diversity_discriminates():
    solo = score_signal(_sig(), distinct_sources=1)
    coro = score_signal(_sig(), distinct_sources=2)
    v1 = next(f for f in solo.factors if f.name == "source_diversity").value
    v2 = next(f for f in coro.factors if f.name == "source_diversity").value
    assert v1 == 50.0 < v2 == 75.0


# ---------------------------------------------------------------------------
# channel reliability from observed yield
# ---------------------------------------------------------------------------


def test_channel_reliability_neutral_without_data(herm, tmp_path):
    dp = _dp(tmp_path)
    assert dp.channel_reliability("rss") == 0.5


def test_channel_reliability_from_yield_counters(herm, tmp_path):
    st = wmod.WatcherState.load()
    st.channels["rss"] = {"quality": {"candidates": 20, "kept": 15}}
    st.channels["hn"] = {"quality": {"candidates": 4, "kept": 4}}
    st.save()
    dp = _dp(tmp_path)
    assert dp.channel_reliability("rss") == pytest.approx(0.75)
    # <10 samples -> stated neutral prior, never fake precision
    assert dp.channel_reliability("hn") == 0.5


# ---------------------------------------------------------------------------
# quarantine
# ---------------------------------------------------------------------------


def test_quarantine_flags_legacy_feed_signal(herm, tmp_path):
    dp = _dp(tmp_path)
    sig = dp.scan_seed("I need a better dog crate.", source="rss")
    report = dp.run_quarantine(dry_run=True)
    assert report["quarantined"] == 1
    assert report["dry_run"] is True
    assert not sig.quarantined  # dry run touches nothing
    report = dp.run_quarantine()
    assert report["quarantined"] == 1
    assert sig.quarantined is True
    assert "provenance" in sig.quarantine_reason
    # Kept in the store, out of the live views.
    assert len(dp.signals) == 1
    assert dp.live_signals() == []


def test_quarantine_flags_supply_side_and_ops(herm, tmp_path):
    dp = _dp(tmp_path)
    dp.scan_seed("I can build anything you need, hire me today.", source="text")
    dp.scan_seed("engagement: weekly digest stats rollup", source="scan")
    report = dp.run_quarantine()
    assert report["quarantined"] == 2
    assert dp.live_signals() == []


def test_quarantine_spares_provenanced_signals(herm, tmp_path):
    dp = _dp(tmp_path)
    dp.scan_seed(
        "I need a better dog crate.",
        source="rss",
        origin={"link": "https://example.com/item/1"},
    )
    report = dp.run_quarantine()
    assert report["quarantined"] == 0
    assert len(dp.live_signals()) == 1


def test_unquarantine_reverses(herm, tmp_path):
    dp = _dp(tmp_path)
    sig = dp.scan_seed("I need a better dog crate.", source="rss")
    dp.run_quarantine()
    assert dp.live_signals() == []
    assert dp.unquarantine(sig.id) is True
    assert sig.quarantined is False
    assert len(dp.live_signals()) == 1
    assert dp.unquarantine("nope") is False


def test_quarantine_persists(herm, tmp_path):
    dp = _dp(tmp_path)
    sig = dp.scan_seed("I need a better dog crate.", source="rss")
    dp.run_quarantine()
    dp2 = DemandPulse(path=tmp_path / "dp.json")
    again = next(s for s in dp2.signals if s.id == sig.id)
    assert again.quarantined is True
    assert again.quarantine_reason != ""
