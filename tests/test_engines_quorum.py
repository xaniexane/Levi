"""Tests for the quorum engine (weighted majority verdicts)."""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def run(**kwargs):
    return registry.run("quorum", kwargs)


def test_quorum_registered():
    assert registry.get("quorum").name == "Quorum"


def test_clear_winner():
    result = run(
        votes=[
            {"voter": "left", "choice": "ship"},
            {"voter": "right", "choice": "ship"},
            {"voter": "keeper", "choice": "hold"},
        ]
    )
    assert result.verdict["outcome"] == "winner"
    assert result.verdict["winner"] == "ship"
    assert result.verdict["totals"]["ship"] == 2.0
    assert result.verdict["quorum_met"] is True
    assert result.confidence > 0.0


def test_tie_is_verdict_not_coin_flip():
    first = run(
        votes=[
            {"voter": "left", "choice": "ship"},
            {"voter": "right", "choice": "hold"},
        ]
    )
    second = run(
        votes=[
            {"voter": "left", "choice": "ship"},
            {"voter": "right", "choice": "hold"},
        ]
    )
    assert first.verdict["outcome"] == "tie"
    assert first.verdict["winner"] is None
    assert first.verdict["margin"] == 0.0
    assert first.confidence == 0.0
    # Deterministic: identical inputs, identical verdict.
    assert first.verdict == second.verdict


def test_no_quorum_declares_nothing():
    result = run(
        votes=[{"voter": "left", "choice": "ship"}],
        quorum_weight=2.0,
    )
    assert result.verdict["outcome"] == "no_quorum"
    assert result.verdict["winner"] is None
    assert result.verdict["quorum_met"] is False
    assert result.confidence == 0.0


def test_abstentions_count_for_quorum_not_for_choices():
    result = run(
        votes=[
            {"voter": "left", "choice": "ship"},
            {"voter": "right", "choice": "abstain"},
        ],
        quorum_weight=2.0,
    )
    assert result.verdict["participation"] == 2.0
    assert result.verdict["quorum_met"] is True
    assert result.verdict["outcome"] == "winner"
    assert result.verdict["winner"] == "ship"
    assert result.verdict["totals"] == {"ship": 1.0}


def test_all_abstain_is_no_votes():
    result = run(
        votes=[
            {"voter": "left", "choice": "abstain"},
            {"voter": "right", "choice": "ABSTAIN"},
        ]
    )
    assert result.verdict["outcome"] == "no_votes"
    assert result.verdict["winner"] is None


def test_weights_and_custom_threshold():
    # Two-thirds of cast weight required.
    result = run(
        votes=[
            {"voter": "a", "choice": "ship", "weight": 2.0},
            {"voter": "b", "choice": "hold", "weight": 1.0},
        ],
        threshold=0.6,
    )
    assert result.verdict["outcome"] == "winner"
    assert result.verdict["winner"] == "ship"

    # Just under the threshold: no winner, even without a tie.
    result = run(
        votes=[
            {"voter": "a", "choice": "ship", "weight": 1.0},
            {"voter": "b", "choice": "hold", "weight": 1.0},
            {"voter": "c", "choice": "wait", "weight": 1.0},
        ],
        threshold=0.5,
    )
    assert result.verdict["outcome"] in ("tie", "no_winner")
    assert result.verdict["winner"] is None


def test_malformed_input_refused():
    with pytest.raises(EngineInputError):
        run()
    with pytest.raises(EngineInputError):
        run(votes=[])
    with pytest.raises(EngineInputError):
        run(votes=[{"voter": "left"}])
    with pytest.raises(EngineInputError):
        run(votes=[{"voter": "left", "choice": "ship", "weight": -1}])
    with pytest.raises(EngineInputError):
        run(votes=[{"voter": "left", "choice": "ship"}], threshold=1.0)
    with pytest.raises(EngineInputError):
        run(votes=[{"voter": "left", "choice": "ship"}], quorum_weight=-1)
