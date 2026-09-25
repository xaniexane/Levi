"""ExplicitReach: the feed that can't be auctioned.

The rented-audience trade: the platform gives you free audience-building
tools, throttles your own posts' delivery to ~1-2% of your followers, and
sells reach back as ads. The follower count is displayed as YOUR asset while
delivery is metered as THEIR product.

ExplicitReach inverts it. The rules are structural:

- The only publishers in the feed are the ones the user explicitly
  subscribed to. Items from anywhere else are REJECTED at build time
  (LAW 5), not filtered afterward.
- Every feed item carries a ``why_shown`` provenance strip:
  ``"subscribed:<publisher-id>"``. There is no other allowed value, so a
  sponsored slot has nowhere to hide (the Amazon's-Choice lesson: badges
  and shelves must name their real inputs).
- Unsubscribing cuts reach immediately — no grace-period ghost delivery
  (LAW 6).
- ``audit_insertions()`` is the machine-checkable guard: any item whose
  provenance strip claims a sponsored, boosted, or promoted source is
  reported (LAW 7). There is deliberately no parameter anywhere that takes
  money, a bid, or an advertiser id as a ranking input.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ALLOWED_WHY_PREFIX = "subscribed:"
FORBIDDEN_WHY_MARKERS = (
    "sponsored",
    "promoted",
    "boosted",
    "paid",
    "advertiser",
    "bid",
    "choice-badge",
)


@dataclass(frozen=True)
class Subscription:
    publisher: str
    subscribed_at: float
    label: str = ""


@dataclass(frozen=True)
class FeedItem:
    id: str
    publisher: str
    title: str
    body: str
    published_at: float
    why_shown: str  # provenance strip, always "subscribed:<publisher>"


@dataclass
class PublisherPost:
    """An incoming post awaiting the feed builder's decision."""

    publisher: str
    title: str
    body: str
    published_at: float = field(default_factory=time.time)


class ExplicitReach:
    """A feed with exactly one ranking input: explicit subscriptions."""

    def __init__(self) -> None:
        self._subscriptions: Dict[str, Subscription] = {}

    # -- subscriptions ----------------------------------------------------

    def subscribe(self, publisher: str, label: str = "") -> Subscription:
        if not publisher.strip():
            raise ValueError("publisher id is required")
        sub = Subscription(
            publisher=publisher.strip(),
            subscribed_at=time.time(),
            label=label.strip(),
        )
        self._subscriptions[sub.publisher] = sub
        return sub

    def unsubscribe(self, publisher: str) -> bool:
        """LAW 6: reach ends the moment the subscription does."""
        return self._subscriptions.pop(publisher, None) is not None

    def subscriptions(self) -> List[Subscription]:
        return sorted(
            self._subscriptions.values(), key=lambda s: s.subscribed_at
        )

    # -- feed building ----------------------------------------------------

    def _why_shown(self, publisher: str) -> str:
        return ALLOWED_WHY_PREFIX + publisher

    def build_feed(self, posts: List[PublisherPost]) -> List[FeedItem]:
        """LAW 5: posts from non-subscribed publishers are rejected here.

        Raises ValueError naming the intruders — silent filtering would
        hide the throttle instead of refusing it.
        """
        intruders = sorted(
            {p.publisher for p in posts if p.publisher not in self._subscriptions}
        )
        if intruders:
            raise ValueError(
                "feed rejected %d post(s) from non-subscribed publisher(s): %s. "
                "Reach requires an explicit subscription — no auction, no "
                "sponsored slots." % (len(intruders), ", ".join(intruders))
            )
        items = [
            FeedItem(
                id="post-%d" % n,
                publisher=p.publisher,
                title=p.title,
                body=p.body,
                published_at=p.published_at,
                why_shown=self._why_shown(p.publisher),
            )
            for n, p in enumerate(
                sorted(posts, key=lambda p: p.published_at, reverse=True), 1
            )
        ]
        return items

    # -- audit ------------------------------------------------------------

    def audit_insertions(
        self, items: List[FeedItem]
    ) -> Tuple[bool, List[Dict[str, str]]]:
        """LAW 7: every item must prove it arrived by subscription.

        Returns (clean, findings). An item is dirty when its provenance
        strip is not exactly ``subscribed:<its own publisher>`` or names
        any forbidden (paid) marker. A dirty feed reports itself —
        detection is honest, not silent.
        """
        findings: List[Dict[str, str]] = []
        for item in items:
            why = (item.why_shown or "").strip()
            expected = self._why_shown(item.publisher)
            if why != expected:
                findings.append(
                    {
                        "item": item.id,
                        "publisher": item.publisher,
                        "why_shown": item.why_shown,
                        "problem": (
                            "provenance strip does not match an explicit "
                            "subscription (expected %r)" % expected
                        ),
                    }
                )
                continue
            low = why.lower()
            hits = [m for m in FORBIDDEN_WHY_MARKERS if m in low]
            if hits:
                findings.append(
                    {
                        "item": item.id,
                        "publisher": item.publisher,
                        "why_shown": item.why_shown,
                        "problem": "paid-marker in provenance: " + ", ".join(hits),
                    }
                )
        return (not findings, findings)

    # -- persistence ------------------------------------------------------

    def export_state(self) -> Dict[str, object]:
        return {
            "format": "levi-explicit-reach/1",
            "subscriptions": [
                {
                    "publisher": s.publisher,
                    "subscribed_at": s.subscribed_at,
                    "label": s.label,
                }
                for s in self.subscriptions()
            ],
        }

    @classmethod
    def import_state(cls, state: Dict[str, object]) -> "ExplicitReach":
        if state.get("format") != "levi-explicit-reach/1":
            raise ValueError("not an explicit-reach state bundle")
        feed = cls()
        for entry in state.get("subscriptions", []):
            sub = Subscription(
                publisher=str(entry["publisher"]),
                subscribed_at=float(entry["subscribed_at"]),
                label=str(entry.get("label", "")),
            )
            feed._subscriptions[sub.publisher] = sub
        return feed
