"""oracle form tests: long-term goal weighting.

Proving bar: strategies are fail-closed (bad weights rejected), ranking
is deterministic arithmetic, unknown criteria / bad ratings are data
(rejected with reasons, never silently dropped), dry runs commit nothing,
and the honesty note is always present.
"""

import pytest

from levi.oracle import FORM_NAME, Criterion, Strategy, weight_goals


@pytest.fixture()
def strategy():
    return Strategy(
        name="founder",
        criteria=[
            Criterion("impact", 0.5, "moves the mission"),
            Criterion("revenue", 0.3),
            Criterion("joy", 0.2),
        ],
    )


def test_strategy_fail_closed():
    with pytest.raises(ValueError):
        Strategy(name="", criteria=[Criterion("x", 1.0)])
    with pytest.raises(ValueError):
        Strategy(name="s", criteria=[])
    with pytest.raises(ValueError):
        Strategy(name="s", criteria=[Criterion("x", -1.0)])
    with pytest.raises(ValueError):
        Strategy(name="s", criteria=[Criterion("x", 1.0), Criterion("x", 2.0)])
    with pytest.raises(ValueError):
        Strategy(name="s", criteria=[Criterion("x", 0.0), Criterion("y", 0.0)])


def test_weight_goals_deterministic_ranking(strategy):
    goals = [
        {
            "id": "a",
            "name": "A",
            "ratings": {"impact": 1.0, "revenue": 0.0, "joy": 0.0},
        },
        {
            "id": "b",
            "name": "B",
            "ratings": {"impact": 0.0, "revenue": 1.0, "joy": 1.0},
        },
    ]
    r1 = weight_goals(strategy, goals)
    r2 = weight_goals(strategy, list(reversed(goals)))
    assert r1["form"] == FORM_NAME
    assert r1["status"] == "ranked"
    # a: 0.5, b: 0.5 -> tie broken by id, deterministic
    assert [g["id"] for g in r1["ranking"]] == [g["id"] for g in r2["ranking"]]
    assert "not predictions" in r1["honest_note"]


def test_unknown_criteria_and_bad_ratings_rejected_as_data(strategy):
    goals = [
        {
            "id": "ok",
            "name": "OK",
            "ratings": {"impact": 0.5, "revenue": 0.5, "joy": 0.5},
        },
        {
            "id": "weird",
            "name": "W",
            "ratings": {"impact": 0.5, "revenue": 0.5, "joy": 0.5, "vibes": 1.0},
        },
        {
            "id": "bad",
            "name": "B",
            "ratings": {"impact": 2.0, "revenue": 0.5, "joy": 0.5},
        },
        "not-a-mapping",
        {"id": "noratings", "name": "N"},
    ]
    r = weight_goals(strategy, goals)
    assert [g["id"] for g in r["ranking"]] == ["ok"]
    assert len(r["rejected"]) == 4
    assert all(x["reason"] for x in r["rejected"])


def test_non_sequence_goals_rejected(strategy):
    r = weight_goals(strategy, "a string is not goals")
    assert r["status"] == "rejected"


def test_dry_run_commits_nothing(strategy):
    goals = [
        {"id": "a", "name": "A", "ratings": {"impact": 1.0, "revenue": 1.0, "joy": 1.0}}
    ]
    r = weight_goals(strategy, goals, dry_run=True)
    assert r["status"] == "dry-run"
    assert r["dry_run"] is True
    assert strategy.last_ranking is None  # purity: nothing committed
    r2 = weight_goals(strategy, goals)
    assert r2["status"] == "ranked"
    assert strategy.last_ranking is not None


def test_score_is_weighted_arithmetic(strategy):
    # impact .5*1 + revenue .3*0 + joy .2*0 over total 1.0 -> 0.5
    assert strategy.score({"impact": 1.0, "revenue": 0.0, "joy": 0.0}) == 0.5
    with pytest.raises(ValueError):
        strategy.score({"impact": 0.5})  # missing criteria
