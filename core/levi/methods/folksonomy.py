"""Delicious-style folksonomy: tagging is filing AND publishing.

Origin: del.icio.us (Joshua Schachter, 2003) — social bookmarking where you
saved URLs under free-form tags, and everyone's tagged collection was
publicly browsable. The tags formed a folksonomy: bottom-up organization with
no editors and no algorithm. Tagging was both filing and publishing — each
bookmark carried its tags into a shared pool, a live human-curated index of
the web, ranked by real use rather than by PageRank.

What it is in LEVI: ``FolksonomyIndex``. Tag items with free-form tags
(personal filing); the shared pool aggregates tag -> items with real
use-counts — re-tagging an item with the same tag bumps its count, because
that IS use; ``related`` suggests tags by co-occurrence on shared items.
Ranking comes from actual tagging activity, never from an algorithm.

Honesty label: USEFUL PATTERN — co-occurrence ranking is a real mechanism,
but it organizes a shared pool; it does not replace retrieval.

Deny-closed inputs: empty item ids, empty tags, untagging an unknown item,
untagging a tag the item does not carry, and querying or relating an unknown
tag are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["FolksonomyIndex"]


@dataclass
class _Filing:
    """One item's personal filing: its tags, and how often each tag was used."""

    item_id: str
    uses: dict[str, int] = field(default_factory=dict)


class FolksonomyIndex:
    """Free-form tags; the shared pool is ranked by real use."""

    def __init__(self) -> None:
        self._filings: dict[str, _Filing] = {}

    # -- validation -------------------------------------------------------
    def _check_item_id(self, item_id: str) -> str:
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("item id must be a non-empty string")
        return item_id.strip()

    def _check_tag(self, tag: str) -> str:
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("tag must be a non-empty string")
        return tag.strip().lower()

    # -- tagging ------------------------------------------------------------
    def tag(self, item_id: str, tags: list[str]) -> None:
        """File an item under free-form tags. Re-tagging an existing
        (item, tag) pair is not an error — it bumps the tag's use-count,
        because repeated use is exactly what the shared pool ranks by."""
        item_id = self._check_item_id(item_id)
        if not isinstance(tags, list) or not tags:
            raise ValueError("tags must be a non-empty list of strings")
        filing = self._filings.setdefault(item_id, _Filing(item_id=item_id))
        for tag in tags:
            tag = self._check_tag(tag)
            filing.uses[tag] = filing.uses.get(tag, 0) + 1

    def untag(self, item_id: str, tag: str) -> None:
        item_id = self._check_item_id(item_id)
        tag = self._check_tag(tag)
        filing = self._filings.get(item_id)
        if filing is None:
            raise ValueError(f"unknown item: {item_id!r}")
        if tag not in filing.uses:
            raise ValueError(f"item {item_id!r} is not tagged {tag!r}")
        del filing.uses[tag]
        if not filing.uses:
            del self._filings[item_id]

    # -- the shared pool ------------------------------------------------------
    def _require_known_tag(self, tag: str) -> str:
        tag = self._check_tag(tag)
        if not any(tag in f.uses for f in self._filings.values()):
            raise ValueError(f"unknown tag: {tag!r}")
        return tag

    def query(self, tag: str) -> list[str]:
        """Items carrying the tag, ranked by real use-count, ties by item id."""
        tag = self._require_known_tag(tag)
        scored = [
            (filing.uses[tag], filing.item_id)
            for filing in self._filings.values()
            if tag in filing.uses
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [item_id for _, item_id in scored]

    def related(self, tag: str, limit: int = 5) -> list[str]:
        """Tags that co-occur with the tag on shared items — the folksonomy's
        way of saying 'people who filed this also filed that'."""
        tag = self._require_known_tag(tag)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError(f"limit must be a positive integer, got {limit!r}")
        scores: dict[str, int] = {}
        weight: dict[str, int] = {}
        for filing in self._filings.values():
            if tag not in filing.uses:
                continue
            for other, uses in filing.uses.items():
                if other == tag:
                    continue
                scores[other] = scores.get(other, 0) + 1
                weight[other] = weight.get(other, 0) + uses
        ranked = sorted(scores, key=lambda t: (-scores[t], -weight[t], t))
        return ranked[:limit]

    # -- inspection -------------------------------------------------------------
    def tags_of(self, item_id: str) -> list[str]:
        item_id = self._check_item_id(item_id)
        filing = self._filings.get(item_id)
        if filing is None:
            raise ValueError(f"unknown item: {item_id!r}")
        return sorted(filing.uses)

    def use_count(self, item_id: str, tag: str) -> int:
        """How many times this item was tagged with this tag — its rank."""
        item_id = self._check_item_id(item_id)
        tag = self._check_tag(tag)
        filing = self._filings.get(item_id)
        if filing is None or tag not in filing.uses:
            raise ValueError(f"item {item_id!r} is not tagged {tag!r}")
        return filing.uses[tag]

    def known_tags(self) -> list[str]:
        tags: set[str] = set()
        for filing in self._filings.values():
            tags.update(filing.uses)
        return sorted(tags)
