"""The Rescue Stone — append-only record of every rescue.

One ``stone.jsonl`` per rescue home. Every stage transition appends an
entry ``{ts, event, episode_id, detail}``. There is deliberately NO
delete path: this module exposes no deletion API at all. Nothing is
ever deleted; the stone records every rescue.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import rescue_home


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stone_path(home=None):
    return rescue_home(home) / "stone.jsonl"


def record(
    home, event: str, episode_id: str, detail: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Append one entry to the stone. Never overwrites, never deletes."""
    if not event or not event.strip():
        raise ValueError("record: event name required")
    entry = {
        "ts": _now(),
        "event": event,
        "episode_id": episode_id,
        "detail": dict(detail or {}),
    }
    path = _stone_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def ledger(home=None) -> List[Dict[str, Any]]:
    """Read the whole stone, oldest first. No delete path exists."""
    path = _stone_path(home)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def episodes(home=None) -> List[str]:
    """Every episode id the stone has ever seen, in first-seen order."""
    seen: List[str] = []
    for entry in ledger(home):
        eid = entry.get("episode_id")
        if eid and eid not in seen:
            seen.append(eid)
    return seen


__all__ = ["episodes", "ledger", "record"]
