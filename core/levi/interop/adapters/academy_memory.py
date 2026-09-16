"""Adapter: academy concepts → memory-store-ready semantic entries.

Pure transform: academy concept dicts (as produced by
:func:`levi.academy.concepts.extract_concepts`) become dicts ready for the
memory store's ``new_entry`` — without importing the store, so this adapter
stays testable and dependency-light.

Output schema per concept::

    {"memory_type": "semantic",
     "content": str,            # human-readable fact: "<name> — <kind>, <track> academy"
     "tags": [str, ...],        # ["academy", <track>, <kind>, "concept"]
     "importance": float,       # 0..1, carried over from concept strength
     "metadata": {"provenance": "academy",
                  "concept_id": str, "track": str, "day": int|None,
                  "block": int|None, "session": int|None, "kind": str,
                  "content_words": [...], "status": str}}

Deny-closed: a concept that is not a dict or lacks a non-empty ``name``
raises :class:`ValueError` — the transform never emits half-formed entries.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def concepts_to_memory_entries(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform academy concepts into memory-store-ready SEMANTIC entries."""
    if not isinstance(concepts, list):
        raise ValueError(
            "concepts_to_memory_entries: expected a list, got %s"
            % type(concepts).__name__
        )
    out: List[Dict[str, Any]] = []
    for idx, concept in enumerate(concepts):
        if not isinstance(concept, dict):
            raise ValueError("concept #%d: not a dict" % idx)
        name = concept.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("concept #%d: missing non-empty 'name'" % idx)
        name = name.strip()
        kind = str(concept.get("kind", "concept") or "concept")
        track = str(concept.get("track", "general") or "general")
        strength = _clamp01(concept.get("strength", 0.8))
        content_words = concept.get("content_words") or []
        content = "%s — %s (%s academy)" % (name, kind, track)
        if content_words:
            content += "; key terms: %s" % ", ".join(str(w) for w in content_words[:12])
        entry = {
            "memory_type": "semantic",
            "content": content,
            "tags": ["academy", track, kind, "concept"],
            "importance": strength,
            "metadata": {
                "provenance": "academy",
                "concept_id": concept.get("id"),
                "track": track,
                "day": concept.get("day"),
                "block": concept.get("block"),
                "session": concept.get("session"),
                "kind": kind,
                "content_words": list(content_words),
                "status": concept.get("status", "active"),
            },
        }
        out.append(entry)
    return out
