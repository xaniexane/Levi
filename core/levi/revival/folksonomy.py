"""Folksonomy — a human-curated tag index for shared bookmarks.

Studied from: fallen-platforms-evening-20260916, report.md [1. Delicious].

The mechanism, functionally: tagging is both filing AND publishing. Every
bookmark carries free-form tags; the same tags that file a link for one
person publish it into a shared, live index. That index is ranked by real
use — how often tags are applied and how recently — so the vocabulary
stays emergent: no fixed taxonomy, the crowd's words become the catalog.

This module is a software analog of that pattern at toy scale: a
``Folksonomy`` holds bookmarks (url, title, owner, tags, timestamp),
builds a tag index and a tag co-occurrence graph, and exposes the live
ranked index (``popular_tags``), tag-conjunction search, and
co-occurrence-driven tag suggestions for new bookmarks.

Honesty: ranking is a heuristic (apply-count with recency decay), not a
measure of quality; suggestions come from tag co-occurrence statistics,
not language understanding. Duplicate bookmarks of the same URL by
different owners are intentional — each person's tags are their own
publishing act — and are linked by URL rather than merged.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Set

ORIGIN = "levi-revival/folksonomy"


class Bookmark:
    """One bookmark: one person's filing act and publishing act."""

    _seq = 0

    def __init__(
        self,
        url: str,
        title: str,
        owner: str,
        tags: Iterable[str],
        timestamp: Optional[float] = None,
    ) -> None:
        Bookmark._seq += 1
        self.id = f"bm{Bookmark._seq:06d}"
        self.url = url.strip()
        self.title = title
        self.owner = owner
        self.tags = frozenset(_normalize(t) for t in tags if _normalize(t))
        self.timestamp = timestamp if timestamp is not None else time.time()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Bookmark({self.id}, {self.title!r}, {sorted(self.tags)})"


def _normalize(tag: str) -> str:
    return tag.strip().lower().replace(" ", "-")


class Folksonomy:
    """A living tag index over a shared bookmark pool."""

    def __init__(self, decay_per_day: float = 0.97) -> None:
        self.bookmarks: Dict[str, Bookmark] = {}
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.cooccur: Dict[str, Counter] = defaultdict(Counter)
        self.decay_per_day = decay_per_day

    # -- filing / publishing ---------------------------------------------

    def add(
        self,
        url: str,
        title: str,
        owner: str,
        tags: Iterable[str],
        timestamp: Optional[float] = None,
    ) -> Bookmark:
        """File a bookmark and publish it into the shared index."""
        bm = Bookmark(url, title, owner, tags, timestamp)
        self.bookmarks[bm.id] = bm
        for tag in bm.tags:
            self.tag_index[tag].add(bm.id)
        for a in bm.tags:
            for b in bm.tags:
                if a != b:
                    self.cooccur[a][b] += 1
        return bm

    def remove(self, bookmark_id: str) -> bool:
        """Unfile a bookmark; withdraws it from the shared index too."""
        bm = self.bookmarks.pop(bookmark_id, None)
        if bm is None:
            return False
        for tag in bm.tags:
            self.tag_index[tag].discard(bookmark_id)
        for a in bm.tags:
            for b in bm.tags:
                if a != b:
                    self.cooccur[a][b] -= 1
                    if self.cooccur[a][b] <= 0:
                        del self.cooccur[a][b]
        return True

    # -- the live index --------------------------------------------------

    def tag_weight(self, tag: str, now: Optional[float] = None) -> float:
        """Recency-decayed weight: real use, not a fixed taxonomy."""
        now = now if now is not None else time.time()
        weight = 0.0
        for bm_id in self.tag_index.get(tag, ()):
            age_days = max(0.0, (now - self.bookmarks[bm_id].timestamp) / 86400.0)
            weight += self.decay_per_day**age_days
        return weight

    def popular_tags(self, limit: int = 25) -> List[str]:
        """The live human-curated index, ranked by real use."""
        return sorted(self.tag_index, key=lambda t: self.tag_weight(t), reverse=True)[
            :limit
        ]

    def tag_count(self, tag: str) -> int:
        return len(self.tag_index.get(tag, ()))

    # -- search & discovery ----------------------------------------------

    def search(
        self, tags: Iterable[str], match: str = "all", limit: int = 50
    ) -> List[Bookmark]:
        """Tag search: 'all' (conjunction) or 'any' (union)."""
        wanted = [_normalize(t) for t in tags if _normalize(t)]
        if not wanted:
            return []
        sets = [self.tag_index.get(t, set()) for t in wanted]
        hits = set.intersection(*sets) if match == "all" else set.union(*sets)
        bms = [self.bookmarks[i] for i in hits]
        bms.sort(key=lambda b: b.timestamp, reverse=True)
        return bms[:limit]

    def related_tags(self, tag: str, limit: int = 10) -> List[str]:
        """Tags that co-occur with ``tag`` — the emergent vocabulary."""
        tag = _normalize(tag)
        return [t for t, _ in self.cooccur.get(tag, Counter()).most_common(limit)]

    def suggest_tags(
        self, url: Optional[str] = None, seed_tags: Iterable[str] = (), limit: int = 8
    ) -> List[str]:
        """Suggest tags for a new bookmark.

        Union of: tags already applied to the same URL by others (their
        publishing act reused) and co-occurrence neighbors of the seed
        tags. A heuristic, not a semantic match.
        """
        scores: Counter = Counter()
        if url:
            for bm in self.bookmarks.values():
                if bm.url == url.strip():
                    for t in bm.tags:
                        scores[t] += 2
        seeds = {_normalize(t) for t in seed_tags if _normalize(t)}
        for s in seeds:
            for other, count in self.cooccur.get(s, {}).items():
                if other not in seeds:
                    scores[other] += count
        return [t for t, _ in scores.most_common(limit)]

    def same_url(self, url: str) -> List[Bookmark]:
        """Every person's tagging of one URL — filing stays personal."""
        url = url.strip()
        return [b for b in self.bookmarks.values() if b.url == url]

    def owners(self) -> Set[str]:
        return {b.owner for b in self.bookmarks.values()}
