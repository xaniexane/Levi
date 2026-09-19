"""The sly-generosity pattern catalog.

Clean-room analyses from first principles (2026-09-16 evening hunt).
Each entry records: the gift as presented, the capture underneath, what
the giant refuses to give, and the honest inversion LEVI ships instead.

No proprietary source was fetched or copied; the facts below are the
publicly documented pattern mechanics.
"""

from __future__ import annotations

from typing import Dict, List, Optional

PATTERNS: List[Dict[str, object]] = [
    {
        "id": "walled-garden-generosity",
        "name": "Walled-garden generosity",
        "exemplar": (
            "Facebook Free Basics / Internet.org (2013-2016): free mobile "
            "access to a curated handful of sites — including Facebook's "
            "own — across 35+ developing countries. India's regulator "
            "(TRAI) banned zero-rating in February 2016; a similar program "
            "was shut down in Egypt."
        ),
        "the_generosity": "Free internet for the unconnected.",
        "the_capture": (
            "The donor draws the map: only their chosen services are free, "
            "so the 'internet' the newcomer meets is the donor's own walled "
            "garden. Philanthropy becomes user acquisition; the gift sets "
            "the boundaries of what the recipient is allowed to want."
        ),
        "what_they_refuse": "Open, neutral access — generosity with no leash.",
        "inversion": (
            "Give without a leash: a generous thing must survive with no "
            "capture attached. If the gift needs a fence to keep paying off, "
            "it was never a gift."
        ),
        "signals": [
            "free",
            "basic",
            "zero-rated",
            "curated",
            "approved",
            "walled",
            "select",
            "partner apps",
            "charity",
            "connecting the unconnected",
        ],
    },
    {
        "id": "asymmetric-rules",
        "name": "Asymmetric rules (privacy as a weapon)",
        "exemplar": (
            "Apple's App Tracking Transparency (from iOS 14.5, 2021): "
            "third-party apps must beg for tracking permission via a "
            "scary prompt, while Apple's own ad system stays exempt — its "
            "Personalized Ads setting is on by default with no such prompt. "
            "France's competition authority fined Apple €150M in 2025 for "
            "the implementation; SMEs lost up to ~37% revenue growth on "
            "Meta-optimized campaigns per a 2025 Hamburg study."
        ),
        "the_generosity": "Privacy for the user.",
        "the_capture": (
            "The rule binds everyone except the rule-maker. A platform that "
            "controls the prompt gets to write the terms of the market: "
            "competitors bleed data while the platform's own first-party "
            "data — exempt from its own rule — becomes more valuable."
        ),
        "what_they_refuse": "Symmetrical rules — one standard that binds the platform too.",
        "inversion": (
            "The rule-maker obeys the rule: any privacy, consent, or data "
            "policy LEVI enforces on others binds LEVI's own components "
            "identically. Asymmetry is the tell of a weapon."
        ),
        "signals": [
            "privacy",
            "transparency",
            "exempt",
            "first-party",
            "our own",
            "platform policy",
            "compliance",
            "except us",
            "opt-in",
        ],
    },
    {
        "id": "roach-motel-funnel",
        "name": "Roach-motel funnel",
        "exemplar": (
            "Amazon Prime enrollment/cancellation (FTC sued June 2023): "
            "checkout buttons that enrolled shoppers without clearly saying "
            "so; a cancellation flow so long Amazon itself codenamed it the "
            "'Iliad Flow' — after a 16,000-line epic. 200M+ members, "
            "$139/yr; the FTC alleged leadership slowed or rejected changes "
            "that would have made leaving easier."
        ),
        "the_generosity": "One-click convenience — try it free, stay for the perks.",
        "the_capture": (
            "Friction is weaponized in one direction: entering is "
            "frictionless (or accidental), exiting is a siege. The product's "
            "retention is not earned by value but manufactured by fatigue — "
            "the customer keeps paying because quitting costs more effort "
            "than another year."
        ),
        "what_they_refuse": "Symmetric friction — leaving as easy as joining.",
        "inversion": (
            "Symmetric friction: any action LEVI makes easy to start must "
            "be equally easy to stop. The exit is tested first; if leaving "
            "is harder than joining, the design is rejected."
        ),
        "signals": [
            "free trial",
            "cancel",
            "subscription",
            "retention",
            "easy to join",
            "one click",
            "opt-out",
            "auto-renew",
            "funnel",
            "maze",
        ],
    },
    {
        "id": "manufactured-social-debt",
        "name": "Manufactured social debt",
        "exemplar": (
            "Snapchat Streaks: a counter rewarding friends who message each "
            "other every single day. A 2023 Antwerp study of 2,483 early "
            "adolescents linked streaks to problematic smartphone use and "
            "FOMO; Egyptian teen research found emotional distress at "
            "losing streaks. The mechanic converts a voluntary friendship "
            "into a daily obligation owed partly to the platform."
        ),
        "the_generosity": "A playful score celebrating your friendships.",
        "the_capture": (
            "Reciprocity and loss aversion — real human wiring — are "
            "repurposed as a retention engine. Missing one day destroys the "
            "number, so the user serves the score instead of the friend; "
            "the 'game' cannot be paused, so a sick day or a holiday "
            "becomes a punishment."
        ),
        "what_they_refuse": "Pausable, forgiving, opt-in play — joy without obligation.",
        "inversion": (
            "Obligation-free play: LEVI never turns voluntary use into a "
            "debt. Streak-like mechanics, where they exist, are pausable, "
            "never punish a gap, and the score belongs to the player — "
            "exportable, erasable, never held hostage."
        ),
        "signals": [
            "streak",
            "daily",
            "don't break",
            "fomo",
            "miss out",
            "score",
            "level",
            "every day",
            "consecutive",
            "obligation",
            "reminder",
        ],
    },
]


def pattern_ids() -> List[str]:
    return [p["id"] for p in PATTERNS]


def get_pattern(pattern_id: str) -> Optional[Dict[str, object]]:
    for p in PATTERNS:
        if p["id"] == pattern_id:
            return p
    return None
