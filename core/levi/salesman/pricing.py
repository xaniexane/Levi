"""Pricing engine — max / fast / floor from cost basis and condition.

Aggressive doesn't mean greedy: the fast-sale price moves inventory in days,
the max price works the patient buyer, and the floor is the line the closer
never crosses without Chauncey (L3).
"""

from __future__ import annotations

from typing import Dict

from levi.salesman import Item

# Condition multiplier on realistic resale (fraction of retail).
_CONDITION_MULT = {
    "new": 0.75,
    "like-new": 0.60,
    "used-good": 0.50,
    "used-fair": 0.35,
    "parts": 0.15,
}

_MIN_MARGIN_MULT = 2.0  # floor must at least double cost basis when basis > 0


def realistic_resale(item: Item) -> float:
    """Best honest estimate of what the item sells for, from intake facts only."""
    if item.retail_price and item.retail_price > 0:
        base = item.retail_price * _CONDITION_MULT[item.condition]
    else:
        # No retail anchor: work off cost basis with a modest multiple.
        base = item.cost_basis * 4.0 if item.cost_basis > 0 else 20.0
    return round(max(base, 1.0), 2)


def price_ladder(item: Item) -> Dict[str, float]:
    """Return {max, fast, floor}. L3: floor is hard — closer never goes under."""
    realistic = realistic_resale(item)
    max_price = round(realistic * 1.15, 2)
    fast_price = round(realistic * 0.85, 2)
    if item.cost_basis > 0:
        floor = round(max(item.cost_basis * _MIN_MARGIN_MULT, realistic * 0.60), 2)
    else:
        floor = round(realistic * 0.60, 2)
    # Keep the ladder ordered: floor <= fast <= max
    floor = min(floor, fast_price)
    return {"max": max_price, "fast": fast_price, "floor": floor}


def bundle_price(items_ladder: Dict[str, Dict[str, float]], discount: float = 0.20) -> Dict[str, float]:
    """Bundle pricing: 10-35% off the sum of fast prices (gem's bundle rule)."""
    if not 0.10 <= discount <= 0.35:
        raise ValueError("bundle discount must be 0.10-0.35")
    total_fast = sum(lad["fast"] for lad in items_ladder.values())
    total_floor = sum(lad["floor"] for lad in items_ladder.values())
    bundle = round(total_fast * (1 - discount), 2)
    return {"bundle": max(bundle, total_floor), "floor": total_floor}
