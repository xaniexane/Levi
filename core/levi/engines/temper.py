"""Temper engine — honest confidence over a claim's evidence.

The keeper's law says raw truth, the whole road: a claim is not "true"
because it feels right, it is *settled*, *leaning*, *provisional*, or
*unfounded* — and the engine must say which, with the arithmetic shown.

Inputs
------
``claim``: the statement under scrutiny (str, required)
``corroborations``: count of independent supporting sources (int, >= 0)
``contradictions``: count of sources that deny it (int, >= 0)
``source_count``: total sources consulted (int, >= 0)
``days_old``: age of the newest evidence, in days (float, >= 0)
``base_confidence``: prior confidence before this evidence (0.0-1.0, default 0.5)

The verdict
-----------
- ``settled``     — net support >= 5: the road is visible, say it plainly
- ``leaning``     — net support >= 2: direction with honest doubt
- ``provisional`` — net support > -2: say it, but flag it as provisional
- ``unfounded``   — otherwise: do not state it as fact

Contradictions weigh double (one honest denial outweighs one echo), and
confidence decays with a 180-day half-life on the evidence age. Stale
proof is not proof. The engine judges; the keeper decides.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_CONTRA_WEIGHT = 2.0  # one contradiction costs two corroborations
_HALF_LIFE_DAYS = 180.0


def _nonneg_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineInputError(f"temper: '{name}' must be a number")
    if value < 0:
        raise EngineInputError(f"temper: '{name}' must be >= 0")
    return float(value)


def _temper(inputs: Dict[str, Any]) -> EngineResult:
    claim = inputs.get("claim")
    if not claim or not isinstance(claim, str):
        raise EngineInputError("temper: 'claim' must be a non-empty string")
    corroborations = _nonneg_number(inputs.get("corroborations", 0), "corroborations")
    contradictions = _nonneg_number(inputs.get("contradictions", 0), "contradictions")
    source_count = _nonneg_number(inputs.get("source_count", 0), "source_count")
    days_old = _nonneg_number(inputs.get("days_old", 0), "days_old")
    base = inputs.get("base_confidence", 0.5)
    if isinstance(base, bool) or not isinstance(base, (int, float)):
        raise EngineInputError("temper: 'base_confidence' must be a number")
    if not 0.0 <= float(base) <= 1.0:
        raise EngineInputError("temper: 'base_confidence' must be 0.0-1.0")

    if corroborations + contradictions > source_count:
        raise EngineInputError(
            "temper: corroborations + contradictions cannot exceed source_count "
            f"({corroborations:g} + {contradictions:g} > {source_count:g})"
        )

    trace: List[str] = [f"claim: {claim}"]
    net = corroborations - _CONTRA_WEIGHT * contradictions
    trace.append(
        f"corroborations {corroborations:g}, contradictions {contradictions:g} "
        f"(x{_CONTRA_WEIGHT:g}) -> net support {net:+g}"
    )

    if net >= 5:
        verdict_word = "settled"
    elif net >= 2:
        verdict_word = "leaning"
    elif net > -2:
        verdict_word = "provisional"
    else:
        verdict_word = "unfounded"
    trace.append(f"net {net:+g} -> '{verdict_word}'")

    # Logistic over net support, then stale-evidence decay.
    strength = 1.0 / (1.0 + math.exp(-net / 2.0))
    decay = 0.5 ** (days_old / _HALF_LIFE_DAYS)
    confidence = round(float(base) * 0.3 + 0.7 * strength * decay, 3)
    trace.append(
        f"strength {strength:.3f} x decay {decay:.3f} (age {days_old:g}d) "
        f"+ prior {float(base):.2f} -> confidence {confidence:.3f}"
    )

    verdict: Dict[str, Any] = {
        "claim": claim,
        "standing": verdict_word,
        "net_support": net,
        "corroborations": corroborations,
        "contradictions": contradictions,
        "source_count": source_count,
        "days_old": days_old,
        "confidence": confidence,
    }
    return EngineResult(
        engine_id="temper", verdict=verdict, confidence=confidence, trace=trace
    )


TEMPER_ENGINE = Engine(
    id="temper",
    name="Temper",
    description=(
        "Honest confidence over a claim's evidence: settled / leaning / "
        "provisional / unfounded, with contradiction-weighted net support "
        "and age-decayed confidence."
    ),
    required=("claim",),
    schema={
        "claim": "statement under scrutiny (str)",
        "corroborations": "independent supporting sources (default 0)",
        "contradictions": "denying sources, weighted double (default 0)",
        "source_count": "total sources consulted (default 0)",
        "days_old": "age of newest evidence in days (default 0)",
        "base_confidence": "prior 0.0-1.0 (default 0.5)",
    },
    risk="info",
    handler=_temper,
)

registry.register(TEMPER_ENGINE)
