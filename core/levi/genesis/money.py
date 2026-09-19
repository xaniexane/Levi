"""Genesis money seam — PAPER ONLY.

Standing law: paper money until Chauncey registers a real rail.
- Price quotes come from the keeper's price advisor
  (``levi.advisor.pricing``) — doctrine, not invention.
- Checkout goes through the Cybrus gateway ONLY — and since no rail is
  registered, checkout returns a paper receipt explaining exactly that.
- The 70/30 split is computed with ``levi.income.engine.split_income``
  and shown as a projection; nothing is ever recorded as income here.
  Never invent income, never invent a payment rail.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from levi.genesis import parts

FORM_NAME = "genesis.money"

# Buyer-safe scrub: the price advisor's rationale mentions roster canon
# wording ("legion" seats etc.) that must not reach the buyer's pack.
_SCRUB_WORDS = set(parts.BASE_AGENTS) | {
    "legion", "dynasty", "section 0", "cybrus",
}


def _scrub_rationale(lines):
    out = []
    for line in lines:
        low = line.lower()
        if any(w in low for w in _SCRUB_WORDS):
            continue
        out.append(line)
    return out


def quote_pack(
    variant_count: int,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
) -> Dict[str, Any]:
    """Paper price quote for a genesis pack.

    The advisor prices tiers per month; a genesis pack is a lifetime
    one-copy buy, so the quote takes the advised flagship band and marks
    it plainly as a lifetime-buy price in paper mode. Deterministic.
    """
    from levi.advisor.pricing import PricePlan, advise_price
    from levi.income.engine import split_income

    advice = advise_price(
        PricePlan(tier="flagship", giant_price=giant_price, strategy=strategy)
    )
    projected = round(advice.recommended, 2)
    split = split_income(projected)
    rationale = _scrub_rationale(advice.rationale) + [
        "genesis canon: lifetime 1-copy buy — the flagship band is "
        "quoted as the one-time lifetime price, paper mode"
    ]
    return {
        "form": FORM_NAME,
        "mode": "paper",
        "variant_count": variant_count,
        "price_band": [advice.low, advice.high],
        "recommended_lifetime_price": projected,
        "seat_note": "genesis pack: single copy, one buyer — roster seat caps do not apply",
        "split_projection": {
            "keeper_70": round(split["keeper"], 2),
            "pool_30": round(split["pool"], 2),
        },
        "rationale": rationale,
        "gateway": "cybrus",
        "rail": "none-registered",
    }


def checkout_paper(quote: Dict[str, Any]) -> Dict[str, Any]:
    """Checkout attempt — Cybrus gateway only, paper mode.

    With no real rail registered this returns a paper receipt that says
    exactly that. It NEVER records income and NEVER invents a rail.
    When Chauncey registers a rail via cybrus, the sale step fills the
    license buyer field and records real income then — not here.
    """
    from levi.cybrus.money import NoRailConfigured, _load_rails

    rails = _load_rails()
    if not rails:
        return {
            "form": FORM_NAME,
            "status": "paper-only",
            "message": (
                "No payment rail is registered with the Cybrus gateway, so "
                "this checkout is paper-only. Register a rail via cybrus to "
                "take real payment; nothing was charged, nothing was recorded."
            ),
            "gateway": "cybrus",
            "rails_found": [],
            "quote": quote,
        }
    # A rail exists: still paper until Chauncey authorizes the sale step.
    return {
        "form": FORM_NAME,
        "status": "paper-only-rail-present",
        "message": (
            "A rail is registered but the sale step has not run — no charge "
            "was made. Real checkout happens only at the keeper's explicit "
            "sale authorization."
        ),
        "gateway": "cybrus",
        "rails_found": sorted(rails.keys()),
        "quote": quote,
    }


def price_receipt(variant_count: int, **kwargs: Any) -> Dict[str, Any]:
    """One call: quote + paper checkout, returned together."""
    q = quote_pack(variant_count, **kwargs)
    return {"quote": q, "checkout": checkout_paper(q)}
