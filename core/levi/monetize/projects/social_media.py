"""Project 02 — Social media management for local businesses.

Income mechanism: monthly retainers for a set number of posts per week.
LEVI handles the drudgery offline: content-calendar generation, tier
quoting, and per-client workload math. Posting to client accounts and
invoicing are Chauncey-gated.

Risk band: medium — recurring revenue, but client churn is real and the
work touches someone else's brand.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "social-media",
    "name": "Social Media Management",
    "automation": "semi",
    "setup_hours": "3-4 per client",
    "days_to_first_dollar": "3-7",
    "daily_time_min": "30-45 (up to 5 clients)",
    "month3_range": (600, 1000),
    "risk_band": "medium",
    "mechanism": "Monthly retainers: 3-5 scheduled posts/week per local business.",
    "pricing": {
        "starter": {
            "price": 100,
            "posts_per_week": 3,
            "platforms": ["instagram"],
            "revisions": 1,
        },
        "growth": {
            "price": 175,
            "posts_per_week": 5,
            "platforms": ["instagram", "facebook"],
            "revisions": 2,
        },
        "premium": {
            "price": 275,
            "posts_per_week": 7,
            "platforms": ["instagram", "facebook", "stories"],
            "revisions": "unlimited + monthly report",
        },
        "reel_addon": {
            "price": 50,
            "posts_per_week": 2,
            "platforms": ["any"],
            "revisions": 1,
        },
    },
    "chauncey_gated": [
        "Sign each client and get their brand assets + account access.",
        "Schedule/post content on their accounts (their credentials).",
        "Send the monthly report and invoice.",
    ],
}

_POST_MIX = [
    ("promotional", "Offer, product, or service highlight with a clear CTA."),
    ("educational", "Tip, how-to, or behind-the-scenes from the trade."),
    ("community", "Local shout-out, customer story, or neighborhood tie-in."),
    ("promotional", "Seasonal offer or limited-time special."),
    ("educational", "Myth-busting or FAQ from the business."),
    ("community", "Staff spotlight or customer review feature."),
    ("promotional", "Repost of a top performer with a fresh caption."),
]


def content_calendar(
    business_type: str, posts_per_week: int, weeks: int = 4
) -> List[Dict]:
    """Generate a post calendar skeleton: rotating promo/educational/community mix."""
    if posts_per_week < 1 or posts_per_week > 7:
        raise ValueError("posts_per_week must be 1-7")
    if weeks < 1 or weeks > 12:
        raise ValueError("weeks must be 1-12")
    calendar = []
    idx = 0
    for week in range(1, weeks + 1):
        for day in range(1, posts_per_week + 1):
            kind, brief = _POST_MIX[idx % len(_POST_MIX)]
            calendar.append(
                {
                    "week": week,
                    "slot": day,
                    "business_type": business_type,
                    "kind": kind,
                    "brief": brief,
                    "status": "draft",
                }
            )
            idx += 1
    return calendar


def quote(tier: str, reel_addon: bool = False, months: int = 1) -> Dict:
    if tier not in PROJECT["pricing"]:
        raise ValueError(
            f"unknown tier {tier!r}; choose from {sorted(PROJECT['pricing'])}"
        )
    pkg = PROJECT["pricing"][tier]
    monthly = pkg["price"] + (
        PROJECT["pricing"]["reel_addon"]["price"] if reel_addon else 0
    )
    return {
        "tier": tier,
        "monthly": monthly,
        "total": monthly * months,
        "months": months,
        "posts_per_week": pkg["posts_per_week"],
        "platforms": pkg["platforms"],
    }


def add_client(
    name: str, business_type: str, tier: str, reel_addon: bool = False
) -> Dict:
    q = quote(tier, reel_addon)
    return {
        "client": name,
        "business_type": business_type,
        "tier": tier,
        "reel_addon": reel_addon,
        "monthly_retainer": q["monthly"],
        "calendar": content_calendar(business_type, q["posts_per_week"]),
        "status": "onboarding",
    }


def capacity_check(clients: int, minutes_per_client_week: int = 90) -> Dict:
    """Honest workload math: weekly minutes vs. a sustainable cap."""
    weekly = clients * minutes_per_client_week
    cap = 600  # ~10h/week ceiling for this stream
    return {
        "clients": clients,
        "weekly_minutes": weekly,
        "weekly_hours": round(weekly / 60, 1),
        "headroom_minutes": cap - weekly,
        "over_capacity": weekly > cap,
    }


def log_retainer(client: Dict, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="recurring",
        amount=client["monthly_retainer"],
        note=note or f"monthly retainer — {client['client']}",
        counterparty=client["client"],
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Build a sample calendar + 3 sample posts as your pitch demo.",
            "gated": False,
        },
        {"step": "Sign first client; collect brand assets and access.", "gated": True},
        {
            "step": "Generate their 30-day calendar with content_calendar().",
            "gated": False,
        },
        {
            "step": "Batch one week of captions + schedule via a scheduler.",
            "gated": True,
        },
        {"step": "Deliver monthly report; invoice; log the retainer.", "gated": True},
    ]
