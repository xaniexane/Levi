"""Legion product tiers: standard and Nephilim grade.

"Nephilim grade" is Chauncey's canon proper noun for the premium hybrid
form — the fused, greater-than-either-parent form — and it is kept
verbatim everywhere it appears here. It names the product grade only;
nothing dynasty-internal is embedded in this module, its docs, or its
tests (eyes-only law).

Money is PAPER throughout: every price carries paper=True, is labeled
PAPER, and no payment rail exists, is imported, or is referenced. This
module asserts its own no-rail hygiene at import time.

Genesis integration (DOCUMENTED, NOT WIRED — core/levi/genesis/ files
are in-flight with siblings):
    Genesis pack descriptors (plain dicts) gain an optional "grade"
    field: "standard" | "nephilim". When the genesis assembler is
    wired, it selects the seat operator for the pack from the grade:

        grade="standard" -> the standard hybrid operator seat
        grade="nephilim" -> NEPHILIM_FUSED_OPERATOR (below), the fused
                            operator seat name declared here; the fused
                            operator itself is built in parallel by
                            Track 2 in core/levi/operator/nephilim.py.
                            If that module registers a different name,
                            genesis must read the name from config here
                            (naming law: operator name comes from
                            config, not from a re-type).

    Until wired, use tiers.with_grade(descriptor, grade) to stamp and
    validate the grade field on any pack-descriptor dict.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from .product import LegionError

GRADE_STANDARD = "standard"
GRADE_NEPHILIM = "nephilim"
VALID_GRADES = (GRADE_STANDARD, GRADE_NEPHILIM)

# Declared seat-operator name for Nephilim-grade seats. The fused
# operator is built in parallel (Track 2, core/levi/operator/nephilim.py);
# this name is the config-side contract the operator must register under.
NEPHILIM_FUSED_OPERATOR = "nephilim-fused"

# The standard hybrid seat operator name (on-demand twin-pair hybrid).
STANDARD_HYBRID_SEAT = "hybrid-twin-pair"


# ---------------------------------------------------------------------------
# Paper prices
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperPrice:
    """A price that can never be charged: labeled PAPER, paper=True.

    frozen so a price point cannot be silently re-priced in place.
    """

    amount_usd: float
    label: str
    paper: bool = True
    currency: str = "USD"
    mode: str = "paper"

    def __post_init__(self) -> None:
        if not self.paper:
            raise LegionError("PaperPrice must be paper=True — money is paper only")
        if self.mode != "paper":
            raise LegionError("PaperPrice mode must be 'paper'")
        if self.amount_usd <= 0:
            raise LegionError(
                "no free core: a tier price must be a positive price"
            )
        if "paper" not in self.label.lower():
            raise LegionError(
                "every tier price label must carry the PAPER label"
            )


# ---------------------------------------------------------------------------
# No payment rails — ever. Enforced at import.
# ---------------------------------------------------------------------------

# Built from fragments so the module's own token list never trips the
# self-check below (the list names the tokens without quoting them).
_FORBIDDEN_RAIL_TOKENS = tuple(
    a + b
    for a, b in (
        ("st", "ripe"),
        ("pay", "pal"),
        ("squa", "reup"),
        ("brain", "tree"),
        ("razo", "rpay"),
        ("check", "out.com"),
        ("payment", "_sdk"),
        ("payments", "_sdk"),
    )
)


def assert_no_payment_rails() -> None:
    """Scan this module's own source for real payment-rail references.

    A real rail import or reference here would violate the paper-money
    law. Scans import statements and attribute references, ignoring the
    token list above and this function's own docstring. Raises
    AssertionError if any forbidden token appears in this module's
    source.
    """
    src = inspect.getsource(inspect.getmodule(assert_no_payment_rails))
    lines = []
    skip = False
    for line in src.splitlines():
        stripped = line.strip()
        # Skip the token-list builder and this function's docstring.
        if stripped.startswith('_FORBIDDEN_RAIL_TOKENS = tuple('):
            skip = True
            continue
        if skip:
            if stripped == ')':
                skip = False
            continue
        if '"""' in stripped and 'self-check' in stripped:
            continue
        lines.append(line)
    lowered = "\n".join(lines).lower()
    hits = [t for t in _FORBIDDEN_RAIL_TOKENS if t in lowered]
    if hits:
        raise AssertionError(
            "paper-money law violated: payment-rail references in "
            f"tiers.py: {hits}"
        )


# ---------------------------------------------------------------------------
# Tier spec
# ---------------------------------------------------------------------------

# Feature slugs. Nephilim grade MUST include every standard feature
# (superset law) plus the fused-form features.
STANDARD_FEATURES = (
    "one_face_router",
    "white_label",
    "hybrid_twin_pair_on_demand",
    "nano_bit_bulk_tier",
    "single_operator_seats",
    "pack_add_ons",
)

NEPHILIM_EXTRA_FEATURES = (
    "nephilim_fused_operator_seat",
    "twin_on_demand_priority_escalation",
    "cross_mind_pattern_synthesis_reports",
)

NEPHILIM_FEATURES = STANDARD_FEATURES + NEPHILIM_EXTRA_FEATURES


@dataclass
class TierSpec:
    """One product tier of the Legion bot."""

    key: str                        # "standard" | "nephilim"
    name: str                       # display name
    grade_label: str                # grade label, canon verbatim
    features: List[str]             # feature slugs (see above)
    operator_wiring: Dict[str, Any]  # per-seat operator wiring, as data
    price_lifetime: PaperPrice      # paper one-time lifetime price
    price_multiplier: float         # vs the advisor's base lifetime quote
    limits: Dict[str, Any]          # seats / usage limits, as data
    white_label: bool = True

    def __post_init__(self) -> None:
        if self.key not in VALID_GRADES:
            raise LegionError(
                f"unknown tier {self.key!r} — choose one of {VALID_GRADES}"
            )
        if self.grade_label != self.key:
            raise LegionError(
                "grade label must match the tier key verbatim "
                f"(got {self.grade_label!r} for key {self.key!r})"
            )
        if self.price_multiplier <= 0:
            raise LegionError("tier price multiplier must be positive")
        if not self.price_lifetime.paper:
            raise LegionError("tier price must be paper")

    def has_feature(self, slug: str) -> bool:
        return slug in self.features

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "grade_label": self.grade_label,
            "features": list(self.features),
            "operator_wiring": dict(self.operator_wiring),
            "price_lifetime_usd": self.price_lifetime.amount_usd,
            "price_label": self.price_lifetime.label,
            "price_multiplier": self.price_multiplier,
            "limits": dict(self.limits),
            "white_label": self.white_label,
        }


def _base_lifetime_price() -> float:
    """Advisor's base lifetime price for the Legion flagship tier.

    Matches the sale.py quote math: recommended monthly x 24 months
    (LIFETIME_MONTHS), stated plainly. Deterministic under the volume
    strategy.
    """
    from levi.advisor.pricing import PricePlan, advise_price
    from .sale import LIFETIME_MONTHS

    advice = advise_price(
        PricePlan(tier="flagship", giant_price=None, strategy="volume")
    )
    return round(advice.recommended * LIFETIME_MONTHS, 2)


def build_tiers() -> Dict[str, TierSpec]:
    """Build the tier catalog. Raises LegionError on any violation."""
    base = _base_lifetime_price()
    # Nephilim grade is the premium tier: 3x the base lifetime price,
    # stated plainly as the Nephilim-grade premium multiplier.
    nephilim_multiplier = 3.0
    standard = TierSpec(
        key=GRADE_STANDARD,
        name="Legion bot — standard",
        grade_label=GRADE_STANDARD,
        features=list(STANDARD_FEATURES),
        operator_wiring={
            "seat_type": "hybrid",
            "seat_operator": STANDARD_HYBRID_SEAT,
            "twin_pair": "on-demand",
            "escalation": "standard",
            "bulk_tier": "nano-bit",
            "seat_shape": "single-operator",
        },
        price_lifetime=PaperPrice(
            amount_usd=base,
            label=(
                f"PAPER — ${base:,.2f} USD lifetime one-copy, "
                "standard grade. Quote only; no money moves."
            ),
        ),
        price_multiplier=1.0,
        limits={
            "installs": 1,
            "seat_cap": 490,
            "usage": "standard hybrid on-demand twin-pair seats",
        },
    )
    nephilim = TierSpec(
        key=GRADE_NEPHILIM,
        name="Legion bot — Nephilim grade",
        grade_label=GRADE_NEPHILIM,
        features=list(NEPHILIM_FEATURES),
        operator_wiring={
            "seat_type": "nephilim-fused",
            "seat_operator": NEPHILIM_FUSED_OPERATOR,
            "twin_pair": "on-demand",
            "escalation": "priority",
            "bulk_tier": "nano-bit",
            "seat_shape": "fused operator seat",
            "reports": "cross-mind pattern-synthesis reports",
        },
        price_lifetime=PaperPrice(
            amount_usd=round(base * nephilim_multiplier, 2),
            label=(
                "PAPER — $"
                + f"{round(base * nephilim_multiplier, 2):,.2f}"
                + " USD lifetime one-copy, Nephilim grade "
                f"(base x {nephilim_multiplier}, stated plainly). "
                "Quote only; no money moves."
            ),
        ),
        price_multiplier=nephilim_multiplier,
        limits={
            "installs": 1,
            "seat_cap": 490,
            "usage": (
                "nephilim-fused operator seat, twin on-demand with "
                "priority escalation, cross-mind pattern-synthesis reports"
            ),
        },
    )
    tiers = {GRADE_STANDARD: standard, GRADE_NEPHILIM: nephilim}

    # Superset law: Nephilim grade includes every standard feature.
    missing = [f for f in standard.features if f not in nephilim.features]
    if missing:
        raise LegionError(
            "superset law violated: Nephilim grade must include every "
            f"standard feature; missing: {missing}"
        )
    return tiers


TIERS: Dict[str, TierSpec] = build_tiers()

assert_no_payment_rails()


# ---------------------------------------------------------------------------
# Access + grade field for pack descriptors
# ---------------------------------------------------------------------------


def get_tier(key: str) -> TierSpec:
    """Fetch one tier by key. Raises LegionError on unknown tiers."""
    k = (key or "").lower()
    if k not in TIERS:
        raise LegionError(
            f"unknown tier {key!r} — choose one of {sorted(TIERS)}"
        )
    return TIERS[k]


def tier_names() -> List[str]:
    return sorted(TIERS)


def with_grade(descriptor: Mapping[str, Any], grade: str) -> Dict[str, Any]:
    """Stamp a pack-descriptor dict with a validated "grade" field.

    Returns a copy; never mutates the caller's descriptor. Raises
    LegionError on unknown grades. This is the documented integration
    point for the genesis assembler: the "grade" field selects the
    seat operator (standard -> STANDARD_HYBRID_SEAT, nephilim ->
    NEPHILIM_FUSED_OPERATOR) once genesis/assemble.py is wired.
    """
    g = (grade or "").lower()
    if g not in VALID_GRADES:
        raise LegionError(
            f"unknown grade {grade!r} — choose one of {VALID_GRADES}"
        )
    data = dict(descriptor)
    data["grade"] = g
    return data


def seat_operator_for_grade(grade: str) -> str:
    """The operator seat name the grade selects.

    Config-side contract for the genesis assembler wiring: the name
    comes from config here, never re-typed at the call site.
    """
    g = (grade or "").lower()
    if g == GRADE_NEPHILIM:
        return NEPHILIM_FUSED_OPERATOR
    if g == GRADE_STANDARD:
        return STANDARD_HYBRID_SEAT
    raise LegionError(
        f"unknown grade {grade!r} — choose one of {VALID_GRADES}"
    )
