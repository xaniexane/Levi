"""Prospect engine — who buys this, where, and when to strike.

Pure heuristics from the item's category: no tracking, no scraped data.
Timing guidance matches the flip playbook (Thursday evening posts get eyes).
"""

from __future__ import annotations

from typing import Dict, List

_CATEGORY_INTEL: Dict[str, Dict[str, object]] = {
    "tools": {
        "buyer": "DIYers, contractors, flippers — they don't haggle much, they need it now",
        "platforms": ["marketplace", "x"],
        "best_days": ["Thursday", "Friday", "Saturday"],
        "pitch_angle": "utility",
    },
    "appliances": {
        "buyer": "renters, new homeowners, parents furnishing on a budget",
        "platforms": ["marketplace", "vinted"],
        "best_days": ["Thursday", "Sunday"],
        "pitch_angle": "value",
    },
    "home": {
        "buyer": "homeowners refreshing rooms, organizers, gift buyers",
        "platforms": ["marketplace", "vinted"],
        "best_days": ["Thursday", "Sunday"],
        "pitch_angle": "lifestyle",
    },
    "toys": {
        "buyer": "parents, grandparents, collectors — seasonal spikes before holidays",
        "platforms": ["marketplace", "tiktok"],
        "best_days": ["Friday", "Saturday", "Sunday"],
        "pitch_angle": "excitement",
    },
    "baby": {
        "buyer": "new parents buying in bundles — always pitch the bundle",
        "platforms": ["marketplace", "vinted"],
        "best_days": ["Thursday", "Saturday"],
        "pitch_angle": "bundle",
    },
    "electronics": {
        "buyer": "deal hunters and tech flippers — expect testing questions, answer fast",
        "platforms": ["marketplace", "x"],
        "best_days": ["Thursday", "Friday"],
        "pitch_angle": "specs",
    },
    "clothing": {
        "buyer": "style hunters, size-specific — photos carry the sale",
        "platforms": ["vinted", "tiktok", "marketplace"],
        "best_days": ["Friday", "Saturday"],
        "pitch_angle": "style",
    },
    "general": {
        "buyer": "Marketplace browsers — hook them in the first line",
        "platforms": ["marketplace", "x"],
        "best_days": ["Thursday", "Friday", "Saturday"],
        "pitch_angle": "value",
    },
}


def prospect(category: str) -> Dict[str, object]:
    intel = _CATEGORY_INTEL.get(category.lower(), _CATEGORY_INTEL["general"])
    return {
        "category": category,
        "buyer": intel["buyer"],
        "platforms": list(intel["platforms"]),  # type: ignore[arg-type]
        "best_days": list(intel["best_days"]),  # type: ignore[arg-type]
        "pitch_angle": intel["pitch_angle"],
        "post_time": "Thursday ~8:30 PM local — weekend pickup planners are scrolling",
    }


def pitch_openers(category: str) -> List[str]:
    """Aggressive openers per pitch angle. L1-safe: no false claims, pure hooks."""
    angle = prospect(category)["pitch_angle"]
    return {
        "utility": [
            "Stop renting tools — own this one for less than a weekend rental.",
            "Contractors pay double. You don't have to.",
        ],
        "value": [
            "Retail is a suggestion. This price is the reality.",
            "Why pay full price when this does the exact same job?",
        ],
        "lifestyle": [
            "Your kitchen deserves better than what you've got.",
            "This is the upgrade you've been putting off — today's the day.",
        ],
        "excitement": [
            "Your kid's face when they open this > the price tag. Every time.",
            "Birthday solved. You're welcome.",
        ],
        "bundle": [
            "One pickup, everything handled — bundle pricing inside.",
            "Buying one is smart. Buying the bundle is genius.",
        ],
        "specs": [
            "Tested. Working. Priced like I want it gone today.",
            "Specs don't lie — and neither does this price.",
        ],
        "style": [
            "This won't sit here long. Good pieces never do.",
            "Your closet called — it wants this.",
        ],
    }[angle]  # type: ignore[index]
