"""Project 05 — Faceless video channel (tutorials, explainers).

Income mechanism: ad revenue per 1,000 views (RPM) once the platform's
monetization threshold is met. LEVI works offline: script outlines,
upload checklists, earnings estimates. Recording, editing, and uploading
under Chauncey's channel are Chauncey-gated.

Risk band: elevated — 30-90+ days before the first dollar; the
algorithm owes nothing.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "youtube-faceless",
    "name": "Faceless Video Channel",
    "automation": "semi",
    "setup_hours": "1 week initial",
    "days_to_first_dollar": "30-90",
    "daily_time_min": "45-60 during growth",
    "month3_range": (50, 300),
    "risk_band": "elevated",
    "mechanism": "Ad revenue per 1,000 views after monetization unlocks.",
    "monetization_threshold": {"subscribers": 1000, "watch_hours": 4000},
    "chauncey_gated": [
        "Create/own the channel (your identity).",
        "Record narration and screen captures; edit and upload.",
        "Respond to comments and community (your voice).",
    ],
}


def earnings_estimate(
    monthly_views: int, rpm_low: float = 0.5, rpm_high: float = 4.0
) -> Dict:
    """Ad-revenue range for a monthly view count at a niche RPM band."""
    if monthly_views < 0:
        raise ValueError("monthly_views must be >= 0")
    low = round(monthly_views / 1000 * rpm_low, 2)
    high = round(monthly_views / 1000 * rpm_high, 2)
    return {
        "monthly_views": monthly_views,
        "rpm_range": (rpm_low, rpm_high),
        "estimated_monthly": (low, high),
        "note": "RPM varies by niche and season; tutorials skew higher, vlogs lower.",
    }


def monetization_check(subscribers: int, watch_hours: int) -> Dict:
    t = PROJECT["monetization_threshold"]
    ok = subscribers >= t["subscribers"] and watch_hours >= t["watch_hours"]
    return {
        "eligible": ok,
        "subscribers": f"{subscribers}/{t['subscribers']}",
        "watch_hours": f"{watch_hours}/{t['watch_hours']}",
        "next": "Keep publishing: every video earns for years after upload."
        if not ok
        else "Apply for monetization; log ad payouts as they land.",
    }


def script_outline(topic: str, minutes: int = 10) -> Dict:
    """Video script skeleton: hook, problem, steps, surprise tip, CTA."""
    if not topic.strip():
        raise ValueError("topic must be non-empty")
    if minutes < 3 or minutes > 30:
        raise ValueError("minutes must be 3-30")
    return {
        "topic": topic,
        "target_minutes": minutes,
        "beats": [
            {
                "beat": "hook",
                "seconds": "0-30",
                "job": "State the payoff; stop the scroll.",
            },
            {"beat": "problem", "job": "Name the pain the viewer already feels."},
            {"beat": "steps", "job": "5-7 actionable steps, shown not told."},
            {"beat": "surprise tip", "job": "One thing most tutorials miss."},
            {"beat": "cta", "job": "Subscribe + next-video pointer."},
        ],
        "production": [
            "Chauncey: record voiceover + screen capture.",
            "Edit: auto-captions, trim dead space, text overlays for key points.",
            "Upload with an optimized title, description, and tags.",
        ],
        "status": "outline — recording is a Chauncey-gated step",
    }


def log_payout(amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="payout",
        amount=amount,
        note=note or "ad revenue payout received",
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Pick one niche; run script_outline() for your first 4 videos.",
            "gated": False,
        },
        {"step": "Create the channel (your identity).", "gated": True},
        {"step": "Record, edit, and upload the first 4 videos.", "gated": True},
        {
            "step": "Track subscribers/watch hours with monetization_check().",
            "gated": False,
        },
        {"step": "Apply for monetization when eligible; log payouts.", "gated": True},
    ]
