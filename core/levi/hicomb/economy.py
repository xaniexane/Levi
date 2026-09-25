"""Hicomb economics: the platform cut as a named constant, entry owner-gated.

Standing law: no-free-core — paid-but-tiny entry, volume over margin.
The exact Hicomb price point is Chauncey's call, so collecting any entry
fee raises OwnerGateRequired until he sets it. Royalty math on digital
products created on-platform uses PLATFORM_CUT = 0.12; the physical-goods
cut is OPEN (invent nothing). No payment wiring here — that gate is his.
"""

from __future__ import annotations

PLATFORM_CUT = 0.12  # 12% platform cut on on-platform digital products

ENTRY_PRICE_USD: float | None = None  # GATED ON CHAUNCEY


class OwnerGateRequired(Exception):
    """An owner decision is required before this step can run."""


def collect_entry_fee() -> float:
    """Collect Hicomb's entry fee. Always raises until Chauncey sets the price."""
    if ENTRY_PRICE_USD is None:
        raise OwnerGateRequired(
            "Hicomb entry price is gated on Chauncey: no-free-core, "
            "paid-but-tiny, volume over margin — his call on the number."
        )
    return ENTRY_PRICE_USD


def marketplace_royalty(sale_price_usd: float) -> float:
    """Platform royalty on an on-platform digital sale. Math only, no wiring."""
    if sale_price_usd < 0:
        raise ValueError("sale price cannot be negative")
    return round(sale_price_usd * PLATFORM_CUT, 2)


def builder_take(sale_price_usd: float) -> float:
    """What the builder keeps after the platform cut. Math only."""
    if sale_price_usd < 0:
        raise ValueError("sale price cannot be negative")
    return round(sale_price_usd * (1 - PLATFORM_CUT), 2)
