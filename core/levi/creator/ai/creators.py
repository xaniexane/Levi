"""AI creator platform — general-audience creators, SFW.

Creator profiles, subscription tiers, messaging, and content drops for a
general audience: tutorials, art, music, writing, community. Same
functionality shape as the SI creator side, reformed content rules, money
through Cybrus only (fail-closed).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_AI
from levi.creator.ai.rules import check_sfw
from levi.creator.money import MoneyAuthorization, charge
from levi.creator.store import ai_read_all, ai_write

_HANDLE_RE = re.compile(r"^[a-z0-9_]{3,24}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_creator(
    handle: str,
    display_name: str,
    bio: str,
    category: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a general-audience creator profile. Rules-enforced."""
    if not _HANDLE_RE.match(handle or ""):
        raise ValueError("handle must be 3-24 chars of a-z, 0-9, underscore")
    if any(c["handle"] == handle for c in ai_read_all(home, "creators")):
        raise ValueError("handle %r is taken" % handle)
    return ai_write(
        home,
        "creators",
        {
            "track": TRACK_AI,
            "handle": handle,
            "display_name": check_sfw(display_name or "", home),
            "bio": check_sfw(bio or "", home),
            "category": check_sfw(category or "", home),
            "created_at": _utcnow(),
        },
    )


def list_creators(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return ai_read_all(home, "creators")


def add_tier(
    creator_handle: str,
    name: str,
    price_minor: int,
    perks: List[str],
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(price_minor, int) or price_minor <= 0:
        raise ValueError("price_minor must be a positive integer of minor units")
    if not any(c["handle"] == creator_handle for c in ai_read_all(home, "creators")):
        raise ValueError("unknown creator %r" % creator_handle)
    return ai_write(
        home,
        "creator_tiers",
        {
            "track": TRACK_AI,
            "creator_handle": creator_handle,
            "name": check_sfw(name or "", home),
            "price_minor": price_minor,
            "perks": [check_sfw(p, home) for p in (perks or [])],
            "created_at": _utcnow(),
        },
    )


def list_tiers(creator_handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [t for t in ai_read_all(home, "creator_tiers") if t["creator_handle"] == creator_handle]


def subscribe(
    creator_handle: str,
    tier_id: str,
    subscriber_id: str,
    authorization: MoneyAuthorization,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Subscribe to a tier. Payment through Cybrus only, fail-closed."""
    tier = next((t for t in ai_read_all(home, "creator_tiers") if t["id"] == tier_id), None)
    if tier is None or tier["creator_handle"] != creator_handle:
        raise ValueError("unknown tier %r for creator %r" % (tier_id, creator_handle))
    result = charge(
        amount_minor=tier["price_minor"],
        currency="USD",
        purpose="subscription:%s:%s" % (creator_handle, tier["name"]),
        identity=subscriber_id,
        authorization=authorization,
    )
    status = "active" if result["status"] == "moved" else "pending_payment"
    return ai_write(
        home,
        "creator_subscriptions",
        {
            "track": TRACK_AI,
            "creator_handle": creator_handle,
            "tier_id": tier_id,
            "subscriber_id": subscriber_id,
            "status": status,
            "plan_id": result["plan_id"],
            "charge": result["status"],
            "created_at": _utcnow(),
        },
    )


def post_drop(
    creator_handle: str,
    title: str,
    body: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Post a general-audience content drop. Rules-enforced."""
    return ai_write(
        home,
        "creator_drops",
        {
            "track": TRACK_AI,
            "creator_handle": creator_handle,
            "title": check_sfw(title or "", home),
            "body": check_sfw(body or "", home),
            "posted_at": _utcnow(),
        },
    )


def list_drops(creator_handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [d for d in ai_read_all(home, "creator_drops") if d["creator_handle"] == creator_handle]


def send_message(
    sender: str,
    recipient: str,
    body: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    if not body or not body.strip():
        raise ValueError("message body is required")
    return ai_write(
        home,
        "creator_messages",
        {
            "track": TRACK_AI,
            "sender": sender,
            "recipient": recipient,
            "body": check_sfw(body, home),
            "sent_at": _utcnow(),
        },
    )
