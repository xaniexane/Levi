"""Project 03 — Print-on-demand storefront (Etsy + Printify style).

Income mechanism: margin between retail price and print-provider base
cost, per unit sold. LEVI does offline work: margin math, design-brief
generation, and catalog tracking. Store/account setup, design uploads,
and listing publishing are Chauncey-gated.

Risk band: elevated — platform fees and marketplace competition can
erase thin margins; margins are computed before any spend.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "print-on-demand",
    "name": "Print-on-Demand Storefront",
    "automation": "full",
    "setup_hours": "4-6",
    "days_to_first_dollar": "14-28",
    "daily_time_min": "5-10",
    "month3_range": (200, 500),
    "risk_band": "elevated",
    "mechanism": "Per-unit margin on printed merchandise; fulfillment handled by the provider.",
    "products": {
        "tshirt": {"base_cost": 13.45, "retail": 24.99, "label": "unisex t-shirt"},
        "mug": {"base_cost": 7.49, "retail": 16.99, "label": "ceramic mug"},
        "tote": {"base_cost": 9.95, "retail": 19.99, "label": "tote bag"},
    },
    "chauncey_gated": [
        "Create the marketplace seller account and connect the print provider (your identity, your tax info).",
        "Upload designs and publish listings.",
        "Withdraw payouts to your own bank/payment account.",
    ],
}

NICHES = [
    "motivational text designs",
    "occupation humor (nurse, teacher, trucker)",
    "local pride (hometown/city designs)",
    "automation/tech humor",
    "pet breeds with funny captions",
]


def margin(product: str, retail: float | None = None) -> Dict:
    """Unit economics for one product at a given retail price."""
    if product not in PROJECT["products"]:
        raise ValueError(
            f"unknown product {product!r}; choose from {sorted(PROJECT['products'])}"
        )
    spec = PROJECT["products"][product]
    price = retail if retail is not None else spec["retail"]
    if price <= 0:
        raise ValueError("retail must be positive")
    profit = price - spec["base_cost"]
    return {
        "product": product,
        "label": spec["label"],
        "base_cost": spec["base_cost"],
        "retail": round(price, 2),
        "unit_profit": round(profit, 2),
        "margin_pct": round(100 * profit / price, 1),
    }


def catalog_forecast(items: List[Dict]) -> Dict:
    """Projected monthly profit from a list of {product, retail?, units} entries."""
    total_profit = 0.0
    total_units = 0
    lines = []
    for item in items:
        m = margin(item["product"], item.get("retail"))
        units = int(item.get("units", 0))
        line_profit = round(m["unit_profit"] * units, 2)
        lines.append(
            {"product": item["product"], "units": units, "profit": line_profit}
        )
        total_profit += line_profit
        total_units += units
    return {
        "lines": lines,
        "total_units": total_units,
        "total_profit": round(total_profit, 2),
        "note": "Gross margin before marketplace fees (~6-8%) and ad spend.",
    }


def design_brief(niche: str, product: str, concept: str) -> Dict:
    """Structured design brief: the offline planning artifact before Chauncey designs."""
    if product not in PROJECT["products"]:
        raise ValueError(f"unknown product {product!r}")
    return {
        "niche": niche,
        "product": product,
        "concept": concept,
        "specs": "transparent PNG, 300 DPI, sized for the product print area",
        "listing_tasks": [
            "Write keyword-optimized title with searchable terms.",
            "Write 5-bullet description.",
            "Attach 13 marketplace tags.",
        ],
        "unit_economics": margin(product),
        "status": "brief — needs Chauncey to create the artwork",
    }


def log_payout(amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="payout",
        amount=amount,
        note=note or "marketplace payout received",
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Pick a niche from NICHES; run margin() on your products.",
            "gated": False,
        },
        {"step": "Write 10 design briefs with design_brief().", "gated": False},
        {
            "step": "Create the marketplace seller account (your identity).",
            "gated": True,
        },
        {"step": "Connect the print provider; upload first 10 designs.", "gated": True},
        {"step": "Publish listings with optimized titles/tags.", "gated": True},
    ]
