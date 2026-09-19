"""SI sealed messaging — Veil-lineage sealed DMs between adults."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_read_all, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def send(
    sender_id: str,
    recipient_id: str,
    body: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Send a sealed message. Gate-locked, bounds-checked, sealed at rest."""
    require_adult(home)
    if not body or not body.strip():
        raise ValueError("message body is required")
    check_bounds(body, home)
    return si_write(
        home,
        "messages",
        {
            "track": TRACK_SI,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "body": body,
            "sent_at": _utcnow(),
        },
    )


def inbox(user_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Messages received by a user. Gate-locked; envelopes verified on read."""
    require_adult(home)
    return [m for m in si_read_all(home, "messages") if m["recipient_id"] == user_id]


def thread(user_a: str, user_b: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Two-way thread between two users. Gate-locked."""
    require_adult(home)
    pair = {user_a, user_b}
    return [
        m
        for m in si_read_all(home, "messages")
        if {m["sender_id"], m["recipient_id"]} == pair
    ]
