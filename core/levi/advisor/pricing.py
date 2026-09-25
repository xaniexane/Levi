"""Price advisor: price bands per the keeper's pricing doctrine.

Binding doctrine (the keeper's word, enforced in code):

- NO FREE CORE, EVER. A price of zero is rejected as ``PriceError`` —
  the free tier is dead by the keeper's own hand. The entry tier is
  paid-but-tiny: dollar scale.
- ~30-60% BELOW THE GIANTS. With a giant reference price supplied, the
  band is ``giant * 0.40`` to ``giant * 0.70`` — never at or above the
  giant. Without a reference, bands come from doctrine anchors and the
  advice says so plainly. The advisor never invents a competitor's price.
- VOLUME OVER MARGIN. ``strategy="volume"`` recommends the low end of
  the band; ``strategy="margin"`` the high end.
- ROSTER LAW. Tier seat/user caps come from the roster canon: the 19
  founder seats, the 122 first-wave seats, the 490 full-legion seats.
  Suggested caps are drawn from ``ROSTER_SEAT_CAPS``.
- AI+SI PAIRING AS THE PRODUCT. Pricing is per seat/pair, never per
  model call — the pairing is what the customer buys.
- FOUNDER COMMISSION where applicable: a commission rate adds a
  separate, labeled line — never hidden inside the price.

Seat tiers (the keeper's word, 2026-09-18; raised 2026-09-18 — still
way below the usual rent): STANDARD seat = $300,
PREMIUM (counsel-backed) seat = $600 — both LIFETIME, one-time
per-seat buys, paper quotes only. The seat definition (seat = one
agent seat in the purchased pack) is flagged KEEPER-CONFIRMABLE: he
has not confirmed it, and every seat quote carries the flag.
ENTERPRISE: floor $100/employee/month, 12-month commitment —
confirmed law 2026-09-18 (his word: "no less than 100 per employee
every month a year"). Quote = floor x employees x 12 months for the
annual commitment (4 employees -> $4,800/year). Any quote BELOW the
floor is refused loud. A keeper-set HIGHER rate may ride as an
explicit override; nothing rides below the floor. The old $2-$5k
band survives only as a DERIVED observation (4 x $1,200/yr = $4,800
— the annual total a small team lands in), never a price. The $500
per-employee figure is dead — struck, then superseded twice over;
no trace of it prices anything.

Deterministic: identical inputs always produce the identical band.
Fail-closed: malformed input raises ``PriceError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

FORM_NAME = "advisor.pricing"


class PriceError(ValueError):
    """Malformed price plan — data, not a band."""


# Roster law: tier seat caps drawn from the legion roster canon.
# 19 founder seats, 122 first-wave seats, 490 full-legion seats.
ROSTER_SEAT_CAPS: Dict[str, int] = {
    "founder": 19,
    "wave": 122,
    "legion": 490,
}

# Doctrine anchors (USD/month) when no giant reference is supplied.
# Entry stays dollar-scale; higher tiers scale as multiples of entry.
ENTRY_FLOOR = 1.0
ENTRY_CEILING = 5.0
STANDARD_MULT = (3.0, 5.0)  # x entry
FLAGSHIP_MULT = (8.0, 12.0)  # x entry

# ~30-60% below the giants: band = giant * (0.40, 0.70).
GIANT_DISCOUNT = (0.40, 0.70)

_VALID_TIERS = ("entry", "standard", "flagship")
_VALID_STRATEGIES = ("volume", "margin")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PricePlan:
    """One tier under advisement.

    giant_price: the giant's price for the comparable tier, USD/month.
    Supply it when known — the advisor anchors ~30-60% below it and
    never invents one. strategy: "volume" (low end of band) or "margin"
    (high end). founder_commission: 0..1 rate, added as a labeled line
    when > 0.
    """

    tier: str = "entry"
    giant_price: Optional[float] = None
    strategy: str = "volume"
    founder_commission: float = 0.0


@dataclass
class PriceAdvice:
    low: float
    high: float
    recommended: float
    seat_cap: int
    commission_line: float
    rationale: List[str] = field(default_factory=list)
    receipt: Dict[str, object] = field(default_factory=dict)


def _validate_plan(plan: PricePlan) -> None:
    if not isinstance(plan, PricePlan):
        raise PriceError(f"plan must be a PricePlan, got {type(plan).__name__}")
    if plan.tier not in _VALID_TIERS:
        raise PriceError(f"tier must be one of {_VALID_TIERS}, got {plan.tier!r}")
    if plan.strategy not in _VALID_STRATEGIES:
        raise PriceError(f"strategy must be one of {_VALID_STRATEGIES}, got {plan.strategy!r}")
    if plan.giant_price is not None:
        g = plan.giant_price
        if not isinstance(g, (int, float)) or isinstance(g, bool) or not g > 0:
            raise PriceError(f"giant_price must be a positive number, got {g!r}")
    c = plan.founder_commission
    if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0.0 <= c <= 1.0:
        raise PriceError(f"founder_commission must be 0..1, got {c!r}")


def advise_price(plan: PricePlan) -> PriceAdvice:
    """Recommend a price band per the keeper's doctrine. Deterministic."""
    _validate_plan(plan)
    rationale: List[str] = []

    if plan.tier == "entry":
        seat_cap = ROSTER_SEAT_CAPS["founder"]
    elif plan.tier == "standard":
        seat_cap = ROSTER_SEAT_CAPS["wave"]
    else:
        seat_cap = ROSTER_SEAT_CAPS["legion"]
    rationale.append(
        f"roster law: {plan.tier} tier capped at {seat_cap} seats "
        f"({'founder' if plan.tier == 'entry' else 'wave' if plan.tier == 'standard' else 'legion'} seats)"
    )

    if plan.giant_price is not None:
        giant = float(plan.giant_price)
        low = round(giant * GIANT_DISCOUNT[0], 2)
        high = round(giant * GIANT_DISCOUNT[1], 2)
        rationale.append(
            f"giant reference ${giant:.2f}/mo supplied — band set "
            f"{int((1 - GIANT_DISCOUNT[1]) * 100)}-{int((1 - GIANT_DISCOUNT[0]) * 100)}% below, "
            "never at or above the giant"
        )
        if plan.tier == "entry" and high > ENTRY_CEILING:
            high = ENTRY_CEILING
            low = min(low, high)
            rationale.append(
                f"entry tier held to dollar scale (<= ${ENTRY_CEILING:.0f}/mo) "
                "even against the giant anchor"
            )
    else:
        if plan.tier == "entry":
            low, high = ENTRY_FLOOR, ENTRY_CEILING
        elif plan.tier == "standard":
            low, high = (
                round(ENTRY_FLOOR * STANDARD_MULT[0], 2),
                round(ENTRY_CEILING * STANDARD_MULT[1], 2),
            )
        else:
            low, high = (
                round(ENTRY_FLOOR * FLAGSHIP_MULT[0], 2),
                round(ENTRY_CEILING * FLAGSHIP_MULT[1], 2),
            )
        rationale.append(
            "no giant reference supplied — band from doctrine anchors; "
            "supply giant_price to anchor ~30-60% below a competitor"
        )

    if plan.strategy == "volume":
        recommended = low
        rationale.append("volume over margin: recommending the low end of the band")
    else:
        recommended = high
        rationale.append("margin strategy: recommending the high end of the band")

    commission_line = round(recommended * plan.founder_commission, 2)
    if plan.founder_commission > 0:
        rationale.append(
            f"founder commission {plan.founder_commission:.0%} — "
            f"${commission_line:.2f}/mo labeled separately, never hidden in the price"
        )
    rationale.append(
        "AI+SI pairing is the product: priced per seat/pair, never per model call"
    )
    rationale.append(
        "no free core: the entry tier is paid-but-tiny — a price of zero is rejected, always"
    )

    return PriceAdvice(
        low=low,
        high=high,
        recommended=recommended,
        seat_cap=seat_cap,
        commission_line=commission_line,
        rationale=rationale,
        receipt={
            "form": FORM_NAME,
            "tier": plan.tier,
            "low": low,
            "high": high,
            "recommended": recommended,
            "seat_cap": seat_cap,
            "strategy": plan.strategy,
            "at": _utcnow(),
        },
    )


# --- Seat pricing (the keeper's word, 2026-09-18; PAPER ONLY) ------------------
#
# Confirmed tiers: STANDARD seat = $300, PREMIUM (counsel-backed) seat = $600.
# Raised 2026-09-18 on the keeper's word ("raise the prices but way below
# usual"): ~one year of the competitors' rent ($240-$360/yr), then free
# forever — and heritable, which no rental can be (see TIERS.md,
# "the holding, not the rental").
#
# +=====================================================================+
# |  SEAT DEFINITION — KEEPER-CONFIRMABLE. The keeper has NOT yet         |
# |  confirmed this definition. Treat it as WORKING LAW, never canon:   |
# |                                                                     |
# |      seat = one agent seat in the purchased pack.                    |
# |      Example: a 5-agent pack at standard = $1,500,                  |
# |               a 5-agent pack at premium = $3,000.                   |
# |                                                                     |
# |  Until he confirms, every seat quote carries this flag verbatim.    |
# +=====================================================================+
#
# PAPER ONLY: the advisor produces quotes — numbers on receipts. No payment
# rail, no checkout, no transaction. A quote is never money.

SEAT_STANDARD_USD = 300.0
SEAT_PREMIUM_USD = 600.0
_SEAT_TIERS = ("standard", "premium")
SEAT_TERM = "lifetime, one-time"  # standard/premium seats: buy once, keep

# The flag, kept verbatim in every seat quote until the keeper confirms.
KEEPER_CONFIRMABLE_SEAT_DEFINITION = (
    "WORKING DEFINITION — AWAITING THE KEEPER'S CONFIRMATION: "
    "seat = one agent seat in the purchased pack (e.g. a 5-agent pack at "
    "standard = $1,500, at premium = $3,000). "
    "Do not treat this definition as canon until the keeper confirms."
)

# Enterprise law (confirmed by the keeper 2026-09-18, his word:
# "no less than 100 per employee every month a year"):
# floor $100/employee/month, 12-month commitment. The floor is the
# floor — any quote below it is refused loud. A keeper-set HIGHER
# rate may ride as an explicit override; nothing rides below.
ENTERPRISE_PER_EMPLOYEE_MONTH_USD = 100.0
ENTERPRISE_COMMITMENT_MONTHS = 12
ENTERPRISE_TERM = "12-month commitment, billed at the monthly floor"

# DERIVED — not prices: annual totals a team lands in AT THE FLOOR.
# The keeper's old $2-$5k band was this kind of observation (4 people
# land at $4,800/year). Orientation only; the law is the floor.
ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED = (
    (4, 4800.0),
    (10, 12000.0),
    (25, 30000.0),
    (100, 120000.0),
)


class EnterpriseBelowFloorError(PriceError):
    """Refused: the rate is below the keeper's $100/employee/month floor."""


def _enterprise_rate_or_floor(enterprise_rate) -> float:
    """Resolve the enterprise rate or refuse loud. Never below the floor."""
    if enterprise_rate is None:
        return ENTERPRISE_PER_EMPLOYEE_MONTH_USD
    if (
        isinstance(enterprise_rate, bool)
        or not isinstance(enterprise_rate, (int, float))
        or not enterprise_rate > 0
    ):
        raise PriceError(
            f"enterprise_rate must be a positive number, got {enterprise_rate!r}"
        )
    rate = float(enterprise_rate)
    if rate < ENTERPRISE_PER_EMPLOYEE_MONTH_USD:
        raise EnterpriseBelowFloorError(
            f"refused: ${rate:.2f}/employee/month is below the keeper's floor "
            f"of ${ENTERPRISE_PER_EMPLOYEE_MONTH_USD:.0f}/employee/month. "
            "The floor is the floor — quotes ride at or above it, never below."
        )
    return rate


@dataclass
class EnterpriseQuote:
    """Paper quote at the enterprise tier: floor x employees x 12 months."""

    employees: int
    per_employee_month: float  # the rate used — at or above the floor, never below
    months: int  # the 12-month commitment
    monthly_total: float
    annual_total: float
    rationale: List[str] = field(default_factory=list)
    receipt: Dict[str, object] = field(default_factory=dict)


@dataclass
class SeatQuote:
    seats: int
    tier: str
    per_seat: float
    total: float
    rationale: List[str] = field(default_factory=list)
    receipt: Dict[str, object] = field(default_factory=dict)


def quote_seat_price(tier: str, seats: int) -> SeatQuote:
    """Paper quote for a seat count at a keeper-confirmed tier. Deterministic."""
    if tier not in _SEAT_TIERS:
        raise PriceError(f"seat tier must be one of {_SEAT_TIERS}, got {tier!r}")
    if isinstance(seats, bool) or not isinstance(seats, int) or seats < 1:
        raise PriceError(f"seats must be a positive integer, got {seats!r}")
    per_seat = SEAT_STANDARD_USD if tier == "standard" else SEAT_PREMIUM_USD
    total = round(per_seat * seats, 2)
    rationale = [
        f"keeper's tier: {tier} seat = ${per_seat:.0f} — confirmed 2026-09-18",
        f"{seats} seats x ${per_seat:.0f} = ${total:.0f} — lifetime, one-time per-seat buy",
        KEEPER_CONFIRMABLE_SEAT_DEFINITION,
        "paper only: a quote is a number on a receipt — no payment rail, no money moved",
    ]
    return SeatQuote(
        seats=seats,
        tier=tier,
        per_seat=per_seat,
        total=total,
        rationale=rationale,
        receipt={
            "form": FORM_NAME,
            "kind": "seat_quote",
            "tier": tier,
            "seats": seats,
            "per_seat": per_seat,
            "total": total,
            "seat_definition_flag": KEEPER_CONFIRMABLE_SEAT_DEFINITION,
            "term": SEAT_TERM,
            "paper_only": True,
            "at": _utcnow(),
        },
    )


def quote_enterprise(
    employees: int,
    enterprise_rate: Optional[float] = None,
) -> EnterpriseQuote:
    """Enterprise paper quote at the keeper's floor.

    Confirmed law 2026-09-18: floor $100/employee/month, 12-month
    commitment. Quote = rate x employees x 12 months (4 employees ->
    $4,800/year). ``enterprise_rate`` is an explicit keeper-set rate
    per employee per month — it may ride HIGHER than the floor, never
    below: below the floor is refused loud (EnterpriseBelowFloorError).
    Deterministic. Paper only.
    """
    if isinstance(employees, bool) or not isinstance(employees, int) or employees < 1:
        raise PriceError(f"employees must be a positive integer, got {employees!r}")
    rate = _enterprise_rate_or_floor(enterprise_rate)
    months = ENTERPRISE_COMMITMENT_MONTHS
    monthly_total = round(rate * employees, 2)
    annual_total = round(monthly_total * months, 2)
    rationale = [
        f"keeper's enterprise floor: ${rate:.0f}/employee/month x {employees} "
        f"employees x {months} months = ${annual_total:.0f}/year "
        "(confirmed 2026-09-18)",
        "12-month commitment, billed at the monthly floor — recurring revenue",
        "paper only: a quote is a number on a receipt — no payment rail, no money moved",
    ]
    return EnterpriseQuote(
        employees=employees,
        per_employee_month=rate,
        months=months,
        monthly_total=monthly_total,
        annual_total=annual_total,
        rationale=rationale,
        receipt={
            "form": FORM_NAME,
            "kind": "enterprise_quote",
            "employees": employees,
            "per_employee_month": rate,
            "months": months,
            "monthly_total": monthly_total,
            "annual_total": annual_total,
            "term": ENTERPRISE_TERM,
            "paper_only": True,
            "at": _utcnow(),
        },
    )
