"""AI dating — SFW dating, society-approved.

Profiles with interests, interest-based matching, and messaging — all
under the SFW rules. The wholesome counterpart to the SI dating module;
same shape, clean content.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_AI
from levi.creator.ai.rules import check_sfw
from levi.creator.store import ai_read_all, ai_write

_HANDLE_RE = re.compile(r"^[a-z0-9_]{3,24}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_profile(
    handle: str,
    display_name: str,
    bio: str,
    interests: List[str],
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create an SFW dating profile. Rules-enforced."""
    if not _HANDLE_RE.match(handle or ""):
        raise ValueError("handle must be 3-24 chars of a-z, 0-9, underscore")
    clean_interests = [check_sfw(i, home) for i in (interests or [])]
    if any(p["handle"] == handle for p in ai_read_all(home, "dating_profiles")):
        raise ValueError("handle %r is taken" % handle)
    return ai_write(
        home,
        "dating_profiles",
        {
            "track": TRACK_AI,
            "handle": handle,
            "display_name": check_sfw(display_name or "", home),
            "bio": check_sfw(bio or "", home),
            "interests": clean_interests,
            "created_at": _utcnow(),
        },
    )


def list_profiles(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return ai_read_all(home, "dating_profiles")


def find_matches(handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Match by shared interests. Returns (profile, shared) pairs, best first."""
    profiles = {p["handle"]: p for p in ai_read_all(home, "dating_profiles")}
    me = profiles.get(handle)
    if me is None:
        raise ValueError("unknown profile %r" % handle)
    mine = {i.lower() for i in me["interests"]}
    scored = []
    for other_handle, other in profiles.items():
        if other_handle == handle:
            continue
        shared = sorted(mine & {i.lower() for i in other["interests"]})
        if shared:
            scored.append({"profile": other, "shared_interests": shared})
    scored.sort(key=lambda s: (-len(s["shared_interests"]), s["profile"]["handle"]))
    return scored


def send_message(
    sender: str,
    recipient: str,
    body: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Send a message. SFW rules enforced."""
    if not body or not body.strip():
        raise ValueError("message body is required")
    return ai_write(
        home,
        "dating_messages",
        {
            "track": TRACK_AI,
            "sender": sender,
            "recipient": recipient,
            "body": check_sfw(body, home),
            "sent_at": _utcnow(),
        },
    )


def inbox(handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [m for m in ai_read_all(home, "dating_messages") if m["recipient"] == handle]
