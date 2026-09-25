"""Project 08 — Niche newsletter business.

Income mechanism: sponsor placements + affiliate commissions, unlocked
by subscriber count. LEVI works offline: issue templates, subscriber
milestone math, sponsor-rate estimates. Account setup, writing, and
sponsor outreach are Chauncey-gated.

Risk band: elevated — 30-90 days of content before meaningful income;
list growth is the whole game.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "newsletter",
    "name": "Newsletter Business",
    "automation": "full",
    "setup_hours": "2-3 days",
    "days_to_first_dollar": "30-90",
    "daily_time_min": "30-45 per issue, 2-3x/week",
    "month3_range": (100, 300),
    "risk_band": "elevated",
    "mechanism": "Ad-network revenue + affiliate links + direct sponsors per issue.",
    "chauncey_gated": [
        "Create the newsletter account (your identity).",
        "Write and approve every issue — your voice, your reputation.",
        "Negotiate and accept sponsor deals.",
    ],
}

ISSUE_STRUCTURE = [
    "intro (2 sentences)",
    "main story or tip (300-400 words)",
    "3 quick bullet tips",
    "1 tool recommendation",
    "1 income case study or update",
    "3 subject-line options",
]


def issue_template(topic: str) -> Dict:
    """The offline skeleton for one issue; writing stays Chauncey-gated."""
    if not topic.strip():
        raise ValueError("topic must be non-empty")
    return {
        "topic": topic,
        "structure": ISSUE_STRUCTURE,
        "sections": {s: "" for s in ISSUE_STRUCTURE},
        "status": "template — Chauncey writes the content",
    }


def monetization_tier(subscribers: int) -> Dict:
    """What unlocks at a subscriber count: honest thresholds."""
    if subscribers < 0:
        raise ValueError("subscribers must be >= 0")
    unlocked = []
    if subscribers >= 500:
        unlocked.append("ad network placements (revenue per 1,000 sends)")
    if subscribers >= 1000:
        unlocked.append("affiliate links compounding per issue")
    if subscribers >= 2500:
        unlocked.append("direct sponsors: ~$25-100 per sponsor per issue")
    if subscribers >= 5000:
        unlocked.append("premium direct sponsors: ~$200-500 per sponsor per issue")
    return {
        "subscribers": subscribers,
        "unlocked": unlocked,
        "next_milestone": next(
            (m for m in (500, 1000, 2500, 5000) if subscribers < m), None
        ),
    }


def sponsor_quote(subscribers: int, sponsors_per_issue: int = 1) -> Dict:
    """Estimate per-issue sponsor revenue at a subscriber count."""
    tier = monetization_tier(subscribers)
    if subscribers < 2500:
        low, high = 25, 100
    else:
        low, high = 200, 500
    return {
        "subscribers": subscribers,
        "sponsors_per_issue": sponsors_per_issue,
        "per_issue_range": (low * sponsors_per_issue, high * sponsors_per_issue),
        "unlocked": tier["unlocked"],
    }


def log_sponsor(amount: float, sponsor: str = "", note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=amount,
        note=note or f"sponsor placement — {sponsor}",
        counterparty=sponsor,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {"step": "Draft 3 complete issues before promoting anything.", "gated": False},
        {
            "step": "Create the newsletter account; add the subscribe link to your bios.",
            "gated": True,
        },
        {"step": "Publish on a fixed schedule (e.g. weekly).", "gated": True},
        {"step": "At 500+ subscribers: enable ad-network placements.", "gated": True},
        {
            "step": "At 1k+: add affiliate links; at 2.5k+: pitch direct sponsors.",
            "gated": True,
        },
    ]
