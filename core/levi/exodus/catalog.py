"""The exit-hostility catalog: giant enclosure patterns, recorded as facts.

Each entry names the pattern, what the giant refuses to add, and the
signals that an enclosure is coming — so LEVI can spot the next one
before the eviction notice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class HostilityEntry:
    """One recorded enclosure pattern."""

    platform: str  # e.g. "X (Twitter)"
    giant: str  # e.g. "X Corp"
    pattern: str  # api-enclosure | acquired-kill | deletion-refusal
    year: int
    facts: str  # the load-bearing facts, researcher's own words
    refused_exit: str  # what the giant refuses to add
    enclosure_signals: List[str] = field(default_factory=list)
    record_id: str = ""  # ArchiveRecord this came from


HOSTILITY_CATALOG: List[HostilityEntry] = [
    HostilityEntry(
        platform="X (Twitter)",
        giant="X Corp",
        pattern="api-enclosure",
        year=2023,
        facts=(
            "Third-party clients cut off without warning Jan 2023 (Tweetbot, "
            "Twitterrific, Fenix, Talon); free API killed; paid tiers Basic "
            "$100/mo (later $200), Pro $5,000/mo, Enterprise reported "
            "~$42,000/mo for 50M tweets; developer agreement amended to ban "
            "substitute clients permanently."
        ),
        refused_exit="Open API and third-party clients — the only door is the official app.",
        enclosure_signals=[
            "Free tier becomes 'write-only' or 'for testing'",
            "ToS gains anti-substitute clauses",
            "Price sheet appears where none existed",
            "Researchers and archivists priced out first",
        ],
        record_id="arch-exit-x-api-kill",
    ),
    HostilityEntry(
        platform="Reddit",
        giant="Reddit, Inc.",
        pattern="api-enclosure",
        year=2023,
        facts=(
            "$12,000 per 50M requests ($0.24/1k calls) with 30 days notice; "
            "Apollo faced ~$20M/year and shut down 2023-06-30 alongside RIF and "
            "Sync; 8,000+ subreddits went dark in protest; company refused to "
            "negotiate while volunteer moderators kept working."
        ),
        refused_exit="Reasonable third-party access — the enclosures evict the builders but keep the volunteers.",
        enclosure_signals=[
            "Pricing announced with <60 days notice",
            "CEO cites 'AI data value' as pretext",
            "Moderator tools carved out (keep the labor, kill the apps)",
            "Protest met with 'not negotiating'",
        ],
        record_id="arch-exit-reddit-api-enclosure",
    ),
    HostilityEntry(
        platform="Parse",
        giant="Facebook (Meta)",
        pattern="acquired-kill",
        year=2017,
        facts=(
            "Bought for ~$85M in 2013; hosted service killed 2017-01-30 after a "
            "1-year runway; ~600,000 apps relied on it at peak; open-sourced "
            "Parse Server + migration tool as the lifeboat. Infra was never "
            "moved onto Facebook's own data centers — it was always disposable."
        ),
        refused_exit="A permanent foundation — a giant's developer platform is a loan, not ground.",
        enclosure_signals=[
            "Acquired platform never moved onto acquirer's infra",
            "Conference-stage praise continues right up to the kill",
            "Strategic pivot announced toward in-ecosystem tools",
            "Migration tooling ships alongside the shutdown notice",
        ],
        record_id="arch-exit-parse-kill",
    ),
    HostilityEntry(
        platform="Discord",
        giant="Discord Inc.",
        pattern="deletion-refusal",
        year=2015,
        facts=(
            "Deleting your account does not delete your messages in servers you "
            "can no longer access; they persist as 'Deleted User #0000' content. "
            "No built-in mass-delete of own messages exists; users rely on "
            "banned self-bots/extensions. Long-running petitions from abuse "
            "victims unanswered."
        ),
        refused_exit="True deletion — the delete button deletes the account, not the history.",
        enclosure_signals=[
            "Deletion leaves content readable (anonymized, not removed)",
            "No bulk self-service delete of your own posts",
            "Export exists but is hard to use (export theater)",
            "Years of user requests, zero shipped changes",
        ],
        record_id="arch-exit-discord-delete-refusal",
    ),
]


def hostility_by_platform(platform: str) -> Optional[HostilityEntry]:
    """Look up a catalog entry by platform name (case-insensitive)."""
    needle = platform.strip().lower()
    for entry in HOSTILITY_CATALOG:
        if entry.platform.lower() == needle or needle in entry.platform.lower():
            return entry
    return None


def patterns() -> Dict[str, List[str]]:
    """All platforms grouped by enclosure pattern."""
    grouped: Dict[str, List[str]] = {}
    for entry in HOSTILITY_CATALOG:
        grouped.setdefault(entry.pattern, []).append(entry.platform)
    return grouped
