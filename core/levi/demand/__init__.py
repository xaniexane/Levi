"""DemandPulse — perception of demand, gaps, opportunities."""

from __future__ import annotations

from levi.demand.pulse import DemandPulse
from levi.demand.scoring import (
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    FACTORS,
    FactorScore,
    ScoreCard,
    composite_score,
    parse_weights,
    rank_cards,
    score_card,
    tier_for,
    validate_factors,
    validate_weights,
)

from levi.demand.authority import (
    TIER_MAJOR,
    TIER_MID,
    TIER_MINOR,
    Action,
    AuthorityEngine,
    AuthorityRefused,
    Escalation,
    Receipt,
    SensedSignal,
    classify_action,
    register_executor,
)

__all__ = [
    "DemandPulse",
    "TIER_MAJOR",
    "TIER_MID",
    "TIER_MINOR",
    "Action",
    "AuthorityEngine",
    "AuthorityRefused",
    "Escalation",
    "Receipt",
    "SensedSignal",
    "classify_action",
    "register_executor",
    "DEFAULT_THRESHOLD",
    "DEFAULT_WEIGHTS",
    "FACTORS",
    "FactorScore",
    "ScoreCard",
    "composite_score",
    "parse_weights",
    "rank_cards",
    "score_card",
    "tier_for",
    "validate_factors",
    "validate_weights",
]
