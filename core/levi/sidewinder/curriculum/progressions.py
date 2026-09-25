"""Sidewinder curriculum — progressions over the leveled course graph.

Entries form a real progression: ``prerequisites`` are entry-id links, and
``level`` runs foundation -> applied -> mastery. This module serves them in
learning order and verifies graph integrity (no dangling refs, no cycles).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from levi.sidewinder import LEVEL_ORDER, TRACKS
from levi.sidewinder.curriculum.corpus import Corpus


def check_graph(corpus: Corpus) -> Tuple[List[str], List[List[str]]]:
    """Return (dangling_refs, cycles).

    dangling_refs: "entry_id -> missing_id" strings. cycles: lists of ids
    forming each detected cycle.
    """
    dangling: List[str] = []
    for entry in corpus.entries:
        for pre in entry["prerequisites"]:
            if not corpus.has_id(pre):
                dangling.append(f"{entry['id']} -> {pre}")
    cycles: List[List[str]] = []
    visited: Dict[str, int] = {}  # 0=unseen 1=in-stack 2=done
    stack: List[str] = []

    def dfs(eid: str) -> None:
        visited[eid] = 1
        stack.append(eid)
        entry = corpus.get(eid)
        for pre in entry["prerequisites"] if entry else []:
            state = visited.get(pre, 0)
            if state == 1:
                cycles.append(stack[stack.index(pre):] + [pre])
            elif state == 0 and corpus.has_id(pre):
                dfs(pre)
        stack.pop()
        visited[eid] = 2

    for entry in corpus.entries:
        if visited.get(entry["id"], 0) == 0:
            dfs(entry["id"])
    return dangling, cycles


def prereq_depth(corpus: Corpus, entry_id: str, _memo: Dict[str, int] | None = None) -> int:
    """Longest prerequisite chain below an entry (cycle-safe)."""
    memo = _memo if _memo is not None else {}
    if entry_id in memo:
        return memo[entry_id]
    entry = corpus.get(entry_id)
    if not entry or not entry["prerequisites"]:
        memo[entry_id] = 0
        return 0
    # Cycle-safe: treat back-edges as depth 0 by seeding memo first.
    memo[entry_id] = 0
    depth = 1 + max((prereq_depth(corpus, p, memo) for p in entry["prerequisites"]), default=-1)
    memo[entry_id] = depth
    return depth


def progression(corpus: Corpus, track: str) -> List[Dict[str, object]]:
    """Entries in a track, in learning order: level, then prereq depth."""
    if track not in TRACKS:
        raise ValueError(f"unknown track {track!r} (want one of {', '.join(TRACKS)})")
    memo: Dict[str, int] = {}
    in_track = [e for e in corpus.entries if track in e["tracks"]]
    return sorted(
        in_track,
        key=lambda e: (LEVEL_ORDER[e["level"]], prereq_depth(corpus, e["id"], memo), e["title"]),
    )


def learning_path(corpus: Corpus, entry_id: str) -> List[Dict[str, object]]:
    """Prerequisite chain (topological, foundations first) then the entry."""
    entry = corpus.get(entry_id)
    if entry is None:
        raise KeyError(f"unknown entry id {entry_id!r}")
    ordered: List[Dict[str, object]] = []
    seen: set = set()

    def visit(eid: str) -> None:
        if eid in seen:
            return
        seen.add(eid)
        node = corpus.get(eid)
        if node is None:
            return
        for pre in node["prerequisites"]:
            visit(pre)
        ordered.append(node)

    visit(entry_id)
    return ordered


def track_counts(corpus: Corpus) -> Dict[str, int]:
    return {t: sum(1 for e in corpus.entries if t in e["tracks"]) for t in TRACKS}


def format_progression(corpus: Corpus, track: str) -> str:
    """Terse curriculum listing for ``levi course <track>``."""
    from levi.sidewinder import TRACK_DESCRIPTIONS

    entries = progression(corpus, track)
    lines = [f"COURSE — {track.upper()}: {TRACK_DESCRIPTIONS[track]}", f"{len(entries)} entries in learning order:"]
    last_level = None
    for entry in entries:
        if entry["level"] != last_level:
            last_level = entry["level"]
            lines.append(f"  [{last_level.upper()}]")
        pre = ", ".join(entry["prerequisites"]) if entry["prerequisites"] else "—"
        lines.append(f"    {entry['id']}  {entry['title']}  (needs: {pre})")
    return "\n".join(lines)


def format_learning_path(corpus: Corpus, entry_id: str) -> str:
    """Entry plus everything it builds on, in order."""
    from levi.sidewinder.curriculum.corpus import format_entry

    path = learning_path(corpus, entry_id)
    lines = [f"LEARNING PATH — {len(path)} steps to {entry_id}:"]
    for i, node in enumerate(path, 1):
        pre = f"[{node['level']}]"
        lines.append(f"  {i}. {node['id']} {pre} {node['title']}")
    lines.append("")
    lines.append(format_entry(path[-1]))
    return "\n".join(lines)
