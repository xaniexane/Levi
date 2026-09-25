"""hub.hitl: human-in-the-loop approval checkpoints.

The original had HITL checkpoints everywhere in spirit; here they are a
real queue in sqlite. Anything consequential — shell execution, writing
files outside a scratch dir, staging job applications, materializing an
Alpha build — must hold an approved HITL record. Advisory reads never
need one.

Flow: ``request_approval(kind, detail)`` -> id (pending) ->
founder approves via CLI/UI/API -> ``decide(id, True)`` ->
``is_approved(id)`` gates the act.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_approval(
    kind: str, detail: Dict[str, Any], *, path: Optional[Path] = None
) -> Dict[str, Any]:
    """Open an approval request. Returns the pending record (id included)."""
    if not kind or not kind.strip():
        raise ValueError("kind is required")
    conn = store.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO hitl (kind, detail, status, created) VALUES (?, ?, 'pending', ?)",
            (kind.strip(), json.dumps(detail or {}), _now()),
        )
        conn.commit()
        return {
            "ok": True,
            "id": cur.lastrowid,
            "kind": kind.strip(),
            "status": "pending",
            "label": "OBSERVED",
        }
    finally:
        conn.close()


def pending(*, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = store.connect(path)
    try:
        rows = conn.execute(
            "SELECT id, kind, detail, status, created FROM hitl "
            "WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "kind": r["kind"],
                "detail": json.loads(r["detail"]),
                "status": r["status"],
                "created": r["created"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def decide(
    request_id: int, approved: bool, *, note: str = "", path: Optional[Path] = None
) -> Dict[str, Any]:
    """Approve or reject a pending request. Returns the updated record."""
    conn = store.connect(path)
    try:
        row = conn.execute(
            "SELECT status FROM hitl WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"no HITL request {request_id}")
        if row["status"] != "pending":
            raise ValueError(f"request {request_id} already {row['status']}")
        status = "approved" if approved else "rejected"
        conn.execute(
            "UPDATE hitl SET status = ?, decided_at = ?, note = ? WHERE id = ?",
            (status, _now(), note or "", request_id),
        )
        conn.commit()
        return {"ok": True, "id": request_id, "status": status}
    finally:
        conn.close()


def is_approved(request_id: int, *, path: Optional[Path] = None) -> bool:
    conn = store.connect(path)
    try:
        row = conn.execute(
            "SELECT status FROM hitl WHERE id = ?", (request_id,)
        ).fetchone()
        return bool(row) and row["status"] == "approved"
    finally:
        conn.close()


class ApprovalRequired(Exception):
    """Raised when a consequential act has no approved HITL record."""


def require(request_id: Optional[int], *, path: Optional[Path] = None) -> None:
    """Gate: raise ApprovalRequired unless the request id is approved."""
    if request_id is None or not is_approved(request_id, path=path):
        raise ApprovalRequired(
            "consequential act needs an approved HITL request — "
            "open one with hitl.request_approval() and wait for the founder's word"
        )
