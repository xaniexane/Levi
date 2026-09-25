"""Quorum engine — weighted majority verdicts, LEVI-native.

The twin pair (left = sequence/logic, right = pattern/intuition) must
converge to ONE action; this engine is the deterministic machine that
runs the convergence: named voters cast weighted votes for named
choices, abstentions count toward participation but not toward any
choice, and the engine declares a winner only when BOTH gates hold:

1. **quorum gate** — total participating weight reaches ``quorum_weight``
   (default 1.0). Below it the verdict is "no_quorum", never a guess.
2. **majority gate** — the leading choice holds strictly more than
   ``threshold`` of the *cast* (non-abstain) weight (default 0.5).
   A tie at the top is a verdict of "tie", not a coin flip.

Same inputs → same verdict, every time. The engine computes; it never
acts, messages, or spends.

Inputs::

    {
        "votes": [
            {"voter": "left", "choice": "ship", "weight": 1.0},
            {"voter": "right", "choice": "hold", "weight": 1.0},
        ],
        "threshold": 0.5,       # optional, 0 < threshold < 1
        "quorum_weight": 1.0,   # optional, >= 0
    }

Verdict::

    {
        "outcome": "winner" | "tie" | "no_quorum" | "no_votes",
        "winner": "<choice>" | None,
        "totals": {"ship": 1.0, "hold": 1.0},
        "participation": 2.0,
        "quorum_met": True,
        "margin": 0.0,
    }
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineResult, registry

ENGINE_ID = "quorum"

_ABSTAIN = "abstain"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_votes(votes: Any) -> List[Dict[str, Any]]:
    if not isinstance(votes, list) or not votes:
        raise ValueError("votes must be a non-empty list of vote dicts")
    cleaned: List[Dict[str, Any]] = []
    for index, vote in enumerate(votes):
        where = f"votes[{index}]"
        if not isinstance(vote, dict):
            raise ValueError(f"{where} must be a dict, got {type(vote).__name__}")
        voter = vote.get("voter")
        choice = vote.get("choice")
        if not isinstance(voter, str) or not voter.strip():
            raise ValueError(f"{where} needs a non-empty string 'voter'")
        if not isinstance(choice, str) or not choice.strip():
            raise ValueError(f"{where} needs a non-empty string 'choice'")
        weight = vote.get("weight", 1.0)
        if not _is_number(weight) or weight < 0:
            raise ValueError(
                f"{where} weight must be a non-negative number, got {weight!r}"
            )
        cleaned.append(
            {
                "voter": voter.strip(),
                "choice": choice.strip(),
                "weight": float(weight),
            }
        )
    return cleaned


def _handler(inputs: Dict[str, Any]) -> EngineResult:
    trace: List[str] = []
    try:
        votes = _validate_votes(inputs.get("votes"))
    except ValueError as exc:
        from levi.engines.base import EngineInputError

        raise EngineInputError(f"engine 'quorum': {exc}") from None

    threshold = inputs.get("threshold", 0.5)
    quorum_weight = inputs.get("quorum_weight", 1.0)
    from levi.engines.base import EngineInputError

    if not _is_number(threshold) or not 0.0 < threshold < 1.0:
        raise EngineInputError(
            f"engine 'quorum': threshold must be in (0, 1), got {threshold!r}"
        )
    if not _is_number(quorum_weight) or quorum_weight < 0:
        raise EngineInputError(
            "engine 'quorum': quorum_weight must be a non-negative "
            f"number, got {quorum_weight!r}"
        )

    totals: Dict[str, float] = {}
    participation = 0.0
    order: List[str] = []  # first-seen order: deterministic tie reporting
    for vote in votes:
        participation += vote["weight"]
        choice = vote["choice"]
        if choice.lower() == _ABSTAIN:
            trace.append(
                f"{vote['voter']} abstained (weight {vote['weight']:.3g}) — "
                "counts toward participation, not toward any choice"
            )
            continue
        if choice not in totals:
            totals[choice] = 0.0
            order.append(choice)
        totals[choice] += vote["weight"]

    cast = sum(totals.values())
    trace.append(
        f"participation {participation:.3g} (quorum gate: {quorum_weight:.3g}), "
        f"cast {cast:.3g} across {len(totals)} choices"
    )

    if not totals:
        verdict = {
            "outcome": "no_votes",
            "winner": None,
            "totals": {},
            "participation": participation,
            "quorum_met": participation >= quorum_weight,
            "margin": 0.0,
        }
        trace.append("no cast votes — verdict is no_votes")
        return EngineResult(
            engine_id=ENGINE_ID,
            verdict=verdict,
            confidence=0.0,
            trace=trace,
        )

    if participation < quorum_weight:
        ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        trace.append(
            f"quorum not met ({participation:.3g} < {quorum_weight:.3g}) — "
            "no winner declared even though votes were cast"
        )
        return EngineResult(
            engine_id=ENGINE_ID,
            verdict={
                "outcome": "no_quorum",
                "winner": None,
                "totals": dict(ranked),
                "participation": participation,
                "quorum_met": False,
                "margin": 0.0,
            },
            confidence=0.0,
            trace=trace,
        )

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    leader, leader_weight = ranked[0]
    runner_weight = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = leader_weight - runner_weight
    required = threshold * cast

    if leader_weight <= required:
        trace.append(
            f"leader {leader!r} holds {leader_weight:.3g} but needs > "
            f"{required:.3g} (threshold {threshold:.3g} of cast {cast:.3g})"
        )
        if len(ranked) > 1 and margin == 0.0:
            trace.append("top choices tied — verdict is tie, never a coin flip")
        return EngineResult(
            engine_id=ENGINE_ID,
            verdict={
                "outcome": "tie" if margin == 0.0 else "no_winner",
                "winner": None,
                "totals": dict(ranked),
                "participation": participation,
                "quorum_met": True,
                "margin": margin,
            },
            confidence=0.0,
            trace=trace,
        )

    confidence = min(1.0, (margin / cast) if cast else 0.0) if cast else 0.0
    # A unanimous, quorum-clearing verdict earns full confidence.
    if margin == cast:
        confidence = 1.0
    trace.append(
        f"{leader!r} wins: {leader_weight:.3g} > {required:.3g} "
        f"(margin {margin:.3g} over runner-up)"
    )
    return EngineResult(
        engine_id=ENGINE_ID,
        verdict={
            "outcome": "winner",
            "winner": leader,
            "totals": dict(ranked),
            "participation": participation,
            "quorum_met": True,
            "margin": margin,
        },
        confidence=confidence,
        trace=trace,
    )


registry.register(
    Engine(
        id=ENGINE_ID,
        name="Quorum",
        description=(
            "Weighted majority verdicts over named votes: quorum "
            "participation gate, strict threshold of cast weight, "
            "deterministic ties. Twin-pair convergence made auditable."
        ),
        version="1.0.0",
        required=("votes",),
        schema={
            "votes": "list of {voter, choice, weight?} dicts",
            "threshold": "float in (0, 1), default 0.5",
            "quorum_weight": "non-negative float, default 1.0",
        },
        risk="info",
        handler=_handler,
    )
)
