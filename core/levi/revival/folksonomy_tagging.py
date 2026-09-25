"""Folksonomy tagging: tags by humans, tag pages, tag-search alerts.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #6] (folksonomy tagging: public-human-style tagging with tag pages
and tag-search alerting).

This is an original, from-scratch implementation for LEVI. A ``Garden``
lets any human attach free-text tags to items — no controlled vocabulary,
no auto-tagger, no suggested tags (the folksonomy *is* the humans). Tags are
normalized lightly (lowercased, trimmed, internal whitespace collapsed) so
``"Slow Web"`` and ``"slow  web"`` are one tag, but no stemming or synonym
merging happens: the module never claims two different human words are the
same.

Every tag gets a tag page (``tag_page``): the items carrying it, who tagged
them, and related tags (co-occurring tags, counted). ``subscribe`` registers
a tag-search alert: when a newly tagged item matches a subscriber's tag, the
alert fires into ``pending_alerts`` — a pull queue, not a push channel, so
nothing ever interrupts anyone.

Honest limits:
- Normalization is cosmetic; it does not resolve synonyms or typos. ``tag``
  and ``tags`` are different tags — humans merge them by retagging.
- Alerts are pull-based (``pending_alerts`` + ``acknowledge``). There is no
  email/push delivery; the surrounding system owns delivery.
- Tags are additive-only metadata; removing a tag is supported, but history
  of who tagged what is kept (``tag_history``) as provenance.

Public surface:
- ``Garden``: ``add_item``, ``tag``, ``untag``, ``tags_of``, ``tag_page``,
  ``related_tags``, ``search``, ``subscribe``, ``unsubscribe``,
  ``pending_alerts``, ``acknowledge``, ``tag_history``, ``all_tags``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/folksonomy-tagging"

_WS = re.compile(r"\s+")


def normalize_tag(raw: str) -> str:
    """Cosmetic normalization only: lower, trim, collapse whitespace."""
    return _WS.sub(" ", raw.strip().lower())


class GardenError(ValueError):
    """Raised when a tagging operation is invalid."""


@dataclass
class TagEvent:
    """Provenance record: who put which tag on which item, when."""

    item_id: int
    tag: str
    tagger: str
    action: str  # "tagged" | "untagged"
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GardenItem:
    id: int
    title: str
    locator: str = ""


class Garden:
    """Human-driven folksonomy with tag pages and pull-based alerts."""

    def __init__(self) -> None:
        self._items: Dict[int, GardenItem] = {}
        self._tags: Dict[int, Dict[str, str]] = {}  # item_id -> {tag: tagger}
        self._history: List[TagEvent] = []
        self._next_id = 1
        # subscriptions: tag -> {subscriber: last_seen_event_index}
        self._subscriptions: Dict[str, Dict[str, int]] = {}

    # -- items -----------------------------------------------------------------

    def add_item(self, title: str, locator: str = "") -> GardenItem:
        if not title.strip():
            raise GardenError("an item needs a title")
        item = GardenItem(
            id=self._next_id, title=title.strip(), locator=locator.strip()
        )
        self._items[item.id] = item
        self._tags[item.id] = {}
        self._next_id += 1
        return item

    def get(self, item_id: int) -> GardenItem:
        try:
            return self._items[item_id]
        except KeyError:
            raise GardenError(f"no item #{item_id}") from None

    # -- human tagging -----------------------------------------------------------

    def tag(self, item_id: int, raw_tag: str, tagger: str) -> str:
        tag = normalize_tag(raw_tag)
        tagger = tagger.strip()
        if not tag:
            raise GardenError("tag cannot be empty")
        if not tagger:
            raise GardenError("tagging needs a tagger")
        item_tags = self._tags[self.get(item_id).id]
        if tag in item_tags:
            raise GardenError(f"item #{item_id} already carries {tag!r}")
        item_tags[tag] = tagger
        self._record(item_id, tag, tagger, "tagged")
        return tag

    def untag(self, item_id: int, raw_tag: str, tagger: str) -> str:
        tag = normalize_tag(raw_tag)
        item_tags = self._tags[self.get(item_id).id]
        if tag not in item_tags:
            raise GardenError(f"item #{item_id} does not carry {tag!r}")
        del item_tags[tag]
        self._record(item_id, tag, tagger.strip() or "unknown", "untagged")
        return tag

    def tags_of(self, item_id: int) -> Dict[str, str]:
        """Current tags on an item, mapped to who placed them."""
        return dict(self._tags[self.get(item_id).id])

    def _record(self, item_id: int, tag: str, tagger: str, action: str) -> None:
        self._history.append(
            TagEvent(item_id=item_id, tag=tag, tagger=tagger, action=action)
        )

    def tag_history(self, item_id: Optional[int] = None) -> List[TagEvent]:
        events = self._history
        if item_id is not None:
            events = [e for e in events if e.item_id == item_id]
        return list(events)

    # -- tag pages -----------------------------------------------------------------

    def all_tags(self) -> Dict[str, int]:
        """Every live tag with its item count."""
        counts: Dict[str, int] = {}
        for item_tags in self._tags.values():
            for tag in item_tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def tag_page(self, raw_tag: str) -> Dict[str, object]:
        """The tag page: items, taggers, related tags."""
        tag = normalize_tag(raw_tag)
        items = [
            {"id": i, "title": self._items[i].title, "tagged_by": tags[tag]}
            for i, tags in self._tags.items()
            if tag in tags
        ]
        items.sort(key=lambda d: d["id"])
        return {
            "tag": tag,
            "count": len(items),
            "items": items,
            "related": self.related_tags(tag),
        }

    def related_tags(self, raw_tag: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Tags that co-occur with this one, counted. Folksonomy's own map."""
        tag = normalize_tag(raw_tag)
        co: Dict[str, int] = {}
        for item_tags in self._tags.values():
            if tag in item_tags:
                for other in item_tags:
                    if other != tag:
                        co[other] = co.get(other, 0) + 1
        return sorted(co.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]

    def search(self, raw_tag: str) -> List[GardenItem]:
        """Exact-tag lookup. No fuzzy matching — the human word is the word."""
        tag = normalize_tag(raw_tag)
        return [self._items[i] for i, tags in self._tags.items() if tag in tags]

    # -- tag-search alerting (pull, never push) --------------------------------------

    def subscribe(self, subscriber: str, raw_tag: str) -> str:
        subscriber = subscriber.strip()
        tag = normalize_tag(raw_tag)
        if not subscriber:
            raise GardenError("a subscription needs a subscriber")
        if not tag:
            raise GardenError("a subscription needs a tag")
        self._subscriptions.setdefault(tag, {})[subscriber] = len(self._history)
        return tag

    def unsubscribe(self, subscriber: str, raw_tag: str) -> bool:
        tag = normalize_tag(raw_tag)
        subs = self._subscriptions.get(tag, {})
        return subs.pop(subscriber.strip(), None) is not None

    def pending_alerts(self, subscriber: str) -> List[Dict[str, object]]:
        """New taggings on subscribed tags since this subscriber last looked."""
        subscriber = subscriber.strip()
        alerts: List[Dict[str, object]] = []
        for tag, subs in self._subscriptions.items():
            if subscriber not in subs:
                continue
            seen = subs[subscriber]
            for idx in range(seen, len(self._history)):
                event = self._history[idx]
                if event.tag == tag and event.action == "tagged":
                    alerts.append(
                        {
                            "tag": tag,
                            "item_id": event.item_id,
                            "item_title": self._items[event.item_id].title,
                            "tagged_by": event.tagger,
                            "at": event.at,
                        }
                    )
        alerts.sort(key=lambda a: a["at"])
        return alerts

    def acknowledge(self, subscriber: str) -> int:
        """Mark all alerts seen. Returns how many were pending."""
        subscriber = subscriber.strip()
        pending = self.pending_alerts(subscriber)
        now = len(self._history)
        for subs in self._subscriptions.values():
            if subscriber in subs:
                subs[subscriber] = now
        return len(pending)

    def __len__(self) -> int:
        return len(self._items)
