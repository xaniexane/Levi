"""SI creator profiles — adult creators, gated and sealed."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_read_all, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

_HANDLE_RE = re.compile(r"^[a-z0-9_]{3,24}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_profile(
    handle: str,
    display_name: str,
    bio: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create an adult creator profile. Gate-locked, bounds-checked, sealed."""
    require_adult(home)
    if not _HANDLE_RE.match(handle or ""):
        raise ValueError("handle must be 3-24 chars of a-z, 0-9, underscore")
    check_bounds(display_name or "", home)
    check_bounds(bio or "", home)
    if any(p["handle"] == handle for p in si_read_all(home, "profiles")):
        raise ValueError("handle %r is taken" % handle)
    return si_write(
        home,
        "profiles",
        {
            "track": TRACK_SI,
            "handle": handle,
            "display_name": display_name.strip(),
            "bio": bio.strip(),
            "adult_content": True,
            "created_at": _utcnow(),
        },
    )


def get_profile(handle: str, home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    require_adult(home)
    for p in si_read_all(home, "profiles"):
        if p["handle"] == handle:
            return p
    return None


def list_profiles(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    require_adult(home)
    return si_read_all(home, "profiles")
