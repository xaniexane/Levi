"""Winnow engine — near-duplicate clustering over text items.

Inputs
------
``items``: list of ``{"id": str, "text": str}``
``threshold``: similarity ratio in (0, 1] (default 0.85)
``max_items``: refuse lists longer than this (default 2000; pairwise
comparison is O(n^2))

The engine normalizes each text (casefold + whitespace collapse),
compares every pair with ``difflib.SequenceMatcher``, and merges pairs
at or above ``threshold`` into groups via union-find. The verdict names
one canonical keeper per group (lexicographically smallest id —
deterministic, disclosed) and lists every member.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Partition law** — every input item appears in exactly one group.
2. **Determinism law** — same inputs → byte-identical verdict.
3. **No-deletion law** — groups only merge; nothing is ever dropped.
   Winnowing separates the grain from the chaff, it does not burn the
   chaff. This is the nothing-thrown-away law as an engine.
4. **Honest-merge law** — a merge is recorded with the exact ratio that
   caused it; pairs below threshold never merge.
5. **Canonical law** — the keeper is the smallest id in the group.

Confidence is the mean merge ratio (every merge ≥ threshold), or 1.0
when nothing merged.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_DEFAULT_THRESHOLD = 0.85
_DEFAULT_MAX_ITEMS = 2000


def _normalize(text: str) -> str:
    """Casefolded, whitespace-collapsed — the comparison surface."""
    return " ".join(text.casefold().split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _winnow(inputs: Dict[str, Any]) -> EngineResult:
    items = inputs.get("items")
    threshold = inputs.get("threshold", _DEFAULT_THRESHOLD)
    max_items = inputs.get("max_items", _DEFAULT_MAX_ITEMS)

    if not isinstance(items, list) or not items:
        raise EngineInputError("winnow: 'items' needs a non-empty list")
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not 0.0 < threshold <= 1.0
    ):
        raise EngineInputError("winnow: 'threshold' must be in (0, 1]")
    if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items < 2:
        raise EngineInputError("winnow: 'max_items' must be an int ≥ 2")
    if len(items) > max_items:
        raise EngineInputError(
            f"winnow: {len(items)} items exceeds max_items={max_items}; "
            "refused rather than an O(n²) blowup"
        )

    seen: Dict[str, str] = {}
    for entry in items:
        if not isinstance(entry, dict):
            raise EngineInputError("winnow: each item must be a dict")
        item_id = entry.get("id")
        text = entry.get("text")
        if not isinstance(item_id, str) or not item_id:
            raise EngineInputError("winnow: each item needs a non-empty str 'id'")
        if not isinstance(text, str):
            raise EngineInputError(f"winnow: item '{item_id}' needs a str 'text'")
        if item_id in seen:
            raise EngineInputError(
                f"winnow: duplicate id '{item_id}' — refused, never merged silently"
            )
        seen[item_id] = text

    ids = sorted(seen)
    norm = {i: _normalize(seen[i]) for i in ids}
    trace: List[str] = [f"normalized {len(ids)} texts; threshold {threshold}"]

    # Union-find over the id set; iteration order is fully sorted, so
    # the clustering — and the verdict — is deterministic.
    parent: Dict[str, str] = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    merge_ratios: List[float] = []
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            ratio = _similarity(norm[a], norm[b])
            if ratio >= threshold:
                if find(a) != find(b):
                    union(a, b)
                    trace.append(
                        f"merged '{b}' into '{find(a)}' group "
                        f"(ratio={ratio:.3f} ≥ {threshold})"
                    )
                merge_ratios.append(ratio)

    clusters: Dict[str, List[str]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)

    groups = []
    for canonical in sorted(clusters):
        members = sorted(clusters[canonical])
        groups.append(
            {
                "canonical": canonical,
                "members": members,
                "duplicate_count": len(members) - 1,
            }
        )

    item_count = len(ids)
    duplicate_count = item_count - len(groups)
    confidence = (
        round(sum(merge_ratios) / len(merge_ratios), 3) if merge_ratios else 1.0
    )
    trace.append(
        f"{item_count} items → {len(groups)} groups; "
        f"{duplicate_count} duplicates marked, 0 deleted"
    )

    verdict = {
        "groups": groups,
        "item_count": item_count,
        "group_count": len(groups),
        "duplicate_count": duplicate_count,
    }
    return EngineResult(
        engine_id="winnow", verdict=verdict, confidence=confidence, trace=trace
    )


WINNOW_ENGINE = Engine(
    id="winnow",
    name="Winnow",
    description=(
        "Near-duplicate clustering over text items: merge groups, a "
        "deterministic canonical keeper per group, full merge trace. "
        "Nothing is ever deleted — duplicates are marked."
    ),
    version="1.0.0",
    required=("items",),
    schema={
        "items": "list[{id: str, text: str}] (non-empty, ids unique)",
        "threshold": "number in (0, 1], default 0.85",
        "max_items": "int ≥ 2, default 2000 (O(n²) guard)",
    },
    risk="info",
    handler=_winnow,
)

registry.register(WINNOW_ENGINE)
