"""SI dating — "skip the games"-style adult dating/classifieds module.

Listings are adult personals: headline, seeking, terms. Posting,
searching, and responding are all gate-locked; every user-supplied field
passes the bounds check; records are sealed at rest. Contact details
stay sealed inside the listing record — there is no public directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_read_all, si_update, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def post_listing(
    poster_id: str,
    headline: str,
    seeking: str,
    terms: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Post an adult dating listing. Gate-locked, bounds-checked, sealed."""
    require_adult(home)
    for field, name in ((headline, "headline"), (seeking, "seeking"), (terms, "terms")):
        if not field or not field.strip():
            raise ValueError("%s is required" % name)
        check_bounds(field, home)
    return si_write(
        home,
        "listings",
        {
            "track": TRACK_SI,
            "poster_id": poster_id,
            "headline": headline.strip(),
            "seeking": seeking.strip(),
            "terms": terms.strip(),
            "active": True,
            "posted_at": _utcnow(),
        },
    )


def search_listings(query: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Keyword search over active listings. Gate-locked."""
    require_adult(home)
    q = (query or "").strip().lower()
    out = []
    for listing in si_read_all(home, "listings"):
        if not listing.get("active"):
            continue
        hay = " ".join((listing["headline"], listing["seeking"], listing["terms"])).lower()
        if not q or q in hay:
            out.append(listing)
    return out


def respond(
    listing_id: str,
    responder_id: str,
    message: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Respond to a listing. Gate-locked, bounds-checked, sealed."""
    require_adult(home)
    listing = next((l for l in si_read_all(home, "listings") if l["id"] == listing_id), None)
    if listing is None or not listing.get("active"):
        raise ValueError("unknown or inactive listing %r" % listing_id)
    if not message or not message.strip():
        raise ValueError("message is required")
    check_bounds(message, home)
    return si_write(
        home,
        "responses",
        {
            "track": TRACK_SI,
            "listing_id": listing_id,
            "poster_id": listing["poster_id"],
            "responder_id": responder_id,
            "message": message.strip(),
            "sent_at": _utcnow(),
        },
    )


def deactivate(listing_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Take a listing down. Gate-locked; the record is updated and re-sealed."""
    require_adult(home)
    return si_update(home, "listings", listing_id, {"active": False, "deactivated_at": _utcnow()})
