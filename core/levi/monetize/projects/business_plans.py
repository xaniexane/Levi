"""Project 12 — Business plan & pitch deck service.

Income mechanism: per-plan fees ($75-$250) + pitch-deck add-ons, with a
bank-ready SBA format at a premium. LEVI works offline: intake
questionnaire, plan skeletons, deck outlines, 3-year projection math.
The narrative writing, financial sanity-check, and delivery are
Chauncey-gated — a funding document carries the owner's story, and
projections must be realistic, never fantasy.

Risk band: low — paid per deliverable; but the reputational bar is the
highest of the 12.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "business-plans",
    "name": "Business Plan & Pitch Deck Service",
    "automation": "semi",
    "setup_hours": 1,
    "days_to_first_dollar": "7-14",
    "daily_time_min": "25-40 per order",
    "month3_range": (600, 1200),
    "risk_band": "low",
    "mechanism": "Per-plan fees; pitch deck add-on; SBA bank-ready format.",
    "pricing": {
        "basic": {
            "price": 75,
            "pages": "10-15",
            "delivery": "48h",
            "includes": "plan without projections",
        },
        "standard": {
            "price": 150,
            "pages": "20-25",
            "delivery": "24h",
            "includes": "full 3-year projections",
        },
        "premium": {
            "price": 250,
            "pages": "30+",
            "delivery": "24h",
            "includes": "full financials + pitch deck",
        },
        "sba": {
            "price": 200,
            "pages": "SBA format",
            "delivery": "48h",
            "includes": "bank-ready required sections",
        },
        "deck_addon": {
            "price": (50, 75),
            "pages": "12 slides",
            "delivery": "24h",
            "includes": "investor pitch deck",
        },
        "revision": {
            "price": 25,
            "pages": "-",
            "delivery": "24h",
            "includes": "one revision round",
        },
    },
    "chauncey_gated": [
        "Client fills the intake form — their business, their numbers.",
        "You write and sanity-check every section; projections must be defensible.",
        "Deliver as PDF; confirm payment before logging.",
    ],
}

INTAKE_QUESTIONS = [
    "Business name and one-line description",
    "Product or service description",
    "Target market and customer profile",
    "Revenue model (how money is made)",
    "Main competitors and your edge",
    "3-year goals",
    "Funding amount needed",
    "Intended use of funds (detailed breakdown)",
    "Owner's professional background",
]

PLAN_SECTIONS = [
    "Executive Summary",
    "Company Description",
    "Market Analysis",
    "Products and Services",
    "Marketing and Sales Strategy",
    "Operational Plan",
    "Management Team and Qualifications",
    "Financial Projections (3-year)",
    "Funding Request",
    "Exit Strategy",
]

DECK_SLIDES = [
    "Title",
    "Problem",
    "Solution",
    "Market size",
    "Product",
    "Business model",
    "Traction",
    "Go-to-market",
    "Competition",
    "Team",
    "Financials",
    "The ask",
]


def intake_form() -> List[str]:
    """The client questionnaire — offline artifact, client fills it."""
    return list(INTAKE_QUESTIONS)


def plan_skeleton(business_name: str) -> Dict:
    return {
        "business": business_name,
        "sections": [
            {"section": s, "status": "draft", "owner": "Chauncey writes/reviews"}
            for s in PLAN_SECTIONS
        ],
        "status": "skeleton — writing is a Chauncey-gated step",
    }


def pitch_deck_outline(business_name: str) -> Dict:
    return {
        "business": business_name,
        "slides": [{"slide": n + 1, "title": t} for n, t in enumerate(DECK_SLIDES)],
        "note": "One idea per slide; visuals designed after copy is approved.",
    }


def projections_3yr(year1_revenue: float, growth_rates: List[float]) -> Dict:
    """Simple 3-year revenue projection table. Rates are Chauncey's judgment calls."""
    if year1_revenue < 0:
        raise ValueError("year1_revenue must be >= 0")
    if len(growth_rates) != 2 or any(g < -1 for g in growth_rates):
        raise ValueError("growth_rates must be 2 rates >= -1 (e.g. [0.5, 0.3])")
    y1 = round(year1_revenue, 2)
    y2 = round(y1 * (1 + growth_rates[0]), 2)
    y3 = round(y2 * (1 + growth_rates[1]), 2)
    return {
        "year_1": y1,
        "year_2": y2,
        "year_3": y3,
        "assumptions": f"Y1={y1}, growth {growth_rates[0]:.0%} then {growth_rates[1]:.0%}",
        "warning": "Projections are estimates, not promises. Never present as guaranteed.",
    }


def quote(package: str, deck_addon: bool = False) -> Dict:
    if package not in PROJECT["pricing"]:
        raise ValueError(
            f"unknown package {package!r}; choose from {sorted(PROJECT['pricing'])}"
        )
    pkg = PROJECT["pricing"][package]
    if package == "deck_addon":
        return {"package": package, "price_range": pkg["price"]}
    price = pkg["price"]
    if deck_addon and package not in ("premium", "deck_addon"):
        lo, hi = PROJECT["pricing"]["deck_addon"]["price"]
        return {"package": package, "price": price, "deck_addon_range": (lo, hi)}
    return {
        "package": package,
        "price": price,
        "delivery": pkg["delivery"],
        "pages": pkg["pages"],
    }


def log_sale(
    client: str, package: str, amount: float, note: str = "", home=None
) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=amount,
        note=note or f"{package} plan — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Save the intake form and plan skeleton as your order template.",
            "gated": False,
        },
        {
            "step": "Create the marketplace listing; offer first 3 orders at 50% off for reviews.",
            "gated": True,
        },
        {
            "step": "Per order: intake -> draft -> Chauncey review -> PDF delivery.",
            "gated": True,
        },
    ]
