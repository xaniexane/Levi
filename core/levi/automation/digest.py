"""Automation run digest — bundle scattered automation events into one
readable summary.

LEVI's automation engine emits events (watcher triggers, flow runs,
routine plays, webhook deliveries). This module turns a pile of those
events into a compact ``Digest``: counts by kind, the headline items,
and a plain-text rendering. Digests persist as JSONL under
``~/.levi/automation/digests.jsonl`` (owner-only, atomic append).

Pure stdlib, local-first. ``home`` is injectable everywhere so tests
never touch the real ``~/.levi``.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Events carry at least ``kind`` (a short label) and ``text`` (one line).
#: Anything else is carried through untouched into the digest items.
_EVENT_KIND = "kind"
_EVENT_TEXT = "text"

#: Max headline items kept per digest; the rest are counted, not listed.
_MAX_ITEMS = 50


def _home() -> Path:
    return Path.home()


def _digests_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "automation" / "digests.jsonl"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Digest:
    """One bundled summary of automation events."""

    title: str
    created_at: str
    total_events: int
    counts_by_kind: Dict[str, int]
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Digest":
        return cls(
            title=str(raw.get("title", "")),
            created_at=str(raw.get("created_at", "")),
            total_events=int(raw.get("total_events", 0)),
            counts_by_kind=dict(raw.get("counts_by_kind", {})),
            items=list(raw.get("items", [])),
        )


def _coerce_event(event: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(event, dict):
        return None
    kind = str(event.get(_EVENT_KIND) or "misc").strip() or "misc"
    text = str(event.get(_EVENT_TEXT) or "").strip()
    if not text:
        return None
    item = dict(event)
    item[_EVENT_KIND] = kind
    item[_EVENT_TEXT] = text
    return item


def build_digest(
    events: List[Any],
    title: str,
    *,
    limit: int = _MAX_ITEMS,
) -> Digest:
    """Bundle ``events`` into a :class:`Digest`.

    Malformed events (not a dict, or no text) are skipped and counted as
    ``skipped`` — the digest never dies on one bad row. ``limit`` caps the
    headline items; everything else is counted by kind.
    """
    title = str(title or "").strip() or "Automation digest"
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _MAX_ITEMS
    limit = max(1, min(limit, _MAX_ITEMS))

    items: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    skipped = 0
    for raw in events or []:
        item = _coerce_event(raw)
        if item is None:
            skipped += 1
            continue
        counts[item[_EVENT_KIND]] = counts.get(item[_EVENT_KIND], 0) + 1
        if len(items) < limit:
            items.append(item)
    if skipped:
        counts["skipped"] = skipped
    return Digest(
        title=title,
        created_at=_utc_now(),
        total_events=sum(counts.values()),
        counts_by_kind=counts,
        items=items,
    )


def save_digest(digest: Digest, home: Optional[Path] = None) -> Path:
    """Append one digest to the local JSONL store (atomic, owner-only)."""
    path = _digests_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(digest.to_dict(), ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".digests-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            if path.exists():
                fh.write(path.read_text(encoding="utf-8"))
            fh.write(line)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def list_digests(home: Optional[Path] = None, *, limit: int = 10) -> List[Digest]:
    """Read back digests, newest first. A corrupt line is skipped, not fatal."""
    path = _digests_file(home)
    if not path.exists():
        return []
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, limit)
    digests: List[Digest] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            digests.append(Digest.from_dict(json.loads(line)))
        except (ValueError, TypeError, AttributeError):
            continue
    return list(reversed(digests[-limit:]))


def format_digest(digest: Digest) -> str:
    """Render a digest as plain text — the form a bot would speak."""
    lines = [f"=== {digest.title} ===", f"created: {digest.created_at}", ""]
    if not digest.total_events:
        lines.append("No events in this window.")
        return "\n".join(lines) + "\n"
    counts = ", ".join(
        f"{kind}: {n}" for kind, n in sorted(digest.counts_by_kind.items())
    )
    lines.append(f"{digest.total_events} events — {counts}")
    lines.append("")
    for item in digest.items:
        lines.append(f"[{item.get(_EVENT_KIND, 'misc')}] {item.get(_EVENT_TEXT, '')}")
    hidden = digest.total_events - len(digest.items)
    if hidden > 0:
        lines.append(f"... and {hidden} more counted above.")
    return "\n".join(lines) + "\n"
