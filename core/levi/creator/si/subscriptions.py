"""SI subscriptions — tiers and paid subscribing, gated, money via Cybrus."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.money import MoneyAuthorization, charge
from levi.creator.store import si_read_all, si_update, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_tier(
    creator_handle: str,
    name: str,
    price_minor: int,
    perks: List[str],
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Add a subscription tier for a creator. Gate-locked."""
    require_adult(home)
    check_bounds(name or "", home)
    for perk in perks or []:
        check_bounds(perk, home)
    if not isinstance(price_minor, int) or price_minor <= 0:
        raise ValueError("price_minor must be a positive integer of minor units")
    if get_creator(creator_handle, home) is None:
        raise ValueError("unknown creator %r" % creator_handle)
    return si_write(
        home,
        "tiers",
        {
            "track": TRACK_SI,
            "creator_handle": creator_handle,
            "name": name.strip(),
            "price_minor": price_minor,
            "perks": list(perks or []),
            "created_at": _utcnow(),
        },
    )


def get_creator(handle: str, home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    require_adult(home)
    for p in si_read_all(home, "profiles"):
        if p["handle"] == handle:
            return p
    return None


def list_tiers(creator_handle: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    require_adult(home)
    return [t for t in si_read_all(home, "tiers") if t["creator_handle"] == creator_handle]


def subscribe(
    creator_handle: str,
    tier_id: str,
    subscriber_id: str,
    authorization: MoneyAuthorization,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Subscribe to a tier. Payment routes through Cybrus only.

    With no real rails the charge is blocked and the subscription is
    recorded as ``pending_payment`` — the intent is honest, money never
    moves.
    """
    require_adult(home)
    tier = next((t for t in si_read_all(home, "tiers") if t["id"] == tier_id), None)
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
    return si_write(
        home,
        "subscriptions",
        {
            "track": TRACK_SI,
            "creator_handle": creator_handle,
            "tier_id": tier_id,
            "subscriber_id": subscriber_id,
            "status": status,
            "plan_id": result["plan_id"],
            "charge": result["status"],
            "created_at": _utcnow(),
        },
    )


def list_subscriptions(subscriber_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    require_adult(home)
    return [s for s in si_read_all(home, "subscriptions") if s["subscriber_id"] == subscriber_id]


def cancel(subscription_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Cancel a subscription. The record is updated and re-sealed."""
    require_adult(home)
    return si_update(home, "subscriptions", subscription_id, {"status": "cancelled", "cancelled_at": _utcnow()})
