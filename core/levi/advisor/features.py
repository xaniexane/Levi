"""Feature advisor: build / hold / kill for feature ideas.

Composes the founders — never duplicates their logic:

- Demand signal: ``levi.demand.scoring.score_card`` (the real DemandPulse
  five-factor composite) when the analyst supplies all five factors, or
  an analyst-assessed composite when they don't. Without demand evidence
  the verdict caps at HOLD — the advisor never builds on vibes.
- Strategic weight: ``levi.oracle.weight_goals`` against the canonical
  ``FEATURE_STRATEGY`` (demand evidence .30 / strategic fit .30 /
  doctrine fit .25 / cost efficiency .15). Oracle's score is arithmetic,
  not prediction — it says how the idea aligns with the stated strategy.

Deterministic: identical inputs always produce the identical verdict.
Fail-closed: malformed input raises ``FeatureError``; nothing is guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from levi.demand.scoring import FACTORS, score_card, tier_for
from levi.oracle import Criterion, Strategy, weight_goals

FORM_NAME = "advisor.features"


class FeatureError(ValueError):
    """Malformed feature idea — data, not a verdict."""


# Canonical feature strategy: named criteria with weights. Sums to 1.0.
FEATURE_STRATEGY = Strategy(
    name="feature-strategy",
    criteria=[
        Criterion("demand_evidence", 0.30),
        Criterion("strategic_fit", 0.30),
        Criterion("doctrine_fit", 0.25),
        Criterion("cost_efficiency", 0.15),
    ],
)

# Documented heuristic: build-cost tier -> efficiency rating.
COST_EFFICIENCY: Dict[str, float] = {
    "small": 1.0,
    "medium": 0.6,
    "large": 0.3,
}

BUILD_ALIGNMENT = 0.70  # oracle alignment >= this -> build-eligible
BUILD_DEMAND = 75.0  # demand composite >= this (DemandPulse "high") -> build-eligible
KILL_DEMAND = 50.0  # demand composite < this (DemandPulse "low") -> kill
KILL_DOCTRINE = 0.40  # doctrine_fit < this -> kill


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FeatureIdea:
    """One feature idea under advisement.

    demand_factors: the five DemandPulse factors (demand, market_size,
    competition_gap, trend_velocity, entry_feasibility), each a
    (score 0-100, basis) pair — scored for real by levI.demand.scoring.
    demand_composite: alternative — an analyst-assessed 0-100 composite
    with demand_basis. One of the two demand inputs is required; without
    either, the verdict caps at HOLD.
    """

    name: str
    description: str = ""
    demand_factors: Optional[Mapping[str, Any]] = None
    demand_composite: Optional[float] = None
    demand_basis: str = ""
    strategic_fit: float = 0.5  # 0..1, analyst rating
    cost: str = "medium"  # small | medium | large
    doctrine_fit: float = 0.5  # 0..1, analyst rating


@dataclass
class FeatureVerdict:
    verdict: str  # build | hold | kill
    alignment: float  # oracle weighted alignment 0..1
    demand_composite: Optional[float]
    demand_tier: str  # high | watch | low | unassessed
    reasons: List[str] = field(default_factory=list)
    receipt: Dict[str, Any] = field(default_factory=dict)


def _validate_idea(idea: FeatureIdea) -> None:
    if not isinstance(idea, FeatureIdea):
        raise FeatureError(f"idea must be a FeatureIdea, got {type(idea).__name__}")
    if not idea.name or not idea.name.strip():
        raise FeatureError("idea needs a name")
    if idea.cost not in COST_EFFICIENCY:
        raise FeatureError(f"cost must be one of {sorted(COST_EFFICIENCY)}")
    for label, value in (("strategic_fit", idea.strategic_fit), ("doctrine_fit", idea.doctrine_fit)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
            raise FeatureError(f"{label} must be 0..1, got {value!r}")
    if idea.demand_factors is not None and idea.demand_composite is not None:
        raise FeatureError("give demand_factors OR demand_composite, not both")
    if idea.demand_composite is not None:
        v = idea.demand_composite
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0.0 <= v <= 100.0:
            raise FeatureError(f"demand_composite must be 0..100, got {v!r}")
        if not idea.demand_basis.strip():
            raise FeatureError("demand_composite needs a demand_basis — scores are judgments, never measurements")


def _demand_signal(idea: FeatureIdea) -> tuple[Optional[float], str, List[str]]:
    """Returns (composite, tier, reasons). Real DemandPulse scoring when
    five factors are supplied; analyst-assessed composite otherwise."""
    reasons: List[str] = []
    if idea.demand_factors is not None:
        card = score_card(
            opportunity_id=idea.name.strip().lower().replace(" ", "-"),
            title=idea.name,
            factors=idea.demand_factors,
        )
        composite = card.composite
        reasons.append(f"DemandPulse five-factor composite {composite:.2f} (auditable via score_card)")
        return composite, tier_for(composite), reasons
    if idea.demand_composite is not None:
        composite = round(float(idea.demand_composite), 2)
        reasons.append(f"demand composite {composite:.2f} analyst-assessed — basis: {idea.demand_basis.strip()}")
        return composite, tier_for(composite), reasons
    reasons.append("no demand evidence supplied — verdict capped at HOLD")
    return None, "unassessed", reasons


def advise_feature(idea: FeatureIdea) -> FeatureVerdict:
    """Score one feature idea. Deterministic. Returns build/hold/kill."""
    _validate_idea(idea)
    demand_composite, demand_tier, reasons = _demand_signal(idea)

    # Oracle: real strategic weighting against the canonical strategy.
    ratings = {
        "demand_evidence": (demand_composite / 100.0) if demand_composite is not None else 0.0,
        "strategic_fit": float(idea.strategic_fit),
        "doctrine_fit": float(idea.doctrine_fit),
        "cost_efficiency": COST_EFFICIENCY[idea.cost],
    }
    oracle_receipt = weight_goals(
        FEATURE_STRATEGY,
        [{"id": "idea", "name": idea.name, "ratings": ratings}],
    )
    ranking = oracle_receipt.get("ranking", [])
    alignment = round(float(ranking[0]["score"]), 4) if ranking else 0.0
    reasons.append(f"Oracle alignment {alignment:.3f} against feature-strategy")

    if idea.doctrine_fit < KILL_DOCTRINE:
        verdict = "kill"
        reasons.append(f"doctrine_fit {idea.doctrine_fit:.2f} < {KILL_DOCTRINE} — violates the keeper's doctrine")
    elif demand_composite is not None and demand_composite < KILL_DEMAND:
        verdict = "kill"
        reasons.append(f"demand {demand_composite:.2f} < {KILL_DEMAND} (DemandPulse 'low') — no pull, no build")
    elif demand_composite is None:
        verdict = "hold"
    elif demand_composite >= BUILD_DEMAND and alignment >= BUILD_ALIGNMENT:
        verdict = "build"
        reasons.append(f"demand {demand_composite:.2f} >= {BUILD_DEMAND} and alignment {alignment:.3f} >= {BUILD_ALIGNMENT}")
    else:
        verdict = "hold"
        reasons.append("meets neither the build bar nor the kill floor — hold for more evidence")

    return FeatureVerdict(
        verdict=verdict,
        alignment=alignment,
        demand_composite=demand_composite,
        demand_tier=demand_tier,
        reasons=reasons,
        receipt={
            "form": FORM_NAME,
            "idea": idea.name,
            "verdict": verdict,
            "alignment": alignment,
            "demand_composite": demand_composite,
            "demand_tier": demand_tier,
            "oracle_receipt": oracle_receipt.get("status"),
            "at": _utcnow(),
        },
    )
