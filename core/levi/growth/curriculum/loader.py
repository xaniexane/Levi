"""Curriculum ingestion: seed the memory store with founder teachings.

``load_curriculum()`` ingests every lesson in
:mod:`levi.growth.curriculum.lessons` through the growth consolidation
path, so consolidation stays the only growth write route into memory.
Each seed entry carries:

* tags ``["growth", "curriculum", kind]`` — growth-tagged like all
  growth writes, plus a ``curriculum`` tag so seed teachings stay
  separable from Levi's self-taught learnings
* high initial corroboration — these came from the founders, so they
  start at high confidence/importance with a seeded corroboration
  count, not as provisional guesses
* provenance ``taught-by: chauncey`` or ``taught-by: rex``

Idempotency: consolidation dedups on word-set Jaccard >= 0.5, so
re-loading an unchanged lesson corroborates the existing entry instead
of writing a duplicate. ``load_curriculum`` then stamps every lesson's
``lesson_id``/``taught_by`` metadata so re-loads stay stable and
``curriculum_topics`` can count by topic.
"""

from __future__ import annotations

from typing import Any

from levi.growth.consolidate import consolidate
from levi.growth.curriculum.lessons import TOPICS, LESSONS, validate_lessons
from levi.growth.reflect import Learning

try:
    from levi.memory.store import MemoryStore
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore

SEED_CONFIDENCE = 0.95
SEED_CORROBORATED_COUNT = 20
CURRICULUM_CYCLE_ID = "curriculum-seed"


def _provenance(taught_by: str) -> dict[str, str]:
    return {"origin": "curriculum-seed", "taught_by": taught_by}


def load_curriculum(store: Any = None) -> dict[str, Any]:
    """Ingest all curriculum lessons as seed memory entries.

    Idempotent: re-loading corroborates existing seed entries (Jaccard
    dedup in consolidation) instead of writing duplicates.

    Returns ``{total, accepted, corroborated, skipped, stamped}``.
    """
    if MemoryStore is None:
        return {
            "total": len(LESSONS),
            "accepted": 0,
            "corroborated": 0,
            "skipped": len(LESSONS),
            "stamped": 0,
        }
    if store is None:
        store = MemoryStore()

    lessons = validate_lessons(list(LESSONS))
    learnings = [
        Learning(
            kind=lesson["kind"],
            content=lesson["text"],
            confidence=SEED_CONFIDENCE,
            provenance=_provenance(lesson["taught_by"]),
        )
        for lesson in lessons
    ]
    report = consolidate(
        learnings,
        cycle_id=CURRICULUM_CYCLE_ID,
        store=store,
        dedup_threshold=0.5,
    )

    # Stamp lesson identity + founder provenance on every matching entry.
    # Consolidation dedups on text similarity; the stamp makes re-loads
    # keyed on stable lesson ids and marks seeds apart from self-taught
    # (provisional) learnings.
    stamped = 0
    entries = store.list(limit=5000)
    for lesson in lessons:
        match = next(
            (
                e
                for e in entries
                if e.content == lesson["text"] and "growth" in e.tags
            ),
            None,
        )
        if match is None:
            continue
        md = dict(match.metadata or {})
        provenance = md.get("provenance")
        if not isinstance(provenance, dict):
            provenance = {}
        provenance.update(_provenance(lesson["taught_by"]))
        md.update(
            {
                "provenance": provenance,
                "lesson_id": lesson["id"],
                "topic": lesson["topic"],
                "taught_by": lesson["taught_by"],
                "seed": True,
                "status": "seeded",
                "corroborated_count": max(
                    int(md.get("corroborated_count", 0)),
                    SEED_CORROBORATED_COUNT,
                ),
            }
        )
        tags = list(match.tags)
        if "curriculum" not in tags:
            tags.append("curriculum")
        store.update(match.id, tags=tags, metadata=md)
        stamped += 1

    return {
        "total": len(lessons),
        "accepted": report["accepted"],
        "corroborated": report["corroborated"],
        "skipped": report["skipped"],
        "stamped": stamped,
    }


def curriculum_topics(store: Any = None) -> dict[str, int]:
    """Count loaded seed lessons per topic (zero for missing topics)."""
    counts: dict[str, int] = {topic: 0 for topic in TOPICS}
    if MemoryStore is None:
        return counts
    if store is None:
        store = MemoryStore()
    for entry in store.list(limit=5000):
        if "curriculum" not in entry.tags:
            continue
        topic = (entry.metadata or {}).get("topic") or "Untagged"
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def curriculum_entries(store: Any = None, *, topic: str = "") -> list[Any]:
    """Return the loaded seed entries, optionally filtered by topic."""
    if MemoryStore is None:
        return []
    if store is None:
        store = MemoryStore()
    entries = [e for e in store.list(limit=5000) if "curriculum" in e.tags]
    if topic:
        entries = [e for e in entries if (e.metadata or {}).get("topic") == topic]
    entries.sort(
        key=lambda e: str((e.metadata or {}).get("lesson_id") or e.id)
    )
    return entries
