"""Hermetic tests for levi.recommender (tmp HOME, fixed clock, no network)."""

import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from levi.recommender import SHELF
from levi.recommender.engine import (
    content_fit,
    cosine,
    explain,
    goal_alignment,
    liked_centroid,
    mmr_order,
    quality_score,
    recency_score,
    recommend,
)
from levi.recommender.model import Goal, Item, check_rating, parse_topics
from levi.recommender.weights import (
    DEFAULT_WEIGHTS,
    normalize_weights,
    parse_weights,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def _item(id, title, kind, topics, days_old=0):
    return Item(
        id=id,
        title=title,
        kind=kind,
        topics=topics,
        added_at=(NOW - timedelta(days=days_old)).isoformat(),
    )


def _goal(id, title, topics, kind_filter=()):
    return Goal(id=id, title=title, topics=topics, kind_filter=list(kind_filter))


def _corpus():
    items = [
        _item(
            "py-async", "Asyncio deep dive", "course", {"python": 1.0, "asyncio": 0.9}
        ),
        _item("py-web", "Flask web apps", "course", {"python": 0.8, "web": 0.9}),
        _item("rust-book", "Rust systems", "book", {"rust": 1.0, "systems": 0.8}),
        _item(
            "py-async-2", "Asyncio patterns", "course", {"python": 1.0, "asyncio": 1.0}
        ),
    ]
    goals = [
        _goal(
            "g1",
            "Learn async Python",
            {"python": 1.0, "asyncio": 1.0},
            kind_filter=["course"],
        )
    ]
    return items, goals


# ---------------------------------------------------------------------------
# Model / weights
# ---------------------------------------------------------------------------


def test_shelf_shape():
    assert SHELF["name"] == "recommender"
    assert SHELF["summary"] and SHELF["items"]


def test_parse_topics():
    assert parse_topics("python:1.0,asyncio:0.6,web") == {
        "python": 1.0,
        "asyncio": 0.6,
        "web": 1.0,
    }
    with pytest.raises(ValueError):
        parse_topics("")
    with pytest.raises(ValueError):
        parse_topics("python:2.0")
    with pytest.raises(ValueError):
        parse_topics("python:abc")


def test_item_validation():
    with pytest.raises(ValueError):
        Item(id="x", title=" ", kind="course", topics={"a": 1.0})
    with pytest.raises(ValueError):
        Item(id="x", title="t", kind="course", topics={})
    with pytest.raises(ValueError):
        Item(id="x", title="t", kind="course", topics={"a": -0.1})


def test_check_rating_bounds():
    assert check_rating("4") == 4.0
    with pytest.raises(ValueError):
        check_rating(0)
    with pytest.raises(ValueError):
        check_rating(6)


def test_normalize_and_parse_weights():
    assert normalize_weights({"goal": 1, "content": 1, "quality": 0, "recency": 0}) == {
        "goal": 0.5,
        "content": 0.5,
        "quality": 0.0,
        "recency": 0.0,
    }
    assert parse_weights("goal=0.5,content=0.5,quality=0,recency=0") == {
        "goal": 0.5,
        "content": 0.5,
        "quality": 0.0,
        "recency": 0.0,
    }
    for bad in (
        "goal=1,vibes=1",
        "goal=-1,content=1,quality=0,recency=0",
        "goal=0,content=0,quality=0,recency=0",
        "garbage",
    ):
        with pytest.raises(ValueError):
            parse_weights(bad)


# ---------------------------------------------------------------------------
# Signal math
# ---------------------------------------------------------------------------


def test_cosine_known_values():
    assert cosine({"a": 1.0}, {"a": 1.0}) == pytest.approx(1.0)
    assert cosine({"a": 1.0}, {"b": 1.0}) == pytest.approx(0.0)
    assert cosine({}, {"a": 1.0}) == 0.0
    # orthogonal-ish: (1,0) vs (1,1) -> 1/sqrt(2)
    assert cosine({"x": 1.0}, {"x": 1.0, "y": 1.0}) == pytest.approx(1 / math.sqrt(2))


def test_goal_alignment_picks_best_and_respects_kind_filter():
    items, goals = _corpus()
    score, which = goal_alignment(items[0], goals)
    assert which == "g1" and score > 0.9
    rust_score, _ = goal_alignment(items[2], goals)
    assert rust_score == 0.0  # book filtered out by kind_filter
    # without kind filter the rust book still scores ~0 (no topic overlap)
    g2 = _goal("g2", "systems", {"rust": 1.0, "systems": 1.0})
    score2, _ = goal_alignment(items[2], [g2])
    assert score2 > 0.9


def test_content_fit_zero_until_rated():
    items, _ = _corpus()
    assert liked_centroid(items, {}) == {}
    assert content_fit(items[0], {}) == 0.0
    centroid = liked_centroid(items, {"py-async": [5.0]})
    assert centroid["python"] == pytest.approx(1.0)
    # a near-duplicate item fits the liked centroid well
    assert content_fit(items[3], centroid) > 0.9
    assert content_fit(items[2], centroid) == pytest.approx(0.0)


def test_quality_from_explicit_ratings_only():
    items, _ = _corpus()
    assert quality_score(items[0], {}) == 0.0
    assert quality_score(items[0], {"py-async": [4.0, 5.0]}) == pytest.approx(0.9)


def test_recency_decay():
    items, _ = _corpus()
    fresh = _item("f", "t", "k", {"a": 1.0}, days_old=0)
    old = _item("o", "t", "k", {"a": 1.0}, days_old=90)
    assert recency_score(fresh, NOW) == pytest.approx(1.0)
    assert recency_score(old, NOW) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        recency_score(fresh, NOW, half_life_days=0)


# ---------------------------------------------------------------------------
# recommend(): ranking, explanations, honesty notes
# ---------------------------------------------------------------------------


def test_recommend_goal_drives_ranking():
    items, goals = _corpus()
    recs = recommend(items, goals, {}, now=NOW)
    assert [r.item.id for r in recs[:2]] == ["py-async-2", "py-async"]
    top = recs[0]
    assert top.best_goal == "g1"
    # contributions sum to the total, exactly as explain() reports
    assert top.total == pytest.approx(sum(top.contributions.values()))
    text = explain(top, DEFAULT_WEIGHTS)
    assert "goal" in text and "contribution" in text


def test_recommend_cold_start_is_honest():
    items, _ = _corpus()
    recs = recommend(items, [], {}, now=NOW)
    assert recs  # recency alone still ranks
    assert any("no active goals" in n for n in recs[0].notes)
    assert any("no liked items yet" in n for n in recs[0].notes)
    assert recs[0].contributions["goal"] == 0.0
    assert recs[0].contributions["content"] == 0.0


def test_ratings_enable_content_and_quality():
    items, goals = _corpus()
    ratings = {"py-async": [5.0], "py-web": [2.0]}
    recs = recommend(items, goals, ratings, now=NOW)
    by_id = {r.item.id: r for r in recs}
    # liked centroid is asyncio-heavy: the other asyncio course rises
    assert (
        by_id["py-async-2"].contributions["content"]
        > by_id["py-web"].contributions["content"]
    )
    # quality reflects the explicit 2.0 rating on py-web
    assert by_id["py-web"].contributions["quality"] == pytest.approx(0.20 * 0.4)
    assert "unrated" not in " ".join(by_id["py-async"].notes)


def test_weight_change_flips_order():
    items, goals = _corpus()
    # rust-book: zero goal alignment, but make it high quality + fresh
    ratings = {"rust-book": [5.0]}
    goal_heavy = recommend(
        items,
        goals,
        ratings,
        weights={"goal": 1.0, "content": 0.0, "quality": 0.0, "recency": 0.0},
        now=NOW,
    )
    quality_heavy = recommend(
        items,
        goals,
        ratings,
        weights={"goal": 0.0, "content": 0.0, "quality": 1.0, "recency": 0.0},
        now=NOW,
    )
    assert goal_heavy[0].item.id.startswith("py-async")
    assert quality_heavy[0].item.id == "rust-book"


def test_exclude_ids_and_top_k():
    items, goals = _corpus()
    recs = recommend(
        items, goals, {}, exclude_ids=["py-async", "py-async-2"], top_k=1, now=NOW
    )
    assert len(recs) == 1 and recs[0].item.id == "py-web"


def test_active_goal_subset():
    items, _ = _corpus()
    g1 = _goal("g1", "async", {"python": 1.0, "asyncio": 1.0})
    g2 = _goal("g2", "rust", {"rust": 1.0})
    recs = recommend(items, [g1, g2], {}, active_goal_ids={"g2"}, now=NOW)
    assert recs[0].item.id == "rust-book"
    assert recs[0].best_goal == "g2"


# ---------------------------------------------------------------------------
# MMR diversity
# ---------------------------------------------------------------------------


def test_mmr_lambda_one_is_pure_relevance():
    items, goals = _corpus()
    recs = recommend(items, goals, {}, mmr_lambda=1.0, now=NOW)
    totals = [r.total for r in recs]
    assert totals == sorted(totals, reverse=True)


def test_mmr_diversity_spreads_topics():
    items = [
        _item("a1", "A1", "course", {"python": 1.0, "asyncio": 1.0}),
        _item("a2", "A2", "course", {"python": 1.0, "asyncio": 0.95}),
        _item("b1", "B1", "course", {"python": 1.0, "typing": 1.0}),
    ]
    goals = [_goal("g", "python", {"python": 1.0})]
    pure = recommend(items, goals, {}, mmr_lambda=1.0, top_k=2, now=NOW)
    diverse = recommend(items, goals, {}, mmr_lambda=0.0, top_k=2, now=NOW)
    # a2 is the most python-concentrated, so it leads pure relevance;
    # a1/a2 are near-dupes, so full diversity swaps a2 out for b1.
    assert [r.item.id for r in pure] == ["a2", "a1"]
    assert [r.item.id for r in diverse] == ["a1", "b1"]  # spread wins
    with pytest.raises(ValueError):
        mmr_order([], 1.5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero():
    from levi.recommender.__main__ import main

    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_cli_end_to_end(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    from levi.recommender.__main__ import main

    assert (
        main(
            [
                "add-item",
                "--title",
                "Asyncio deep dive",
                "--kind",
                "course",
                "--topics",
                "python:1.0,asyncio:0.9",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "add-item",
                "--title",
                "Rust systems",
                "--kind",
                "book",
                "--topics",
                "rust:1.0",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "add-goal",
                "--title",
                "Learn async Python",
                "--topics",
                "python:1.0,asyncio:1.0",
                "--kind-filter",
                "course",
            ]
        )
        == 0
    )
    assert main(["rate", "asyncio-deep-dive", "5"]) == 0
    assert main(["recommend", "--explain"]) == 0
    out = capsys.readouterr().out
    assert "Asyncio deep dive" in out
    assert "contribution" in out
    # diverse flag + weights round-trip
    assert main(["recommend", "--diverse", "0.5", "--top", "1"]) == 0
    assert main(["weights", "set", "goal=0.6,content=0.4,quality=0,recency=0"]) == 0
    assert main(["weights", "show"]) == 0
    assert "goal=0.60" in capsys.readouterr().out
    assert main(["list", "items"]) == 0
    assert "asyncio-deep-dive" in capsys.readouterr().out
    # bad inputs rejected, not silently accepted
    assert main(["rate", "asyncio-deep-dive", "9"]) == 2
    assert main(["rate", "nope", "3"]) == 1
    assert (
        main(["add-item", "--title", "Bad", "--kind", "course", "--topics", "python:9"])
        == 2
    )


def test_cli_recommend_empty_corpus(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    from levi.recommender.__main__ import main

    assert main(["recommend"]) == 1
    assert "empty" in capsys.readouterr().out


def test_cli_export(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    from levi.recommender.__main__ import main

    assert main(["add-item", "--title", "T", "--kind", "k", "--topics", "a:1.0"]) == 0
    out = tmp_path / "taste.json"
    assert main(["export", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["items"] and payload["weights"]
