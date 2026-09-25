"""Hermetic tests for Wave Pulse (levi.demand.studio).

No network, no HOME writes (LEVI_HOME pointed at tmp_path), no randomness.
Grade math is hand-computed below; if the formula changes, these fail loudly.
"""

import json

import pytest

from levi.demand import studio
from levi.demand.studio import (
    ADAPTERS,
    GRADE_THRESHOLD,
    AdapterUnavailable,
    ContentBrief,
    ContentSignal,
    GradeResult,
    LocalFileAdapter,
    RedditPublicAdapter,
    TikTokAdapter,
    XAdapter,
    MetaAdapter,
    attention_score,
    conversation_score,
    extract_patterns,
    generate_brief,
    load_signals,
    originality_score,
    parse_reddit_listing,
    propagation_score,
    quality_grade,
    rank_signals,
    render_brief,
    save_brief,
    save_signals,
    velocity_multiplier,
)


def _sig(**kw):
    base = dict(id="t1", platform="tiktok", text="alpha beta gamma delta epsilon")
    base.update(kw)
    return ContentSignal(**base)


# --- component scores -------------------------------------------------------


def test_attention_from_completion_rate():
    score, basis = attention_score(_sig(metrics={"completion_rate": 80}))
    assert score == pytest.approx(80.0)
    assert "completion_rate" in basis


def test_attention_watch_over_duration():
    score, _ = attention_score(_sig(metrics={"avg_watch_s": 30, "duration_s": 40}))
    assert score == pytest.approx(75.0)


def test_attention_no_inputs_is_none():
    score, basis = attention_score(_sig())
    assert score is None
    assert basis == "no attention inputs"


def test_propagation_rate_vs_views():
    score, basis = propagation_score(_sig(metrics={"shares": 200, "views": 1000}))
    assert score == pytest.approx(20.0)
    assert basis == "rate-vs-views"


def test_propagation_weights_saves_and_dm():
    score, _ = propagation_score(
        _sig(metrics={"saves": 100, "dm_shares": 50, "views": 1000})
    )
    # 100*1.5 + 50*2 = 250 -> 25.0
    assert score == pytest.approx(25.0)


def test_conversation_comment_rate():
    score, _ = conversation_score(_sig(metrics={"comments": 50, "views": 1000}))
    # 100 * (50/1000) * 5 = 25
    assert score == pytest.approx(25.0)


def test_conversation_author_replies_bonus():
    plain, _ = conversation_score(_sig(metrics={"comments": 50, "views": 1000}))
    bonus, _ = conversation_score(
        _sig(metrics={"comments": 50, "views": 1000, "author_replies": 1})
    )
    assert bonus == pytest.approx(plain + 10.0)


def test_originality_identical_is_zero():
    text = "the quick brown fox jumps over the lazy dog today"
    score, _ = originality_score(_sig(text=text), [text])
    assert score == pytest.approx(0.0)


def test_originality_unrelated_is_high():
    score, _ = originality_score(
        _sig(text="alpha beta gamma delta epsilon zeta eta"),
        ["zebra quantum toaster refrigerator"],
    )
    assert score > 90.0


def test_originality_no_corpus_is_neutral():
    score, basis = originality_score(_sig(text="anything at all here"), [])
    assert score == pytest.approx(60.0)
    assert basis == "no-corpus-neutral"


def test_velocity_multiplier_bounds():
    assert velocity_multiplier(_sig()) == 1.0  # unknown age/actions: neutral
    hot = _sig(
        posted_at="2026-09-21T13:00:00+00:00",
        metrics={"likes": 100000, "comments": 5000, "shares": 2000},
    )
    assert velocity_multiplier(hot) == pytest.approx(1.3)
    # monkey-age it: ancient post with tiny action counts -> floor
    cold = _sig(
        posted_at="2020-01-01T00:00:00+00:00",
        metrics={"likes": 1},
    )
    assert velocity_multiplier(cold) == pytest.approx(0.8)


# --- unified grade -----------------------------------------------------------


def test_quality_grade_hand_computed():
    """0.35*80 + 0.30*20 + 0.20*25 + 0.15*100 = 54.0, velocity neutral."""
    s = _sig(
        text="alpha beta gamma delta epsilon zeta eta theta iota",
        metrics={
            "completion_rate": 80,
            "shares": 200,
            "views": 1000,
            "comments": 50,
        },
    )
    g = quality_grade(s, corpus=["zebra quantum toaster"])
    assert g.attention == pytest.approx(80.0)
    assert g.propagation == pytest.approx(20.0)
    assert g.conversation == pytest.approx(25.0)
    assert g.originality > 90.0
    # originality is ~100 here (no shared shingles), so:
    assert g.grade == pytest.approx(54.0, abs=0.5)
    assert g.coverage == pytest.approx(1.0)
    assert g.hypothesis is True


def test_quality_grade_reweights_missing_components():
    """Only text: attention/propagation/conversation unknown -> grade = originality."""
    s = _sig(text="lone wolf post with no metrics")
    g = quality_grade(s, corpus=[])
    assert g.attention is None
    assert g.propagation is None
    assert g.conversation is None
    assert g.grade == pytest.approx(60.0)  # neutral originality, full reweight
    assert g.coverage == pytest.approx(0.0)


def test_rank_signals_sorts_descending():
    weak = _sig(id="w", metrics={"completion_rate": 10})
    strong = _sig(id="s", metrics={"completion_rate": 95, "shares": 500, "views": 1000})
    ranked = rank_signals([weak, strong], corpus=["zzz"])
    assert [s.id for s, _ in ranked] == ["s", "w"]


# --- adapters -----------------------------------------------------------------


def test_reddit_parse_fixture():
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc123",
                        "title": "Test post",
                        "selftext": "body here",
                        "author": "someuser",
                        "score": 1500,
                        "num_comments": 200,
                        "num_crossposts": 3,
                        "all_awardings": [{"count": 2}],
                        "permalink": "/r/test/comments/abc123/test_post/",
                        "created_utc": 1758470400,
                    }
                }
            ]
        }
    }
    signals = parse_reddit_listing(payload)
    assert len(signals) == 1
    s = signals[0]
    assert s.platform == "reddit"
    assert s.id == "reddit:abc123"
    assert s.metrics["upvotes"] == 1500.0
    assert s.metrics["comments"] == 200.0
    assert s.metrics["awards"] == 2.0
    assert "Test post" in s.text


def test_keyed_adapters_raise_without_keys(monkeypatch):
    for cls, var in (
        (TikTokAdapter, "TIKTOK_API_KEY"),
        (XAdapter, "X_BEARER_TOKEN"),
        (MetaAdapter, "META_ACCESS_TOKEN"),
    ):
        monkeypatch.delenv(var, raising=False)
        ad = cls()
        assert ad.available() is False
        with pytest.raises(AdapterUnavailable):
            ad.fetch("anything")


def test_adapter_registry():
    assert set(ADAPTERS) == {"local", "reddit", "tiktok", "x", "meta"}


def test_local_file_adapter_roundtrip_and_query(tmp_path):
    p = tmp_path / "sig.jsonl"
    rows = [
        _sig(id="a", text="cats are great").to_dict(),
        _sig(id="b", text="dogs are great").to_dict(),
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    ad = LocalFileAdapter(p)
    assert len(ad.fetch(limit=10)) == 2
    assert [s.id for s in ad.fetch("cats", limit=10)] == ["a"]


# --- patterns & briefs ---------------------------------------------------------


def _graded_pair(sid, grade, text="Hook line here. Rest of post.", platform="tiktok"):
    s = _sig(
        id=sid,
        platform=platform,
        text=text,
        format="short_video",
        hashtags=["Test"],
        sound="sound1",
    )
    g = GradeResult(
        signal_id=sid,
        grade=grade,
        attention=80.0,
        propagation=70.0,
        conversation=60.0,
        originality=90.0,
        velocity_mult=1.0,
        coverage=1.0,
        basis="test",
    )
    return (s, g)


def test_extract_patterns_only_from_winners():
    graded = [
        _graded_pair("w1", 90.0, text="Stop doing this. Rest."),
        _graded_pair("w2", 80.0, text="Stop doing this. More rest? comment below"),
        _graded_pair("loser", 10.0, text="Unrelated filler post nobody saw."),
    ]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    assert pat.winners == 2
    assert pat.scanned == 3
    assert pat.top_hooks[0][0] == "Stop doing this"
    assert pat.top_hooks[0][1] == 2
    assert pat.cta_rate == pytest.approx(0.5)
    assert any("carousel" in gap for gap in pat.gaps)  # open lane flagged


def test_generate_and_render_brief():
    graded = [_graded_pair("w1", 90.0)]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    brief = generate_brief("comedy", graded, pat)
    assert isinstance(brief, ContentBrief)
    assert brief.niche == "comedy"
    assert brief.hypothesis is True
    assert any("REWRITE" in r for r in brief.risk_flags)
    text = render_brief(brief)
    assert "WAVE PULSE BRIEF — comedy" in text
    assert "HYPOTHESIS" in text
    assert "HOOK LIBRARY" in text


def test_storage_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    sigs = [_sig(id="x1"), _sig(id="x2")]
    p = save_signals(sigs, "test")
    assert p.exists()
    loaded = load_signals("test")
    assert [s.id for s in loaded] == ["x1", "x2"]
    brief = generate_brief("n", [], extract_patterns([]))
    bp = save_brief(brief, "test")
    payload = json.loads(bp.read_text(encoding="utf-8"))
    assert payload["niche"] == "n"
    assert payload["hypothesis"] is True


def test_reddit_adapter_is_public():
    ad = RedditPublicAdapter()
    assert ad.available() is True
    assert isinstance(ad, studio.SignalAdapter)
