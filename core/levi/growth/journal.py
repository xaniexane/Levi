"""The growth journal — baby Levi's baby book.

Every growth cycle appends one record to ``~/.levi/growth/journal.jsonl``:
what was harvested, what was learned, what was written to memory, and
which engine did the reflecting. Append-only: Levi's history is never
rewritten, only added to. (The user can always remove individual
learnings via ``levi growth forget``; the journal records that too.)
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def growth_dir() -> Path:
    """``~/.levi/growth`` (override with ``LEVI_GROWTH_DIR``)."""
    import os

    override = os.environ.get("LEVI_GROWTH_DIR")
    p = Path(override).expanduser() if override else Path.home() / ".levi" / "growth"
    p.mkdir(parents=True, exist_ok=True)
    return p


def journal_path() -> Path:
    return growth_dir() / "journal.jsonl"


def state_path() -> Path:
    return growth_dir() / "state.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_cycle_id() -> str:
    return f"cyc-{uuid.uuid4().hex[:8]}"


def append_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Append one journal record. Returns the record with id/ts filled in.

    Raises ValueError when ``entry`` is not a dict.
    """
    if not isinstance(entry, dict):
        raise ValueError(
            "append_entry: entry must be a dict, got %s" % type(entry).__name__
        )
    entry = dict(entry)
    entry.setdefault("id", new_cycle_id())
    entry.setdefault("ts", _now())
    entry.setdefault("kind", "cycle")
    with open(journal_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_entries(limit: int = 50) -> list[dict[str, Any]]:
    """Latest-first journal records (tolerates corrupt lines)."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(
            "read_entries: limit must be a positive int, got %r" % (limit,)
        )
    try:
        lines = journal_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[-limit:][::-1]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[-limit:][::-1]


def load_state() -> dict[str, Any]:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path())


# ---------------------------------------------------------------------------
# Developmental stages — a light, honest label for how far Levi has grown.
# This is engagement copy, not a cognitive claim: the stage is a pure
# function of consolidated learnings + completed cycles.
# ---------------------------------------------------------------------------

_STAGES = [
    (0, "newborn", "just opened its eyes — no learnings consolidated yet"),
    (1, "sprout", "first learnings taking root"),
    (10, "curious", "asking questions of its own experience now"),
    (30, "growing", "a real memory of how things work around here"),
    (100, "maturing", "seasoned — a long personal history to draw on"),
]


def developmental_stage(learnings: int, cycles: int) -> tuple[str, str]:
    for name, val in (("learnings", learnings), ("cycles", cycles)):
        if not isinstance(val, int) or val < 0:
            raise ValueError(
                "developmental_stage: %s must be a non-negative int, got %r"
                % (name, val)
            )
    name, blurb = "newborn", _STAGES[0][2]
    for threshold, sname, sblurb in _STAGES:
        if learnings >= threshold:
            name, blurb = sname, sblurb
    return name, f"{blurb} ({learnings} learnings over {cycles} cycles)"
