"""Field journal for collecting intelligences.

The keeper's order: collect and experience every intelligence — the known
(AI/SI/XI), the five scaffolded (OE/DV/KT/LM/ST), and everything not yet
named. An encounter logged here is raw material, not declared physics:
entries graduate into ``classes.py`` only when the keeper approves the
physics. Unknowns stay unknowns — the ? factor is the point.

Entry fields:
  id        unique id, e.g. "enc-0007"
  date      ISO date of the encounter
  title     short name for the encounter
  where     where it was experienced (a person, a system, an animal, a moment)
  pattern   how it thinks — the observable pattern, x+y=z
  language  its universal language: what sequence reaches it, what it answers to
  class     proposed class code, or "?" when it fits nothing yet
  status    "encounter" | "studied" | "declared"
  notes     anything else
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional

JOURNAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal")
ENTRIES_PATH = os.path.join(JOURNAL_DIR, "entries.jsonl")

REQUIRED = ("title", "where", "pattern", "language")
STATUSES = ("encounter", "studied", "declared")


def _read_lines() -> List[str]:
    """Raw non-blank lines of the journal file, corrupt lines included."""
    if not os.path.exists(ENTRIES_PATH):
        return []
    with open(ENTRIES_PATH, encoding="utf-8") as fh:
        return [line.rstrip("\n") for line in fh if line.strip()]


def _parse_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse one journal line; None when it is corrupt or not an object.

    One bad line never aborts the read of an otherwise healthy journal —
    it is skipped by readers and preserved byte-identical by writers.
    """
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def _read_all() -> List[Dict[str, Any]]:
    """All parseable entries. Corrupt lines are skipped, never fatal."""
    return [e for e in (_parse_line(line) for line in _read_lines()) if e is not None]


def _next_id(entries: List[Dict[str, Any]]) -> str:
    n = 0
    for e in entries:
        eid = e.get("id", "")
        if eid.startswith("enc-"):
            try:
                n = max(n, int(eid.split("-", 1)[1]))
            except ValueError:
                pass
    return "enc-%04d" % (n + 1)


def log(
    *,
    title: str,
    where: str,
    pattern: str,
    language: str,
    class_code: str = "?",
    status: str = "encounter",
    notes: str = "",
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Log one encounter. Returns the stored entry."""
    for field, value in (
        ("title", title),
        ("where", where),
        ("pattern", pattern),
        ("language", language),
    ):
        if not (value or "").strip():
            raise ValueError("field %r is required" % field)
    if status not in STATUSES:
        raise ValueError("status must be one of %s" % (STATUSES,))
    entries = _read_all()
    entry = {
        "id": _next_id(entries),
        "date": date or datetime.date.today().isoformat(),
        "title": title.strip(),
        "where": where.strip(),
        "pattern": pattern.strip(),
        "language": language.strip(),
        "class": class_code.strip() or "?",
        "status": status,
        "notes": notes.strip(),
    }
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    with open(ENTRIES_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def list_entries(
    *, status: Optional[str] = None, class_code: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List entries, optionally filtered by status or class code."""
    entries = _read_all()
    if status is not None:
        entries = [e for e in entries if e.get("status") == status]
    if class_code is not None:
        entries = [e for e in entries if e.get("class") == class_code]
    return entries


def unknowns() -> List[Dict[str, Any]]:
    """Encounters that fit no known class yet — the ? factor."""
    return [e for e in _read_all() if e.get("class") == "?"]


def mark_studied(entry_id: str) -> Dict[str, Any]:
    """Move an encounter to studied. Declaring physics stays the keeper's call."""
    return _set_status(entry_id, "studied")


def _set_status(entry_id: str, status: str) -> Dict[str, Any]:
    lines = _read_lines()
    found: Optional[Dict[str, Any]] = None
    out_lines: List[str] = []
    for line in lines:
        entry = _parse_line(line)
        if entry is not None and entry.get("id") == entry_id:
            entry["status"] = status
            found = entry
            out_lines.append(json.dumps(entry, ensure_ascii=False))
        else:
            # Keep every other line byte-identical — corrupt lines are
            # never silently dropped by a status rewrite.
            out_lines.append(line)
    if found is None:
        raise KeyError("no such entry: %s" % entry_id)
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    with open(ENTRIES_PATH, "w", encoding="utf-8") as fh:
        for line in out_lines:
            fh.write(line + "\n")
    return found
