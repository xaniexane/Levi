"""advisor: founder-level feature/price advisor (LEVI-native).

Founder-grade extra modules + skill set. Two instruments:

- ``levi.advisor.features`` — feature advisor: scores a feature idea
  (demand signal via DemandPulse, strategic weight via Oracle, build
  cost, doctrine fit) and returns build / hold / kill with reasons.
- ``levi.advisor.pricing`` — price advisor: recommends a price band per
  the keeper's pricing doctrine (paid entry at dollar scale — no free
  core, ever; ~30-60% below the giants; volume over margin; roster law
  seat caps; AI+SI pairing as the product; founder commission where
  applicable).

Both compose the founders — they never duplicate founder logic. The
feature advisor calls ``levi.demand.scoring.score_card`` and
``levi.oracle.weight_goals`` for real. Deterministic: identical inputs
always produce the identical verdict.

Honesty law: a verdict describes an assessment; it executes nothing,
guarantees nothing, and touches no money.

Stdlib only. Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from .features import (
    COST_EFFICIENCY,
    FEATURE_STRATEGY,
    FeatureIdea,
    FeatureVerdict,
    advise_feature,
)
from .pricing import (
    ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED,
    ENTERPRISE_COMMITMENT_MONTHS,
    ENTERPRISE_PER_EMPLOYEE_MONTH_USD,
    ENTERPRISE_TERM,
    KEEPER_CONFIRMABLE_SEAT_DEFINITION,
    ROSTER_SEAT_CAPS,
    SEAT_PREMIUM_USD,
    SEAT_STANDARD_USD,
    SEAT_TERM,
    EnterpriseBelowFloorError,
    EnterpriseQuote,
    PriceAdvice,
    PriceError,
    PricePlan,
    SeatQuote,
    advise_price,
    quote_enterprise,
    quote_seat_price,
)

__all__ = [
    "ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED",
    "ENTERPRISE_COMMITMENT_MONTHS",
    "ENTERPRISE_PER_EMPLOYEE_MONTH_USD",
    "ENTERPRISE_TERM",
    "KEEPER_CONFIRMABLE_SEAT_DEFINITION",
    "ROSTER_SEAT_CAPS",
    "SEAT_PREMIUM_USD",
    "SEAT_STANDARD_USD",
    "SEAT_TERM",
    "EnterpriseBelowFloorError",
    "EnterpriseQuote",
    "FeatureIdea",
    "FeatureVerdict",
    "PriceAdvice",
    "PriceError",
    "PricePlan",
    "SeatQuote",
    "advise_feature",
    "advise_price",
    "quote_enterprise",
    "quote_seat_price",
]
