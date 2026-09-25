"""Registry of the 12 monetization projects."""

from __future__ import annotations

from typing import Dict, List

from . import (
    business_plans,
    chatbot_service,
    data_scraping,
    kdp_publishing,
    lead_generation,
    newsletter,
    podcast_notes,
    print_on_demand,
    resume_service,
    social_media,
    whatsapp_automation,
    youtube_faceless,
)

MODULES = [
    resume_service,
    social_media,
    print_on_demand,
    kdp_publishing,
    youtube_faceless,
    chatbot_service,
    lead_generation,
    newsletter,
    data_scraping,
    whatsapp_automation,
    podcast_notes,
    business_plans,
]

REGISTRY: Dict[str, Dict] = {m.PROJECT["slug"]: m.PROJECT for m in MODULES}
BY_SLUG = {m.PROJECT["slug"]: m for m in MODULES}


def list_projects() -> List[Dict]:
    """The 12 projects in order, as descriptor dicts."""
    return [m.PROJECT for m in MODULES]


def get(slug: str) -> Dict:
    if slug not in REGISTRY:
        raise ValueError(f"unknown project {slug!r}; choose from {sorted(REGISTRY)}")
    return REGISTRY[slug]


def get_module(slug: str):
    if slug not in BY_SLUG:
        raise ValueError(f"unknown project {slug!r}; choose from {sorted(BY_SLUG)}")
    return BY_SLUG[slug]


def total_month3_range() -> Dict:
    lo = sum(m.PROJECT["month3_range"][0] for m in MODULES)
    hi = sum(m.PROJECT["month3_range"][1] for m in MODULES)
    return {
        "month3_conservative": lo,
        "month3_ceiling": hi,
        "note": "Sum of per-project ranges; running all 12 at once is not advised.",
    }
