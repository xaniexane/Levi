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

from levi.demand import ingest as ingest
from levi.demand import processing as processing
from levi.demand import studio as studio
from levi.demand import workflows as workflows

from levi.demand import direction as direction
from levi.demand.direction import (
    DirectionItem,
    DirectionProfile,
    FitResult,
    build_seed_profile,
    coach_brief,
    direction_fit,
    load_profile,
    reseed_profile,
    verdict,
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
    "ingest",
    "processing",
    "studio",
    "workflows",
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
    "direction",
    "DirectionItem",
    "DirectionProfile",
    "FitResult",
    "build_seed_profile",
    "coach_brief",
    "direction_fit",
    "load_profile",
    "reseed_profile",
    "verdict",
]
