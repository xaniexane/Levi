"""The promotion rule — how facts earn permanence in the creed block.

A candidate fact enters the persistent creed block ONLY after 3
recorded reinforcements, OR one explicit ``promote()`` call. Below
the threshold the fact stays provisional — visible, but not trusted
as creed.

Facts live in :class:`~levi.memory.store.MemoryStore` as SEMANTIC
entries tagged ``creed`` (+ ``creed-provisional`` / ``creed-promoted``)
with ``status`` and ``reinforcements`` in metadata. The growth loop
feeds the tracker through :func:`consolidation_corroboration_hook`,
an adapter: every time a learning corroborates an existing growth
entry, the matching creed candidate earns one reinforcement.

Stdlib-only. Home resolved at call time; pass a ``MemoryStore``
explicitly in tests for full hermeticity.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.creed._paths import _levi_home

try:
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore
    MemoryType = None  # type: ignore


PROMOTION_THRESHOLD = 3
PROVISIONAL = "provisional"
PROMOTED = "promoted"

CREED_TAG = "creed"
PROVISIONAL_TAG = "creed-provisional"
PROMOTED_TAG = "creed-promoted"


# --- content matching (same family of rule as growth dedup) -----------------

_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset(
    "the and for with that this from have has had were was are but not you your "
    "levi when what which while where their there then than them they our out can "
    "will would should could about into over after before between through during".split()
)


def _words(text: str) -> frozenset:
    return frozenset(w for w in _WORD.findall((text or "").lower()) if w not in _STOP)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similar_enough(a: str, b: str, threshold: float = 0.5) -> bool:
    return _jaccard(_words(a), _words(b)) >= threshold


# --- tracker -----------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fact_status(entry: Any) -> Dict[str, Any]:
    """Status view of a creed fact entry (None-safe shape, never raises)."""
    md = dict(getattr(entry, "metadata", None) or {})
    return {
        "fact_id": getattr(entry, "id", ""),
        "content": getattr(entry, "content", ""),
        "status": md.get("status", PROVISIONAL),
        "reinforcements": int(md.get("reinforcements", 0) or 0),
        "threshold": PROMOTION_THRESHOLD,
        "promoted": md.get("status") == PROMOTED,
        "source": md.get("creed_source", "manual"),
        "promoted_at": md.get("promoted_at"),
    }


class PromotionTracker:
    """Reinforcement counting + explicit promotion for creed facts."""

    def __init__(self, store: Any = None) -> None:
        if MemoryStore is None:
            raise RuntimeError("creed: levi.memory.store is unavailable")
        self.store = (
            store
            if store is not None
            else MemoryStore(data_dir=_levi_home() / "memory")
        )

    # -- queries ---------------------------------------------------------

    def _creed_entries(self) -> List[Any]:
        return [e for e in self.store.list(limit=5000) if CREED_TAG in e.tags]

    def provisional_facts(self) -> List[Any]:
        return [
            e
            for e in self._creed_entries()
            if (e.metadata or {}).get("status", PROVISIONAL) == PROVISIONAL
        ]

    def promoted_facts(self) -> List[Any]:
        return [
            e
            for e in self._creed_entries()
            if (e.metadata or {}).get("status") == PROMOTED
        ]

    def _find_match(self, content: str) -> Optional[Any]:
        for entry in self._creed_entries():
            if _similar_enough(content, entry.content or ""):
                return entry
        return None

    def _require(self, fact_id: str) -> Any:
        if not isinstance(fact_id, str) or not fact_id.strip():
            raise ValueError(
                "creed: fact_id must be a non-empty string, got %r" % (fact_id,)
            )
        entry = self.store.get(fact_id)
        if entry is None or CREED_TAG not in (entry.tags or []):
            raise ValueError("creed: unknown creed fact %r" % (fact_id,))
        return entry

    # -- the rule ---------------------------------------------------------

    def propose(
        self,
        content: str,
        *,
        source: str = "manual",
        importance: float = 0.5,
    ) -> str:
        """Register a candidate fact as PROVISIONAL. Returns its fact id.

        Duplicate proposals (same content by the matching rule) return
        the existing fact id instead of writing a second entry.
        """
        if not isinstance(content, str) or not content.strip():
            raise ValueError("creed: content must be a non-empty string")
        content = content.strip()
        existing = self._find_match(content)
        if existing is not None:
            return existing.id
        try:
            importance_f = max(0.0, min(1.0, float(importance)))
        except (TypeError, ValueError):
            raise ValueError(
                "creed: importance must be a number, got %r" % (importance,)
            ) from None
        entry = self.store.add(
            memory_type=MemoryType.SEMANTIC,
            content=content,
            importance=importance_f,
            source="creed",
            tags=[CREED_TAG, PROVISIONAL_TAG],
            metadata={
                "status": PROVISIONAL,
                "reinforcements": 0,
                "threshold": PROMOTION_THRESHOLD,
                "creed_source": source,
                "proposed_at": _now(),
            },
        )
        return entry.id

    def reinforce(self, fact_id: str) -> Dict[str, Any]:
        """Record one reinforcement. Promotes automatically at threshold.

        Reinforcing an already-promoted fact is a no-op returning its
        status. Raises ValueError on unknown fact id.
        """
        entry = self._require(fact_id)
        md = dict(entry.metadata or {})
        if md.get("status") == PROMOTED:
            return fact_status(entry)
        md["reinforcements"] = int(md.get("reinforcements", 0) or 0) + 1
        md["last_reinforced_at"] = _now()
        self.store.update(entry.id, metadata=md)
        entry = self.store.get(entry.id)
        if int((entry.metadata or {}).get("reinforcements", 0)) >= PROMOTION_THRESHOLD:
            return self._promote_entry(entry)
        return fact_status(entry)

    def promote(self, fact_id: str) -> Dict[str, Any]:
        """Explicit promotion — takes effect immediately, no threshold.

        Raises ValueError on unknown fact id.
        """
        entry = self._require(fact_id)
        return self._promote_entry(entry)

    def _promote_entry(self, entry: Any) -> Dict[str, Any]:
        md = dict(entry.metadata or {})
        if md.get("status") == PROMOTED:
            return fact_status(entry)
        md["status"] = PROMOTED
        md["promoted_at"] = _now()
        tags = [t for t in (entry.tags or []) if t != PROVISIONAL_TAG]
        if PROMOTED_TAG not in tags:
            tags.append(PROMOTED_TAG)
        self.store.update(entry.id, tags=tags, metadata=md)
        return fact_status(self.store.get(entry.id))

    def status(self, fact_id: str) -> Optional[Dict[str, Any]]:
        """Status of a fact; None when the id is not a creed fact."""
        if not isinstance(fact_id, str) or not fact_id.strip():
            return None
        entry = self.store.get(fact_id)
        if entry is None or CREED_TAG not in (entry.tags or []):
            return None
        return fact_status(entry)


# --- growth adapter -----------------------------------------------------------


def consolidation_corroboration_hook(
    entry_id: str, store: Any
) -> Optional[Dict[str, Any]]:
    """Adapter: growth corroboration → creed reinforcement.

    Called by :func:`levi.growth.consolidate.consolidate` (via its
    ``on_corroborate`` hook) whenever a learning corroborates an
    existing growth entry. Finds (or bootstraps) the matching creed
    candidate and records one reinforcement for it. Returns the fact
    status, or None when the entry is not a growth learning.

    Best-effort by contract: callers must wrap this so growth never
    breaks because the creed tracker hiccuped.
    """
    try:
        entry = store.get(entry_id)
    except Exception:
        return None
    if entry is None or "growth" not in (entry.tags or []):
        return None
    content = (entry.content or "").strip()
    if not content:
        return None
    try:
        tracker = PromotionTracker(store=store)
    except Exception:
        return None
    match = tracker._find_match(content)
    if match is not None:
        return tracker.reinforce(match.id)
    fact_id = tracker.propose(content, source="growth", importance=entry.importance)
    return tracker.reinforce(fact_id)
