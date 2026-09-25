"""SI content drops — creator posts, gated, bounds-checked, sealed."""

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


def post_drop(
    creator_handle: str,
    title: str,
    body: str,
    tier_id: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Post a content drop. Gate-locked, bounds-checked, sealed at rest."""
    require_adult(home)
    check_bounds(title or "", home)
    check_bounds(body or "", home)
    return si_write(
        home,
        "drops",
        {
            "track": TRACK_SI,
            "creator_handle": creator_handle,
            "title": (title or "").strip(),
            "body": (body or "").strip(),
            "tier_id": tier_id,
            "posted_at": _utcnow(),
        },
    )


def list_drops(creator_handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    require_adult(home)
    return [d for d in si_read_all(home, "drops") if d["creator_handle"] == creator_handle]
