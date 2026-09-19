"""Consolidation: write learnings into durable memory.

Learnings become :class:`~levi.memory.types.MemoryEntry` records in the
local :class:`~levi.memory.store.MemoryStore`:

* fact       → SEMANTIC
* preference → PREFERENCE
* procedural → PROCEDURAL
* correction → SEMANTIC (tagged ``correction``)

Deduplication: a learning whose word-set overlaps an existing
growth-tagged entry by >= 0.5 (Jaccard) corroborates it instead —
importance rises, ``corroborated_count`` increments, no duplicate is
written. Every entry carries ``source="growth"``, tags
``["growth", "levi-learned", kind]``, and provenance metadata, so the
user can always see what Levi learned on its own and remove it.

Consolidation is the ONLY growth write path into memory. Growth never
writes anywhere else.
"""

from __future__ import annotations

import os
import re
from typing import Any

from levi.growth.guards import check_no_sentience_claim
from levi.growth.reflect import Learning

try:
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore
    MemoryType = None  # type: ignore


_KIND_TO_TYPE = {
    "fact": "semantic",
    "preference": "preference",
    "procedural": "procedural",
    "correction": "semantic",
}

_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset(
    "the and for with that this from have has had were was are but not you your "
    "levi when what which while where their there then than them they our out can "
    "will would should could about into over after before between through during".split()
)


def _words(text: str) -> frozenset:
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOP)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def contribute_enabled() -> bool:
    """Owner opt-in to pack their own local learnings for the collective.

    Cloud-distilled learnings (consent verified at harvest) pack by
    default; the owner's own sessions need this explicit opt-in.
    """
    return os.environ.get("LEVI_GROWTH_CONTRIBUTE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def shareable_learning(learning: Learning) -> bool:
    """Whether this learning may ever travel in a learning pack.

    Technique-only (procedural) AND consented origin. The pack builder
    re-verifies independently; this mark is the first of two gates.
    """
    if learning.kind != "procedural":
        return False
    prov = learning.provenance or {}
    if str(prov.get("mode", "")) == "rules:cloud-distill":
        return True
    return contribute_enabled()


def consolidate(
    learnings: list[Learning],
    *,
    cycle_id: str = "",
    store: Any = None,
    dry_run: bool = False,
    dedup_threshold: float = 0.5,
    on_corroborate: Any = None,
    extra_tags: tuple = (),
    dedup_scope: tuple = (),
) -> dict[str, Any]:
    """Write learnings to the memory store with dedup.

    Returns a report: ``{accepted, corroborated, skipped, writes}`` where
    ``writes`` lists the new entry ids (empty on dry-run).

    ``on_corroborate``, when given, is a callable ``(entry_id, store)``
    invoked (best-effort) each time a learning corroborates an existing
    entry. The creed package registers
    :func:`levi.creed.promotion.consolidation_corroboration_hook` here so
    repeated corroboration feeds the creed promotion rule — without this
    module ever importing the creed package.

    ``extra_tags`` appends tags to every written entry (e.g. the
    raising tracks' ``seat:<key>`` namespace). ``dedup_scope`` scopes
    the dedup pool to entries carrying all of those tags — one seat's
    learnings corroborate only that seat's record. Both default to
    empty, which keeps the original Levi-only behavior exactly.

    Raises ValueError when ``learnings`` is not a list or
    ``dedup_threshold`` is not within 0..1.
    """
    if not isinstance(learnings, list):
        raise ValueError(
            "consolidate: learnings must be a list, got %s" % type(learnings).__name__
        )
    try:
        dedup_threshold = float(dedup_threshold)
    except (TypeError, ValueError):
        raise ValueError(
            "consolidate: dedup_threshold must be a number, got %r" % (dedup_threshold,)
        ) from None
    if not 0.0 <= dedup_threshold <= 1.0:
        raise ValueError(
            "consolidate: dedup_threshold must be within 0..1, got %r"
            % (dedup_threshold,)
        )
    try:
        extra_tags = tuple(extra_tags)
    except TypeError:
        raise ValueError(
            "consolidate: extra_tags must be iterable, got %r" % (extra_tags,)
        )
    if not all(isinstance(t, str) and t.strip() for t in extra_tags):
        raise ValueError("consolidate: extra_tags must all be non-empty strings")
    try:
        dedup_scope = tuple(dedup_scope)
    except TypeError:
        raise ValueError("consolidate: dedup_scope must be iterable")
    report: dict[str, Any] = {
        "accepted": 0,
        "corroborated": 0,
        "skipped": 0,
        "writes": [],
    }
    if MemoryStore is None:
        report["skipped"] = len(learnings)
        return report
    if store is None:
        store = MemoryStore()

    growth_entries = [
        e
        for e in store.list(limit=5000)
        if "growth" in (e.tags or []) and all(t in (e.tags or []) for t in dedup_scope)
    ]
    # Precompute word sets once — was recomputed for every
    # learning x existing-entry pair (O(learnings x entries) tokenizations).
    entry_words: list[tuple[Any, frozenset]] = [
        (entry, _words(entry.content or "")) for entry in growth_entries
    ]

    for learning in learnings:
        if not isinstance(learning, Learning):
            report["skipped"] += 1
            continue
        if learning.kind not in _KIND_TO_TYPE:
            report["skipped"] += 1
            continue
        content = (learning.content or "").strip()
        if len(content) < 12:
            report["skipped"] += 1
            continue

        # Binding rail, last line of defense: nothing that asserts
        # sentience/subjective experience is ever written to memory.
        # A violation here is a bug upstream — log it loudly, skip the
        # learning, keep the cycle running.
        if check_no_sentience_claim(content):
            print(
                "growth: REFUSED to consolidate a learning asserting "
                "sentience/subjective experience (skipped, not written)"
            )
            report["skipped"] += 1
            continue

        # dedup against Levi's own past learnings
        lw = _words(content)
        best = None
        best_score = 0.0
        for entry, ew in entry_words:
            score = _jaccard(lw, ew)
            if score > best_score:
                best_score = score
                best = entry
        if best is not None and best_score >= dedup_threshold:
            report["corroborated"] += 1
            if not dry_run:
                md = dict(best.metadata or {})
                md["corroborated_count"] = int(md.get("corroborated_count", 0)) + 1
                md["last_corroborated_cycle"] = cycle_id
                store.update(
                    best.id,
                    importance=min(1.0, round(best.importance + 0.15, 3)),
                    metadata=md,
                )
                # Adapter hook: notify whoever counts corroborations
                # (the creed promotion tracker). Best-effort — a failing
                # hook must never break consolidation.
                if on_corroborate is not None:
                    try:
                        on_corroborate(best.id, store)
                    except Exception as exc:
                        print("growth: on_corroborate hook failed (%s)" % exc)
            continue

        if dry_run:
            report["accepted"] += 1
            continue

        mtype = MemoryType(_KIND_TO_TYPE[learning.kind])
        tags = ["growth", "levi-learned", learning.kind] + list(extra_tags)
        entry = store.add(
            memory_type=mtype,
            content=content,
            importance=round(max(0.05, min(1.0, learning.confidence)), 3),
            source="growth",
            tags=tags,
            metadata={
                "confidence": round(learning.confidence, 3),
                "provenance": learning.provenance,
                "cycle_id": cycle_id,
                "status": "provisional",
                "corroborated_count": 0,
                # First gate for learning-pack distribution; the pack
                # builder re-verifies independently (see levi.growth.sync).
                "shareable": shareable_learning(learning),
            },
        )
        entry_words.append((entry, _words(content)))
        report["accepted"] += 1
        report["writes"].append(entry.id)

    return report
