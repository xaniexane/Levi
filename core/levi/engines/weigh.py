"""Weigh engine — two-sided judgment with calibrated confidence.

The weighing mind's native tool: given a proposition, evidence for and
against (each with a weight), it produces a lean (for / against /
balanced), a calibrated confidence, and the decisive factors. Weights
are evidence strengths, not votes — one strong reason can outweigh
three weak ones, and the trace says exactly which.

Inputs
------
``proposition``: the statement or choice under judgment (str)
``for_evidence``: list of ``{"point": str, "weight": number}``
``against_evidence``: same shape
``threshold``: margin below which the verdict is "balanced" (default 0.15)

Output verdict: ``{"lean": "for"|"against"|"balanced", ...}``.
Confidence calibrates to the weight margin: near 0.5 on a coin flip,
climbing toward 1.0 as one side dominates. Advisory only — the engine
judges, the keeper decides.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry


def _side(evidence: Any, label: str) -> List[Dict[str, Any]]:
    if evidence is None:
        return []
    if not isinstance(evidence, list):
        raise EngineInputError(f"weigh: '{label}' must be a list")
    cleaned = []
    for i, e in enumerate(evidence):
        if not isinstance(e, dict) or "point" not in e:
            raise EngineInputError(
                f"weigh: '{label}'[{i}] needs a 'point'"
            )
        w = float(e.get("weight", 1.0))
        if w < 0:
            raise EngineInputError(f"weigh: '{label}'[{i}] weight < 0")
        cleaned.append({"point": str(e["point"]), "weight": w})
    return cleaned


def _weigh(inputs: Dict[str, Any]) -> EngineResult:
    proposition = inputs.get("proposition")
    if not proposition or not isinstance(proposition, str):
        raise EngineInputError("weigh: 'proposition' must be a non-empty string")
    for_side = _side(inputs.get("for_evidence"), "for_evidence")
    against_side = _side(inputs.get("against_evidence"), "against_evidence")
    threshold = float(inputs.get("threshold", 0.15))

    trace: List[str] = [f"proposition: {proposition}"]
    for_w = sum(e["weight"] for e in for_side)
    against_w = sum(e["weight"] for e in against_side)
    total = for_w + against_w
    trace.append(
        f"for {for_w:.1f} ({len(for_side)} points) vs "
        f"against {against_w:.1f} ({len(against_side)} points)"
    )
    if total == 0:
        verdict = {
            "proposition": proposition,
            "lean": "balanced",
            "margin": 0.0,
            "decisive_for": [],
            "decisive_against": [],
        }
        trace.append("no evidence on either side — balanced by default")
        return EngineResult(
            engine_id="weigh", verdict=verdict, confidence=0.5, trace=trace
        )

    margin = (for_w - against_w) / total
    if abs(margin) < threshold:
        lean = "balanced"
    elif margin > 0:
        lean = "for"
    else:
        lean = "against"

    # Decisive factors: top contributors on each side, heaviest first.
    top_for = sorted(for_side, key=lambda e: -e["weight"])[:3]
    top_against = sorted(against_side, key=lambda e: -e["weight"])[:3]
    # Confidence: 0.5 at the threshold boundary → 0.99 at total dominance.
    span = max(abs(margin) - threshold, 0.0)
    confidence = round(0.5 + 0.49 * min(span / (1.0 - threshold or 1.0), 1.0), 3)

    trace.append(f"margin {margin:+.2f} → lean '{lean}' (threshold ±{threshold})")
    for e in top_for:
        trace.append(f"  for [{e['weight']:.1f}]: {e['point'][:80]}")
    for e in top_against:
        trace.append(f"  against [{e['weight']:.1f}]: {e['point'][:80]}")

    verdict = {
        "proposition": proposition,
        "lean": lean,
        "margin": round(margin, 3),
        "for_weight": round(for_w, 2),
        "against_weight": round(against_w, 2),
        "decisive_for": [e["point"] for e in top_for],
        "decisive_against": [e["point"] for e in top_against],
    }
    return EngineResult(
        engine_id="weigh", verdict=verdict, confidence=confidence, trace=trace
    )


WEIGH_ENGINE = Engine(
    id="weigh",
    name="Weigh",
    description=(
        "Two-sided judgment over weighted evidence: lean (for/against/"
        "balanced), margin, decisive factors, calibrated confidence."
    ),
    required=("proposition",),
    schema={
        "proposition": "statement under judgment (str)",
        "for_evidence": "list[{point, weight}] (optional)",
        "against_evidence": "list[{point, weight}] (optional)",
        "threshold": "balanced-band half-width (default 0.15)",
    },
    risk="info",
    handler=_weigh,
)

registry.register(WEIGH_ENGINE)
