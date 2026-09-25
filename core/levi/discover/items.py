"""Item schema + loader for the discovery corpus.

An item is one JSON object per line::

    {"id": "unique-string",
     "title": "Human title",
     "kind": "note|paper|bookmark|memory|file|...",
     "tags": ["tag1", "tag2"],
     "added_at": "2026-09-01T10:00:00",
     "source": "archive|memory|manual|...",
     "blurb": "one-line why it exists (optional)"}

``kind`` is free-form — the digest's diversity rules cap per-kind counts
whatever the kinds are. Validation is fail-closed per line: corrupt lines
are skipped with a warning printed (never silently, never fatal to the
whole corpus). Missing ``id``/``title`` fails the line; everything else
has a sane default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

__all__ = ["DiscoverError", "validate_item", "load_items", "ITEM_FIELDS"]

ITEM_FIELDS = ("id", "title", "kind", "tags", "added_at", "source", "blurb")


class DiscoverError(Exception):
    """Discovery failed (unreadable corpus, no usable items...)."""


def validate_item(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise DiscoverError(f"item must be an object, got {type(raw).__name__}")
    item_id = raw.get("id")
    title = raw.get("title")
    if not isinstance(item_id, str) or not item_id.strip():
        raise DiscoverError("item is missing a non-empty string 'id'")
    if not isinstance(title, str) or not title.strip():
        raise DiscoverError(f"item {item_id!r} is missing a non-empty 'title'")
    tags = raw.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise DiscoverError(f"item {item_id!r}: 'tags' must be a list of strings")
    return {
        "id": item_id.strip(),
        "title": title.strip(),
        "kind": str(raw.get("kind", "misc")),
        "tags": [t for t in tags],
        "added_at": str(raw.get("added_at", "")),
        "source": str(raw.get("source", "manual")),
        "blurb": str(raw.get("blurb", "")),
    }


def load_items(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL corpus. Corrupt lines are skipped with a printed warning."""
    path = Path(path)
    if not path.exists():
        raise DiscoverError(
            f"corpus not found: {path} "
            "(run `discover init-sample` for a starter corpus, or pass --source)"
        )
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError as exc:
                print(f"discover: skipping corrupt line {lineno} ({exc})")
                continue
            try:
                item = validate_item(raw)
            except DiscoverError as exc:
                print(f"discover: skipping invalid line {lineno} ({exc})")
                continue
            if item["id"] in seen:
                print(f"discover: skipping duplicate id {item['id']!r} (line {lineno})")
                continue
            seen.add(item["id"])
            items.append(item)
    if not items:
        raise DiscoverError(f"corpus {path} yielded no usable items")
    return items
