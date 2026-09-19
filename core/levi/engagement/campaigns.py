"""Campaigns — informational drives that keep users in the loop.

A campaign is a short series of cards: feature spotlights, security
tips, drop announcements. Delivered on the user's terms — dismissable
at any point, never re-shown once dismissed or completed. Viewing a
campaign records metadata only (which cards were seen); completing one
reports aggregate learnings to DemandPulse like surveys do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Card:
    title: str
    body: str


@dataclass
class Campaign:
    id: str
    title: str
    tagline: str
    cards: List[Card] = field(default_factory=list)


CAMPAIGNS: Dict[str, Campaign] = {}


def _reg(c: Campaign) -> Campaign:
    CAMPAIGNS[c.id] = c
    return c


_reg(
    Campaign(
        id="drop-01-tour",
        title="Drop One Tour",
        tagline="what's shippable today — and where it all lands",
        cards=[
            Card(
                "Rolling drops, not one big launch",
                "Levi ships continuously, year-round, on three tracks: "
                "services, SI, AI agents. Every capability is its own MVP "
                "drop and keeps improving in place. Nothing waits on "
                "everything — that's the whole point.",
            ),
            Card(
                "Services track — work you can buy",
                "Analyze → quote → deliver → paid → showcase. Bounty hunts, "
                "site lifts, cyber audits, the job search as a service. "
                "Money moves through Cybrus only — one gate, fail-closed, "
                "audited.",
            ),
            Card(
                "SI track — the mind itself",
                "Companion chat, the Cybrus vault, DemandPulse sensing what "
                "the world needs, Oracle weighing which move matters. Your "
                "answers to the surveys feed the hub — in aggregate, never "
                "your words.",
            ),
            Card(
                "Agents track — the legion",
                "490 seats across four waves, UniForge the code surgeon, the "
                "daemon keeping the organism breathing. Take the Feature "
                "Hunt survey and tell the hub which division to tour first.",
            ),
            Card(
                "Everything circles back to the hub",
                "The drops are the familiarization phase: standalone, "
                "introductory, yours to play with. What you use, skip, and "
                "love teaches DemandPulse — and the next drops follow the "
                "signal. You're not a user here. You're a co-conspirator.",
            ),
        ],
    )
)


def get_campaign(campaign_id: str) -> Optional[Campaign]:
    return CAMPAIGNS.get(campaign_id)


def view_campaign(campaign: Campaign, store: "EngagementStore | None" = None) -> Dict:
    """Render campaign cards interactively. Dismiss anytime with 'skip'."""
    print(f"\n== {campaign.title} ==")
    print(campaign.tagline + "\n")
    seen = 0
    for i, card in enumerate(campaign.cards, 1):
        print(f"  [{i}/{len(campaign.cards)}] {card.title}")
        print(f"  {card.body}\n")
        if i < len(campaign.cards):
            try:
                raw = input("  (enter for next, 'skip' to dismiss) > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                raw = "skip"
            if raw == "skip":
                break
        seen = i
    completed = seen == len(campaign.cards)
    if store is not None:
        store.record_campaign(campaign.id, seen=seen, completed=completed)
    if completed:
        print("  Tour complete — the hub notes another informed co-conspirator.")
    else:
        print("  Dismissed — it won't bug you again.")
    return {"campaign_id": campaign.id, "seen": seen, "completed": completed}
