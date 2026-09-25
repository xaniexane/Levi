"""Plaiground depth — companion continuity and rapport.

Companions get memory: a per-companion journal (owner-only, 0600),
a deterministic rapport meter computed from shared history, and a
recall summary for continuity across sessions. Depth is earned —
the journal only grows through actual interaction, and the rapport
meter reads the record rather than flattering the owner.

Gate-checked first; journal entries pass the bounds check. Stored
under the Plaiground directory alongside the gate record and
companion definitions.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.plaiground.bounds import check_bounds
from levi.plaiground.companions import get_companion
from levi.plaiground.gate import gate_dir, require_adult

TRACK = "si"
ZONE = "plaiground"

_DEPTH_SUBDIR = "depth"
_MAX_ENTRY_LEN = 2000
_MAX_ENTRIES = 500


def _depth_dir(home: Optional[Path] = None) -> Path:
    return gate_dir(home) / _DEPTH_SUBDIR


def _journal_path(companion_name: str, home: Optional[Path] = None) -> Path:
    slug = "".join(ch if ch.isalnum() else "-" for ch in companion_name.lower()).strip("-")
    return _depth_dir(home) / ("%s.jsonl" % (slug[:60] or "companion"))


def _read_entries(companion_name: str, home: Optional[Path] = None) -> List[Dict]:
    path = _journal_path(companion_name, home)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            entries.append(record)
    return entries


def remember(
    companion_name: str,
    entry: str,
    kind: str = "moment",
    home: Optional[Path] = None,
) -> Dict:
    """Write one journal entry for a companion. Bounds-checked, 0600."""
    require_adult(home)
    get_companion(companion_name, home=home)  # must exist
    entry = check_bounds(entry, home)
    if len(entry) > _MAX_ENTRY_LEN:
        raise ValueError("entry must be at most %d characters" % _MAX_ENTRY_LEN)
    if kind not in ("moment", "milestone", "preference", "inside-joke", "promise"):
        raise ValueError(
            "kind must be one of moment, milestone, preference, inside-joke, promise"
        )
    record = {
        "track": TRACK,
        "zone": ZONE,
        "companion": companion_name,
        "kind": kind,
        "entry": entry,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    d = _depth_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    path = _journal_path(companion_name, home)
    entries = _read_entries(companion_name, home)
    if len(entries) >= _MAX_ENTRIES:
        # Oldest out; the journal is a living record, not an archive.
        entries = entries[-(_MAX_ENTRIES - 1):]
        path.write_text(
            "".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8"
        )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    os.chmod(path, 0o600)
    return {"ok": True, "companion": companion_name, "kind": kind,
            "entries": len(_read_entries(companion_name, home))}


def recall(companion_name: str, limit: int = 10, home: Optional[Path] = None) -> Dict:
    """Continuity summary: the latest journal entries for a companion."""
    require_adult(home)
    get_companion(companion_name, home=home)
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer 1..50")
    entries = _read_entries(companion_name, home)[-limit:]
    return {
        "track": TRACK,
        "zone": ZONE,
        "companion": companion_name,
        "entries": entries,
        "count": len(entries),
    }


def rapport(companion_name: str, home: Optional[Path] = None) -> Dict:
    """A deterministic rapport meter, read from the actual record.

    Scores 0..100 from journal depth (entries, milestones, promises
    kept-or-noted) — earned, never flattered. Same record, same score.
    """
    require_adult(home)
    companion = get_companion(companion_name, home=home)
    entries = _read_entries(companion_name, home)
    kinds = [e.get("kind") for e in entries]
    score = min(40, len(entries) * 4)
    score += min(20, kinds.count("milestone") * 5)
    score += min(20, kinds.count("promise") * 5)
    score += min(20, kinds.count("inside-joke") * 4)
    score = max(0, min(100, score))
    if score < 20:
        band = "just met"
    elif score < 45:
        band = "warming up"
    elif score < 70:
        band = "in rhythm"
    elif score < 90:
        band = "deep water"
    else:
        band = "old souls"
    digest = hashlib.sha256(
        json.dumps(entries, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return {
        "track": TRACK,
        "zone": ZONE,
        "companion": companion["name"],
        "rapport": score,
        "band": band,
        "entries": len(entries),
        "record_digest": digest,
    }


def forget(companion_name: str, home: Optional[Path] = None) -> bool:
    """Delete a companion's journal. The owner can always start over."""
    require_adult(home)
    get_companion(companion_name, home=home)
    path = _journal_path(companion_name, home)
    if path.is_file():
        path.unlink()
        return True
    return False
