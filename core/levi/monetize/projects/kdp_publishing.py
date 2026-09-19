"""Project 04 — Self-published books (Kindle Direct Publishing style).

Income mechanism: royalties per sale, compounding across a catalog.
LEVI works offline: royalty math, book-outline skeletons, catalog
tracking. Writing, cover design, and publishing under Chauncey's
author account are Chauncey-gated.

Honest note: LEVI assists drafting; quality review and originality are
Chauncey's job — marketplaces penalize low-effort catalogs.

Risk band: elevated — long ramp, platform-dependent, review risk.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "kdp-publishing",
    "name": "Self-Published Books",
    "automation": "semi",
    "setup_hours": "3-5 days per book",
    "days_to_first_dollar": "14-30",
    "daily_time_min": "30-60 during creation, ~5 after",
    "month3_range": (150, 400),
    "risk_band": "elevated",
    "mechanism": "Per-sale royalties (35-70%) compounding across a growing catalog.",
    "pricing": {"ebook": (2.99, 9.99), "paperback": (8.99, 16.99)},
    "chauncey_gated": [
        "Publish under your author account (your identity, your tax forms).",
        "Write/review every manuscript — you own the quality and originality.",
        "Design the cover and upload the final files.",
    ],
}


def royalty(price: float, ebook: bool = True, print_cost: float = 0.0) -> Dict:
    """Estimate per-sale royalty for a list price."""
    if price <= 0:
        raise ValueError("price must be positive")
    if ebook:
        # 70% band for the standard $2.99-$9.99 window, 35% outside it.
        rate = 0.70 if 2.99 <= price <= 9.99 else 0.35
        per_sale = round(price * rate, 2)
        band = "70%" if rate == 0.70 else "35%"
    else:
        # Simplified paperback: 60% of (price - print cost).
        rate = 0.60
        per_sale = round(max(0.0, (price - print_cost)) * rate, 2)
        band = "60% of net"
    return {
        "price": round(price, 2),
        "rate_band": band,
        "royalty_per_sale": per_sale,
        "ebook": ebook,
    }


def catalog_earnings(books: List[Dict]) -> Dict:
    """Compound catalog projection from [{price, ebook, monthly_sales}]."""
    total = 0.0
    lines = []
    for b in books:
        r = royalty(b["price"], b.get("ebook", True), b.get("print_cost", 0.0))
        monthly = round(r["royalty_per_sale"] * int(b.get("monthly_sales", 0)), 2)
        lines.append({"title": b.get("title", "untitled"), **r, "monthly": monthly})
        total += monthly
    return {"books": lines, "catalog_monthly": round(total, 2)}


def outline_skeleton(title: str, audience: str, chapters: int = 9) -> Dict:
    """Chapter skeleton: the offline planning artifact before writing."""
    if chapters < 3 or chapters > 15:
        raise ValueError("chapters must be 3-15")
    skeleton = [
        {"chapter": "Introduction", "goal": f"Promise the outcome to {audience}."},
    ]
    for n in range(1, chapters + 1):
        skeleton.append(
            {
                "chapter": f"Chapter {n}",
                "goal": "One actionable idea + 2-3 immediate steps.",
                "sections": ["concept", "walkthrough", "action steps"],
            }
        )
    skeleton.append({"chapter": "Conclusion", "goal": "Recap, next steps, resources."})
    return {
        "title": title,
        "audience": audience,
        "chapters": skeleton,
        "production_steps": [
            "Draft one chapter per session (1,500-2,000 words).",
            "Chauncey: review every chapter for accuracy and originality.",
            "Format manuscript; design cover; publish under your account.",
            "Track royalties; log payouts as they land.",
        ],
        "status": "skeleton — writing is a Chauncey-gated step",
    }


def log_payout(amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="payout",
        amount=amount,
        note=note or "royalty payout received",
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Pick one niche and run outline_skeleton() for the first title.",
            "gated": False,
        },
        {
            "step": "Fastest first dollar: a low-content planner/journal, not a full book.",
            "gated": False,
        },
        {"step": "Write the manuscript (Chauncey authors/reviews).", "gated": True},
        {"step": "Design cover; publish under your author account.", "gated": True},
        {"step": "Log royalty payouts monthly.", "gated": True},
    ]
