"""Tests for the feedlab feed-ranking transparency lab (hermetic, stdlib-only)."""

import json
from datetime import datetime, timezone

import pytest

from levi.feedlab.feedlab import (
    MODEL_VERSION,
    WEIGHTS,
    Post,
    compare,
    flag_bait,
    load_posts,
    rank_bait,
    rank_chronological,
    score,
    transparency,
)

NOW = datetime(2026, 9, 16, 16, 0, 0, tzinfo=timezone.utc)


def _post(**kw):
    base = dict(author="@t", text="hello world", posted_at="2026-09-16T15:00:00+00:00")
    base.update(kw)
    return Post(**base)


def test_weights_are_disclosed_and_stable():
    assert set(WEIGHTS) == {
        "relative_engagement",
        "outrage_language",
        "engagement_farming",
        "follower_asymmetry",
        "media_bonus",
        "recency",
    }
    assert MODEL_VERSION.startswith("feedlab-bait-model/")


def test_score_itemizes_every_point():
    p = _post(
        text="This is SHOCKING and outrageous, comment below!",
        likes=100,
        reposts=10,
        replies=5,
        follower_count=1000,
        has_media=True,
    )
    total, contributions = score(p, NOW)
    assert abs(total - sum(c["points"] for c in contributions)) < 1e-6
    signals = {c["signal"] for c in contributions}
    assert signals == set(WEIGHTS)
    for c in contributions:
        assert "observed" in c and "detail" in c and "weight" in c


def test_chronological_order_is_newest_first():
    posts = [
        _post(posted_at="2026-09-16T15:00:00+00:00"),
        _post(posted_at="2026-09-16T16:00:00+00:00"),
        _post(posted_at="2026-09-16T14:00:00+00:00"),
    ]
    ordered = rank_chronological(posts)
    assert [p.posted_at for p in ordered] == [
        "2026-09-16T16:00:00+00:00",
        "2026-09-16T15:00:00+00:00",
        "2026-09-16T14:00:00+00:00",
    ]


def test_bait_ranking_sorts_by_score_desc():
    posts = [
        _post(text="plain", likes=1, follower_count=10000),
        _post(
            text="SHOCKING outrage comment below",
            likes=500,
            reposts=200,
            replies=100,
            follower_count=1000,
            has_media=True,
        ),
    ]
    ranked = rank_bait(posts, NOW)
    assert ranked[0][1] >= ranked[1][1]
    assert "SHOCKING" in ranked[0][0].text


def test_flags_are_labeled_heuristic():
    p = _post(text="This is UNBELIEVABLE and TERRIFYING, retweet if you agree?")
    flags = flag_bait(p)
    kinds = {f["flag"] for f in flags}
    assert "outrage-language" in kinds
    assert "engagement-farming" in kinds
    assert "rage-bait-question" in kinds
    assert "caps-amplification" in kinds
    for f in flags:
        assert f["kind"] == "heuristic"
        assert f["basis"]


def test_no_flags_on_plain_post():
    flags = flag_bait(_post(text="The meeting is at noon in room 4."))
    assert flags == []


def test_compare_shows_movement_and_disclaimer():
    posts = [
        _post(
            author="@a",
            text="plain",
            posted_at="2026-09-16T16:00:00+00:00",
            likes=1,
            follower_count=10000,
        ),
        _post(
            author="@b",
            text="SHOCKING scandal, comment below!",
            posted_at="2026-09-16T15:00:00+00:00",
            likes=900,
            reposts=400,
            replies=1200,
            follower_count=250000,
        ),
    ]
    rep = compare(posts, NOW)
    assert rep["model"] == MODEL_VERSION
    assert "EDUCATIONAL SIMULATION" in rep["disclaimer"]
    assert len(rep["ranking"]) == 2
    for row in rep["ranking"]:
        assert "moved" in row and "top_signal" in row and "flags" in row


def test_load_posts_deny_closed(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps([{"author": "@a", "text": "hi", "likes": 3}]))
    posts = load_posts(good)
    assert len(posts) == 1 and posts[0].likes == 3

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"author": "", "text": "hi"}]))
    with pytest.raises(ValueError):
        load_posts(bad)

    neg = tmp_path / "neg.json"
    neg.write_text(json.dumps([{"author": "@a", "text": "hi", "likes": -1}]))
    with pytest.raises(ValueError):
        load_posts(neg)

    notarray = tmp_path / "notarray.json"
    notarray.write_text(json.dumps({"author": "@a"}))
    with pytest.raises(ValueError):
        load_posts(notarray)

    with pytest.raises(ValueError):
        load_posts(tmp_path / "missing.json")


def test_transparency_sorted_by_points_desc():
    p = _post(
        text="SHOCKING outrage, comment below!",
        likes=500,
        reposts=200,
        follower_count=1000,
        has_media=True,
    )
    ledger = transparency(p, NOW)
    points = [c["points"] for c in ledger]
    assert points == sorted(points, reverse=True)
