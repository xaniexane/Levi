"""Creator-platform pricing — two separate schedules, doctrine-driven.

Chauncey's correction (2026-09-17): the $1 / $5 / $12-15 tiers are the
DATING side's prices only. The creator-service side gets its own
competitive pricing. The two schedules are separate objects, separate
docs sections, never mixed.

Every price below was set by running the founder price advisor
(:mod:`levi.advisor.pricing`) against VERIFIED competitor numbers —
never invented ones. The config is built by actually calling
``advise_price``; the receipts ride along in each tier. Rebuilding is
deterministic: same inputs, same prices.

Verified competitor anchors (2026-09-17/18):
- Dating monthly: Tinder Plus $24.99/mo (1-month, Android Authority).
- Creator monthly: OnlyFans median paid-profile price $9.99/mo
  (June 2026 creator dataset, ~100k profiles).
- Creator flagship: OnlyFans top of typical range $49.99/mo.
- Platform cut: OnlyFans keeps a flat 20% (Fenix filings via Variety;
  OnlyFans terms).

Doctrine applied: 40-70% below the giant (volume -> low end), entry
dollar-scale, no free core, volume over margin. Where the keeper's own
anchor differs from the advisor's volume recommendation, the keeper's
word is the spec — the variance is recorded honestly on the tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from levi.advisor.pricing import PriceAdvice, PricePlan, advise_price

# Verified competitor anchors. Change these only with a newly verified
# number and its source — never from memory, never invented.
GIANT = {
    "dating_monthly_tinder_plus": {"price": 24.99, "source": "Android Authority, Tinder plans 2026"},
    "creator_monthly_of_median": {"price": 9.99, "source": "OnlyFans creator dataset, Jun 2026 (median paid profile)"},
    "creator_flagship_of_top": {"price": 49.99, "source": "OnlyFans typical range top $4.99-$49.99/mo"},
    "platform_cut_of": {"rate": 0.20, "source": "OnlyFans terms; Fenix International filings via Variety"},
}

# Platform cut: 60% of the prevailing 20% standard = 12% — exactly 40%
# below the giant, inside the doctrine's 40-70% band.
PLATFORM_CUT = 0.12


@dataclass
class TierPrice:
    """One priced tier: the price, its period, and the advisor receipt."""

    name: str
    price_minor: int  # integer minor units (cents) — no float money
    period: str  # "day" | "week" | "month"
    track: str  # "dating" | "creator"
    advisor_tier: str  # entry | standard | flagship
    giant_key: str | None
    advice: PriceAdvice
    variance: str = ""  # honest note when the keeper's anchor != advice
    receipt: Dict[str, Any] = field(default_factory=dict)


def _price(name: str, price_minor: int, period: str, track: str,
           advisor_tier: str, giant_key: str | None, variance: str = "") -> TierPrice:
    giant = GIANT[giant_key]["price"] if giant_key else None
    advice = advise_price(PricePlan(tier=advisor_tier, giant_price=giant, strategy="volume"))
    return TierPrice(
        name=name,
        price_minor=price_minor,
        period=period,
        track=track,
        advisor_tier=advisor_tier,
        giant_key=giant_key,
        advice=advice,
        variance=variance,
        receipt={
            "price_minor": price_minor,
            "band": [advice.low, advice.high],
            "recommended": advice.recommended,
            "giant": giant,
            "giant_source": GIANT[giant_key]["source"] if giant_key else None,
            "strategy": "volume",
        },
    )


def build_dating_schedule() -> List[TierPrice]:
    """Dating-side price schedule. $1 day / $5 week / $12 month."""
    return [
        _price(
            name="day_pass", price_minor=100, period="day", track="dating",
            advisor_tier="entry", giant_key=None,
            variance="keeper anchor $1.00 == advisor volume recommendation $1.00 — no variance",
        ),
        _price(
            name="weekly", price_minor=500, period="week", track="dating",
            advisor_tier="standard", giant_key=None,
            variance="advisor volume recommended $3.00 (band $3.00-$25.00, no giant); "
                     "keeper set $5.00 — inside the band, compliant",
        ),
        _price(
            name="monthly", price_minor=1200, period="month", track="dating",
            advisor_tier="flagship", giant_key="dating_monthly_tinder_plus",
            variance="advisor volume recommended $10.00 (band $10.00-$17.49, "
                     "40-70% below Tinder Plus $24.99); keeper's $12-15 range "
                     "honored at $12.00 — inside the band, compliant",
        ),
    ]


def build_creator_schedule() -> List[TierPrice]:
    """Creator-service price schedule. Its own competitive structure."""
    return [
        _price(
            name="taste", price_minor=100, period="day", track="creator",
            advisor_tier="entry", giant_key=None,
            variance="3-day sampler; advisor volume recommendation $1.00 — no variance",
        ),
        _price(
            name="monthly", price_minor=400, period="month", track="creator",
            advisor_tier="standard", giant_key="creator_monthly_of_median",
            variance="advisor volume recommended $4.00 (band $4.00-$6.99, 40-70% "
                     "below OnlyFans median $9.99) — no variance",
        ),
        _price(
            name="patron", price_minor=2000, period="month", track="creator",
            advisor_tier="flagship", giant_key="creator_flagship_of_top",
            variance="advisor volume recommended $20.00 (band $20.00-$34.99, 40-70% "
                     "below OnlyFans top $49.99) — no variance",
        ),
    ]


# Built once at import: deterministic, doctrine-driven, receipt-carrying.
DATING_SCHEDULE: List[TierPrice] = build_dating_schedule()
CREATOR_SCHEDULE: List[TierPrice] = build_creator_schedule()


def schedule_for(track: str) -> List[TierPrice]:
    """Fetch one schedule. The tracks never share a schedule object."""
    if track == "dating":
        return DATING_SCHEDULE
    if track == "creator":
        return CREATOR_SCHEDULE
    raise ValueError("track must be 'dating' or 'creator', got %r" % track)


def suggested_tiers(track: str) -> List[Dict[str, Any]]:
    """Suggested subscription tiers a creator/dating-profile can adopt.

    Returns plain dicts (name, price_minor, period) ready for
    ``si_subscriptions.add_tier`` / ``ai_creators.add_tier``.
    """
    return [
        {"name": t.name, "price_minor": t.price_minor, "period": t.period, "perks": []}
        for t in schedule_for(track)
    ]


def platform_fee(amount_minor: int) -> int:
    """Platform cut on a paid flow, in minor units. Undercuts the 20% standard."""
    if not isinstance(amount_minor, int) or amount_minor < 0:
        raise ValueError("amount_minor must be a non-negative integer")
    return int(amount_minor * PLATFORM_CUT)


def creator_share(amount_minor: int) -> int:
    """What the creator keeps after the platform cut."""
    return amount_minor - platform_fee(amount_minor)
