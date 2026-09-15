"""Review queue — the HITL surface for King-level decisions.

Persisted JSON at ``<data_dir>/review.json`` with restrictive
permissions (0o600). Holds:

* ``pending`` — items awaiting a human: social packs queued by
  ``levi king social`` sit here until ``levi king approve <id>`` or
  ``levi king deny <id>`` decides them.
* ``approved`` / ``denied`` — decided items, with timestamps and notes.
* ``decisions`` — an audit log of engine pass-through decisions made by
  ``levi king deny`` / ``levi king approve`` *without* an id (those go
  straight to the manuscript engine's ``deny_last()``/``approve_last()``
  and are recorded here for the audit trail).

A social pack can only be posted after it leaves ``pending`` via
``approve`` — ``King.social_post`` refuses anything else. This is the
second HITL layer on top of the connector's own confirmation gate
(``--yes``): two independent gates, both required, neither bypassable
from inside King.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ledger import _default_data_dir, _write_json_600

_PENDING = "pending"
_APPROVED = "approved"
_DENIED = "denied"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "rev") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}"


def _bucket(raw: Any) -> List[Dict[str, Any]]:
    """Structural filter for loaded buckets: lists of dicts only."""
    if not isinstance(raw, list):
        return []
    return [i for i in raw if isinstance(i, dict)]


class ReviewError(Exception):
    """Unknown id, or a decision on an already-decided item."""


class ReviewQueue:
    """Pending/approved/denied items + a decision audit log."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else _default_data_dir()
        self.path = self.data_dir / "review.json"
        self.pending: List[Dict[str, Any]] = []
        self.approved: List[Dict[str, Any]] = []
        self.denied: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        self.pending = _bucket(raw.get("pending"))
        self.approved = _bucket(raw.get("approved"))
        self.denied = _bucket(raw.get("denied"))
        self.decisions = _bucket(raw.get("decisions"))

    def _persist(self) -> None:
        _write_json_600(
            self.path,
            {
                "pending": self.pending,
                "approved": self.approved,
                "denied": self.denied,
                "decisions": self.decisions[-500:],
            },
        )

    # -- queue ----------------------------------------------------------

    def queue_pack(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        """Add a generated social pack as a pending review item."""
        if not isinstance(pack, dict):
            raise ValueError(f"queue_pack needs a pack dict, got {type(pack).__name__}")
        caption = pack.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError("queue_pack: pack needs a non-empty string 'caption'")
        hashtags = pack.get("hashtags", [])
        if not isinstance(hashtags, list) or any(
            not isinstance(t, str) for t in hashtags
        ):
            raise ValueError("queue_pack: pack 'hashtags' must be a list of strings")
        platform = pack.get("platform")
        title = pack.get("title", "")
        if platform is not None and not isinstance(platform, str):
            raise ValueError("queue_pack: pack 'platform' must be a string")
        if not isinstance(title, str):
            raise ValueError("queue_pack: pack 'title' must be a string")
        item = {
            "id": _new_id(),
            "kind": "social-pack",
            "platform": platform,
            "title": title,
            "caption": caption,
            "hashtags": list(hashtags),
            "status": _PENDING,
            "created_ts": _utcnow(),
            "decided_ts": None,
            "note": "",
        }
        self.pending.append(item)
        self._persist()
        return item

    def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        for bucket in (self.pending, self.approved, self.denied):
            for item in bucket:
                if item.get("id") == item_id:
                    return item
        return None

    def approve(self, item_id: str, note: str = "") -> Dict[str, Any]:
        return self._decide(item_id, _APPROVED, note)

    def deny(self, item_id: str, note: str = "") -> Dict[str, Any]:
        return self._decide(item_id, _DENIED, note)

    def _decide(self, item_id: str, verdict: str, note: str) -> Dict[str, Any]:
        if not isinstance(item_id, str) or not item_id.strip():
            raise ReviewError(
                f"Cannot {verdict} {item_id!r}: item id must be a non-empty string."
            )
        if not isinstance(note, str):
            raise ValueError(f"decision note must be a string, got {note!r}")
        for i, item in enumerate(self.pending):
            if item.get("id") == item_id:
                decided = dict(item)
                decided["status"] = verdict
                decided["decided_ts"] = _utcnow()
                decided["note"] = note
                self.pending.pop(i)
                (self.approved if verdict == _APPROVED else self.denied).append(decided)
                self.decisions.append(
                    {
                        "ts": decided["decided_ts"],
                        "action": verdict,
                        "item_id": item_id,
                        "kind": item.get("kind"),
                        "note": note,
                    }
                )
                self._persist()
                return decided
        raise ReviewError(
            f"Cannot {verdict} {item_id!r}: not pending "
            "(unknown id or already decided)."
        )

    # -- audit ----------------------------------------------------------

    def log_decision(self, action: str, detail: str = "") -> Dict[str, Any]:
        """Audit-log an engine pass-through decision (deny/approve/rupture…)."""
        if not isinstance(action, str) or not action.strip():
            raise ValueError(f"log_decision action must be a non-empty string, got {action!r}")
        if not isinstance(detail, str):
            raise ValueError(f"log_decision detail must be a string, got {detail!r}")
        entry = {"ts": _utcnow(), "action": action, "detail": detail}
        self.decisions.append(entry)
        self._persist()
        return entry

    # -- read -----------------------------------------------------------

    def pending_count(self) -> int:
        return len(self.pending)

    def summary(self) -> Dict[str, Any]:
        return {
            "pending": len(self.pending),
            "approved": len(self.approved),
            "denied": len(self.denied),
            "decisions": len(self.decisions),
        }
