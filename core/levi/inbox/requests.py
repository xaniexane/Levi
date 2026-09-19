"""The feature/request box.

The user can drop a request in anytime from the companion chat box
(``/request <text>`` in the REPL, or ``levi inbox request "..."``).
Requests are stored locally under ``~/.levi/inbox/requests.jsonl``
(override with ``LEVI_INBOX_DIR``), owner-only, never transmitted.

Statuses: ``open`` → ``considered`` → ``building`` → ``done``.
Statuses only move forward; ``done`` is terminal.

Stdlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from levi.inbox.analytics import _append_line, _ensure_dir, default_inbox_dir

STATUSES = ("open", "considered", "building", "done")

_FILE = "requests.jsonl"


class RequestError(ValueError):
    """Bad request text, unknown id, or illegal status transition."""


@dataclass
class Request:
    id: int
    text: str
    status: str = "open"
    ts: str = ""
    updated: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "ts": self.ts,
            "updated": self.updated,
        }


class RequestBox:
    """Local request inbox: add, list, triage."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else default_inbox_dir()
        self.path = self.base_dir / _FILE
        _ensure_dir(self.base_dir)

    # -- internals -----------------------------------------------------

    def _load(self) -> List[Request]:
        out: List[Request] = []
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    try:
                        out.append(
                            Request(
                                id=int(d["id"]),
                                text=str(d["text"]),
                                status=str(d.get("status", "open")),
                                ts=str(d.get("ts", "")),
                                updated=str(d.get("updated", "")),
                            )
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
        except OSError:
            pass
        return out

    def _save(self, items: List[Request]) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for item in items:
                    fh.write(json.dumps(item.as_dict()) + "\n")
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise RequestError("cannot persist request box: %s" % exc)

    # -- public API ----------------------------------------------------

    def add(self, text: str) -> Request:
        text = " ".join((text or "").split())
        if not text:
            raise RequestError("request text is empty")
        if len(text) > 2000:
            raise RequestError("request text too long (max 2000 chars)")
        items = self._load()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        req = Request(
            id=(max((r.id for r in items), default=0) + 1),
            text=text,
            status="open",
            ts=now,
            updated=now,
        )
        items.append(req)
        self._save(items)
        return req

    def list(self, status: Optional[str] = None) -> List[Request]:
        items = self._load()
        if status is not None:
            if status not in STATUSES:
                raise RequestError("unknown status %r" % status)
            items = [r for r in items if r.status == status]
        return sorted(items, key=lambda r: r.id)

    def get(self, request_id: int) -> Request:
        for r in self._load():
            if r.id == int(request_id):
                return r
        raise RequestError("no request #%d" % request_id)

    def set_status(self, request_id: int, status: str) -> Request:
        if status not in STATUSES:
            raise RequestError("unknown status %r" % status)
        items = self._load()
        target = None
        for r in items:
            if r.id == int(request_id):
                target = r
                break
        if target is None:
            raise RequestError("no request #%d" % request_id)
        old_idx = STATUSES.index(target.status)
        new_idx = STATUSES.index(status)
        if new_idx < old_idx:
            raise RequestError(
                "status only moves forward: #%d is %r" % (target.id, target.status)
            )
        target.status = status
        target.updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._save(items)
        return target


def render_list(items: List[Request]) -> str:
    if not items:
        return "request box: empty — /request <text> drops one in"
    lines = [f"request box: {len(items)} request(s)"]
    for r in items:
        text = r.text if len(r.text) <= 100 else r.text[:97] + "..."
        lines.append(f"  #{r.id} [{r.status}] {text}")
    return "\n".join(lines)
