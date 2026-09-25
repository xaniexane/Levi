"""Three-tier memory in file-portable form: core, recall, archival.

Origin: the 2026 "KAI-9000" method entry — memory split into three tiers.
Core holds the current commitments and standards and rides every prompt;
recall holds recent digests and daemon logs; archival holds old facts and
matured patterns. The whole thing is plain portable files, so the memory can
be backed up, diffed, and moved without a database.

What it is in LEVI: ``TieredMemory``. ``put``/``get`` per tier; items move
with ``promote`` (recall -> core) and ``demote`` (recall -> archival).
Archival is append-only: nothing ever leaves it. Tier sizes are capped — a
full core refuses new items outright (commitments are deliberate), while
recall and archival evict the oldest entry to make room.

Honesty label: LOAD-BEARING — tiered placement with promotion/demotion rules
and enforced caps is a concrete mechanism.

Deny-closed inputs: unknown tier names, empty keys, duplicate keys within a
tier, getting or removing an unknown key, promoting anything that is not in
recall, demoting anything that is not in recall, any removal from archival,
and putting into a full core are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

__all__ = ["TIERS", "MemoryItem", "TieredMemory"]

TIERS = ("core", "recall", "archival")

PROMOTE_FROM = "recall"
PROMOTE_TO = "core"
DEMOTE_FROM = "recall"
DEMOTE_TO = "archival"


@dataclass
class MemoryItem:
    """One fact living in one tier."""

    key: str
    value: Any
    tier: str


class TieredMemory:
    """Three tiers, capped, with promote/demote rules between them."""

    def __init__(
        self,
        core_cap: int = 64,
        recall_cap: int = 256,
        archival_cap: int = 1024,
    ) -> None:
        for name, cap in (
            ("core_cap", core_cap),
            ("recall_cap", recall_cap),
            ("archival_cap", archival_cap),
        ):
            if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
                raise ValueError(f"{name} must be a positive integer, got {cap!r}")
        self._caps = {"core": core_cap, "recall": recall_cap, "archival": archival_cap}
        self._store: dict[str, dict[str, MemoryItem]] = {t: {} for t in TIERS}

    # -- validation -------------------------------------------------------
    def _check_tier(self, tier: str) -> str:
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}: tiers are {list(TIERS)}")
        return tier

    def _check_key(self, key: str) -> str:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be a non-empty string")
        return key.strip()

    def _evict_oldest(self, tier: str) -> None:
        oldest = next(iter(self._store[tier]))
        del self._store[tier][oldest]

    # -- basic put/get ------------------------------------------------------
    def put(self, tier: str, key: str, value: Any) -> MemoryItem:
        """File an item in a tier. Core refuses when full; recall and
        archival evict the oldest entry to make room."""
        tier = self._check_tier(tier)
        key = self._check_key(key)
        if key in self._store[tier]:
            raise ValueError(f"duplicate key {key!r} in tier {tier!r}")
        if len(self._store[tier]) >= self._caps[tier]:
            if tier == "core":
                raise ValueError(
                    f"core tier is full ({self._caps[tier]} items): "
                    "core refuses rather than evicts — demote or remove first"
                )
            self._evict_oldest(tier)
        item = MemoryItem(key=key, value=value, tier=tier)
        self._store[tier][key] = item
        return item

    def get(self, tier: str, key: str) -> MemoryItem:
        tier = self._check_tier(tier)
        key = self._check_key(key)
        item = self._store[tier].get(key)
        if item is None:
            raise ValueError(f"unknown key {key!r} in tier {tier!r}")
        return item

    def remove(self, tier: str, key: str) -> MemoryItem:
        """Remove an item. Archival is append-only — removal there raises."""
        tier = self._check_tier(tier)
        if tier == "archival":
            raise ValueError("archival is append-only: items never leave it")
        key = self._check_key(key)
        try:
            return self._store[tier].pop(key)
        except KeyError:
            raise ValueError(f"unknown key {key!r} in tier {tier!r}") from None

    # -- movement -----------------------------------------------------------
    def promote(self, key: str) -> MemoryItem:
        """Move an item from recall into core. Only recall promotes."""
        key = self._check_key(key)
        if key not in self._store[PROMOTE_FROM]:
            raise ValueError(
                f"promote refused: {key!r} is not in recall "
                "(promotion runs recall -> core only)"
            )
        if len(self._store[PROMOTE_TO]) >= self._caps[PROMOTE_TO]:
            raise ValueError(
                f"promote refused: core is full ({self._caps['core']} items)"
            )
        if key in self._store[PROMOTE_TO]:
            raise ValueError(f"promote refused: duplicate key {key!r} already in core")
        item = self._store[PROMOTE_FROM].pop(key)
        item.tier = PROMOTE_TO
        self._store[PROMOTE_TO][key] = item
        return item

    def demote(self, key: str) -> MemoryItem:
        """Move an item from recall into archival. Only recall demotes."""
        key = self._check_key(key)
        if key not in self._store[DEMOTE_FROM]:
            raise ValueError(
                f"demote refused: {key!r} is not in recall "
                "(demotion runs recall -> archival only)"
            )
        if key in self._store[DEMOTE_TO]:
            raise ValueError(
                f"demote refused: duplicate key {key!r} already in archival"
            )
        if len(self._store[DEMOTE_TO]) >= self._caps[DEMOTE_TO]:
            self._evict_oldest(DEMOTE_TO)
        item = self._store[DEMOTE_FROM].pop(key)
        item.tier = DEMOTE_TO
        self._store[DEMOTE_TO][key] = item
        return item

    # -- inspection ---------------------------------------------------------
    def tier_of(self, key: str) -> Optional[str]:
        """Which tier holds this key, or None."""
        key = self._check_key(key)
        for tier in TIERS:
            if key in self._store[tier]:
                return tier
        return None

    def keys(self, tier: str) -> list[str]:
        return list(self._store[self._check_tier(tier)])

    def counts(self) -> dict[str, int]:
        return {t: len(self._store[t]) for t in TIERS}
