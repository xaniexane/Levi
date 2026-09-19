"""Project 11 — Podcast show-notes & transcript service.

Income mechanism: per-episode fees plus monthly retainers for weekly
shows. LEVI works offline: package quoting, timestamp helpers,
deliverable checklists. Transcription uses free local tooling where
possible; client audio and final review are Chauncey-gated.

Risk band: low — paid per delivered episode, no inventory, no platform
lock-in.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "podcast-notes",
    "name": "Podcast Show Notes Service",
    "automation": "full",
    "setup_hours": 3,
    "days_to_first_dollar": "7-14",
    "daily_time_min": "10-15 per order",
    "month3_range": (300, 600),
    "risk_band": "low",
    "mechanism": "Per-episode packages + monthly retainers for weekly podcasts.",
    "pricing": {
        "basic": {"price": 15, "delivery": "24h", "includes": "show-notes summary"},
        "standard": {
            "price": 25,
            "delivery": "24h",
            "includes": "summary + timestamps + pull quotes",
        },
        "premium": {
            "price": 40,
            "delivery": "24h",
            "includes": "everything + SEO blog post + resource list",
        },
        "retainer_weekly": {
            "price": (80, 150),
            "delivery": "ongoing",
            "includes": "4 episodes/month",
        },
    },
    "chauncey_gated": [
        "Client sends the audio; you confirm the package and deadline.",
        "Review the transcript-derived notes before delivery.",
        "Deliver and confirm payment before logging.",
    ],
}

DELIVERABLES = [
    "3-paragraph show-notes summary",
    "5-7 key timestamps with short descriptions",
    "5 pull quotes worth sharing",
    "resource/tool list from the episode",
    "400-word SEO blog post (premium)",
]


def format_timestamp(seconds: int) -> str:
    """Seconds -> H:MM:SS chapter marker."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def chapter_list(marks: List[Dict]) -> List[str]:
    """marks: [{"seconds": 123, "label": "..."}] -> formatted chapter lines."""
    lines = []
    for mark in marks:
        lines.append(f"{format_timestamp(mark['seconds'])} — {mark['label']}")
    return lines


def quote(package: str, episodes: int = 1) -> Dict:
    if package not in PROJECT["pricing"]:
        raise ValueError(
            f"unknown package {package!r}; choose from {sorted(PROJECT['pricing'])}"
        )
    pkg = PROJECT["pricing"][package]
    if package == "retainer_weekly":
        lo, hi = pkg["price"]
        return {
            "package": package,
            "monthly_range": (lo, hi),
            "includes": pkg["includes"],
        }
    return {
        "package": package,
        "per_episode": pkg["price"],
        "episodes": episodes,
        "total": pkg["price"] * episodes,
        "delivery": pkg["delivery"],
        "includes": pkg["includes"],
    }


def create_order(client: str, episode_title: str, package: str) -> Dict:
    q = quote(package)
    return {
        "client": client,
        "episode_title": episode_title,
        "package": package,
        "price": q.get("total", q.get("monthly_range")),
        "status": "draft",
        "workflow": [
            "Receive audio from the client.",
            "Transcribe (free local tooling first; cloud only if the client agrees).",
            "Generate deliverables from the transcript.",
            "Chauncey reviews; package in a clean document; deliver.",
        ],
        "deliverables": DELIVERABLES,
    }


def log_sale(order: Dict, note: str = "", home=None) -> Dict:
    price = order["price"] if isinstance(order["price"], (int, float)) else 0
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=price,
        note=note
        or f"{order['package']} — {order['episode_title']} for {order['client']}",
        counterparty=order["client"],
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Test the transcript->notes workflow on a sample episode.",
            "gated": False,
        },
        {
            "step": "Create the marketplace listing with the 3 package tiers.",
            "gated": True,
        },
        {
            "step": "Offer a free sample episode to the first 3 prospects.",
            "gated": True,
        },
        {"step": "Convert happy one-off clients to weekly retainers.", "gated": True},
    ]
