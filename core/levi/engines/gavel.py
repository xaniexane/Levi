"""Gavel engine — adjudicated rulings over competing claims, LEVI-native.

Two or more claims collide; one ruling must come out. Gavel is the
deterministic adjudicator: every claim brings evidence (0..1), a source
weight, and a contradiction flag. The engine scores the claims, penalizes
contradicted ones, and rules against a named burden of proof:

- ``preponderance`` (default): the prevailing claim must hold strictly
  more than 1/2 of the total penalized score
- ``clear``: strictly more than 2/3
- ``beyond_doubt``: strictly more than 4/5

Rulings:

- ``upheld`` — the incumbent (or the leading claim, when no incumbent is
  named) meets the burden
- ``overturned`` — a challenger meets the burden AND outscores the incumbent
- ``split`` — nobody meets the burden, but the leader clears the remand
  floor: the evidence must grow before anyone rules
- ``remanded`` — every claim scores below the remand floor: back for more
  evidence, no ruling rendered

Laws (invariants):

- L1 determinism — identical inputs always produce the identical verdict.
- L2 deny-closed — malformed input is refused with a named error, never
  coerced or guessed.
- L3 no fabrication — ``split`` and ``remanded`` never name a prevailing
  claim; the engine rules only when the burden is met.
- L4 tie determinism — ties break by penalized score, then raw evidence,
  then input order. Never a coin flip.
- L5 contradiction penalty — a contradicted claim always scores at most
  its uncontradicted twin.
- L6 monotonicity — raising a claim's evidence (all else equal) never
  lowers its rank.

Inputs::

    {
        "claims": [
            {"claim": "ship", "evidence": 0.8, "weight": 1.0,
             "contradicted": False},
            {"claim": "hold", "evidence": 0.6, "contradicted": True},
        ],
        "incumbent": "hold",        # optional: the ruling under challenge
        "standard": "preponderance", # optional: preponderance | clear |
                                    #           beyond_doubt
        "remand_floor": 0.25,       # optional: float in [0, 1)
    }

Verdict::

    {
        "ruling": "upheld" | "overturned" | "split" | "remanded",
        "prevailing": "<claim>" | None,
        "scores": {"ship": 0.8, "hold": 0.3},
        "shares": {"ship": 0.727, "hold": 0.273},
        "ranking": ["ship", "hold"],
        "standard": "preponderance",
        "burden": 0.5,
        "reason": "...",
    }

The engine computes; it never acts, messages, or spends.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from levi.engines.base import Engine, EngineResult, registry

ENGINE_ID = "gavel"

_STANDARDS: Dict[str, float] = {
    "preponderance": 0.5,
    "clear": 2.0 / 3.0,
    "beyond_doubt": 0.8,
}

_CONTRADICTION_PENALTY = 0.5
_GENESIS_REASON = "no evidence on the table"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean_claims(raw: Any) -> List[Dict[str, Any]]:
    """Validate and normalize the claims list (deny-closed)."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("claims must be a non-empty list of claim dicts")
    seen = set()
    cleaned: List[Dict[str, Any]] = []
    for index, item in enumerate(raw):
        where = f"claims[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be a dict")
        name = item.get("claim")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{where}.claim must be a non-empty string")
        if name in seen:
            raise ValueError(f"duplicate claim name {name!r}")
        seen.add(name)
        evidence = item.get("evidence")
        if not _is_number(evidence) or not 0.0 <= evidence <= 1.0:
            raise ValueError(f"{where}.evidence must be a number in [0, 1]")
        weight = item.get("weight", 1.0)
        if not _is_number(weight) or weight <= 0:
            raise ValueError(f"{where}.weight must be a positive number")
        contradicted = item.get("contradicted", False)
        if not isinstance(contradicted, bool):
            raise ValueError(f"{where}.contradicted must be a bool")
        cleaned.append(
            {
                "claim": name,
                "evidence": float(evidence),
                "weight": float(weight),
                "contradicted": contradicted,
                "order": index,
            }
        )
    return cleaned


def _score(entry: Dict[str, Any]) -> float:
    penalized = entry["evidence"] * entry["weight"]
    if entry["contradicted"]:
        penalized *= _CONTRADICTION_PENALTY
    return penalized


def _rank(
    cleaned: List[Dict[str, Any]], scores: Dict[str, float]
) -> List[Tuple[str, float]]:
    """Deterministic ranking: score, then evidence, then input order."""
    evidence_of = {c["claim"]: c["evidence"] for c in cleaned}
    order_of = {c["claim"]: c["order"] for c in cleaned}
    return sorted(
        scores.items(),
        key=lambda kv: (-kv[1], -evidence_of[kv[0]], order_of[kv[0]]),
    )


def _handler(inputs: Dict[str, Any]) -> EngineResult:
    trace: List[str] = []
    cleaned = _clean_claims(inputs["claims"])

    standard = inputs.get("standard", "preponderance")
    if standard not in _STANDARDS:
        raise ValueError(
            f"standard must be one of {sorted(_STANDARDS)}, got {standard!r}"
        )
    burden = _STANDARDS[standard]

    remand_floor = inputs.get("remand_floor", 0.25)
    if not _is_number(remand_floor) or not 0.0 <= remand_floor < 1.0:
        raise ValueError("remand_floor must be a number in [0, 1)")

    incumbent = inputs.get("incumbent")
    names = {c["claim"] for c in cleaned}
    if incumbent is not None:
        if not isinstance(incumbent, str) or incumbent not in names:
            raise ValueError(
                f"incumbent must name one of the claims, got {incumbent!r}"
            )

    scores: Dict[str, float] = {}
    for entry in cleaned:
        penalized = _score(entry)
        scores[entry["claim"]] = penalized
        bits = f"evidence {entry['evidence']:.3g} x weight {entry['weight']:.3g}"
        if entry["contradicted"]:
            bits += f" x contradiction penalty {_CONTRADICTION_PENALTY}"
        trace.append(f"claim {entry['claim']!r}: {bits} = {penalized:.3g}")

    total = sum(scores.values())
    ranked = _rank(cleaned, scores)
    leader, leader_score = ranked[0]
    shares = {
        name: (score / total if total > 0 else 0.0) for name, score in scores.items()
    }
    trace.append(
        f"burden {standard!r} requires share > {burden:.3g}; "
        f"total penalized score {total:.3g}"
    )

    verdict: Dict[str, Any]
    if total <= 0:
        verdict = {
            "ruling": "remanded",
            "prevailing": None,
            "reason": _GENESIS_REASON,
        }
        trace.append("ruling: remanded — no evidence on the table")
        confidence = 0.0
    elif leader_score < remand_floor:
        verdict = {
            "ruling": "remanded",
            "prevailing": None,
            "reason": (
                f"strongest claim {leader!r} scores {leader_score:.3g}, "
                f"below remand floor {remand_floor:.3g}"
            ),
        }
        trace.append(f"ruling: remanded — {verdict['reason']}")
        confidence = 0.0
    elif incumbent is not None:
        inc_share = shares[incumbent]
        trace.append(f"incumbent {incumbent!r} holds share {inc_share:.3g}")
        if inc_share > burden:
            verdict = {
                "ruling": "upheld",
                "prevailing": incumbent,
                "reason": (
                    f"{incumbent!r} meets the {standard} burden "
                    f"({inc_share:.3g} > {burden:.3g})"
                ),
            }
            trace.append(f"ruling: upheld — {verdict['reason']}")
            confidence = min(1.0, inc_share)
        else:
            challengers = [n for n, _ in ranked if n != incumbent]
            top_challenger = challengers[0]
            chal_share = shares[top_challenger]
            if chal_share > burden and scores[top_challenger] > scores[incumbent]:
                verdict = {
                    "ruling": "overturned",
                    "prevailing": top_challenger,
                    "reason": (
                        f"{top_challenger!r} meets the {standard} burden "
                        f"({chal_share:.3g} > {burden:.3g}) and outscores "
                        f"incumbent {incumbent!r}"
                    ),
                }
                trace.append(f"ruling: overturned — {verdict['reason']}")
                confidence = min(1.0, chal_share)
            else:
                verdict = {
                    "ruling": "split",
                    "prevailing": None,
                    "reason": (
                        f"no claim meets the {standard} burden; evidence "
                        "must grow before anyone rules"
                    ),
                }
                trace.append(f"ruling: split — {verdict['reason']}")
                confidence = shares[leader]
    else:
        leader_share = shares[leader]
        if leader_share > burden:
            verdict = {
                "ruling": "upheld",
                "prevailing": leader,
                "reason": (
                    f"{leader!r} meets the {standard} burden "
                    f"({leader_share:.3g} > {burden:.3g})"
                ),
            }
            trace.append(f"ruling: upheld — {verdict['reason']}")
            confidence = min(1.0, leader_share)
        else:
            verdict = {
                "ruling": "split",
                "prevailing": None,
                "reason": (
                    f"no claim meets the {standard} burden; evidence "
                    "must grow before anyone rules"
                ),
            }
            trace.append(f"ruling: split — {verdict['reason']}")
            confidence = shares[leader]

    verdict.update(
        {
            "scores": dict(scores),
            "shares": dict(shares),
            "ranking": [name for name, _ in ranked],
            "standard": standard,
            "burden": burden,
        }
    )
    return EngineResult(
        engine_id=ENGINE_ID,
        verdict=verdict,
        confidence=confidence,
        trace=trace,
    )


registry.register(
    Engine(
        id=ENGINE_ID,
        name="Gavel",
        description=(
            "Adjudicated rulings over competing claims: evidence-weighted "
            "scoring with a contradiction penalty, a named burden of proof, "
            "and upheld / overturned / split / remanded rulings. Deterministic; "
            "never fabricates a prevailing claim."
        ),
        version="1.0.0",
        required=("claims",),
        schema={
            "claims": "list of {claim, evidence 0..1, weight?, contradicted?}",
            "incumbent": "optional claim name under challenge",
            "standard": "preponderance | clear | beyond_doubt",
            "remand_floor": "float in [0, 1), default 0.25",
        },
        risk="info",
        handler=_handler,
    )
)
