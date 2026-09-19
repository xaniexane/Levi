"""SI dating privacy — airtight messaging around the listings module.

Chauncey's rule: "post a price, message airtight, nothing else escapes."

Three guarantees, enforced in code:

1. **Minimal metadata.** Public search returns redacted listing views —
   headline, seeking, terms — with NO poster identity. There is no public
   directory of who posted what.
2. **Explicit disclosure gates.** Responding to a listing reveals exactly
   what the responder authorizes and nothing more. ``reveal_profile``
   defaults to True (the responder's id is shown to the poster); passing
   False substitutes a pseudonym — the real identity stays sealed and is
   resolvable only by the responder themselves.
3. **Participant-only reads.** Responses are readable by the listing's
   poster or the responder — never by a third party, never by search.

All entries are gate-locked (Plaiground law); user text passes the
bounds check; records are sealed at rest. Response views returned to the
poster carry ``displayed_as``, never the raw responder identity unless
the responder explicitly allowed it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_read_all, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult


class PrivacyError(ValueError):
    """A privacy-guaranteed operation was refused."""


class PrivacyDeniedError(PermissionError):
    """The caller is not entitled to this private data."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alias(responder_id: str, listing_id: str) -> str:
    digest = hashlib.sha256(
        (responder_id + "|" + listing_id).encode("utf-8")
    ).hexdigest()[:10]
    return "anon_" + digest


def public_search(query: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Keyword search over active listings — redacted public view.

    Returns headline/seeking/terms only. Poster identities never leave
    through this path. Gate-locked.
    """
    require_adult(home)
    q = (query or "").strip().lower()
    out = []
    for listing in si_read_all(home, "listings"):
        if not listing.get("active"):
            continue
        hay = " ".join((listing["headline"], listing["seeking"], listing["terms"])).lower()
        if not q or q in hay:
            out.append(
                {
                    "id": listing["id"],
                    "headline": listing["headline"],
                    "seeking": listing["seeking"],
                    "terms": listing["terms"],
                    "posted_at": listing["posted_at"],
                }
            )
    return out


def respond(
    listing_id: str,
    responder_id: str,
    message: str,
    home: Optional[Path] = None,
    reveal_profile: bool = True,
) -> Dict[str, Any]:
    """Respond to a listing with an explicit disclosure gate.

    ``reveal_profile=True`` (default): the poster sees the responder's id.
    ``reveal_profile=False``: the poster sees a pseudonym; the real
    identity stays sealed and is resolvable only by the responder.
    Nothing is revealed beyond this explicit choice.
    """
    require_adult(home)
    listing = next(
        (l for l in si_read_all(home, "listings") if l["id"] == listing_id), None
    )
    if listing is None or not listing.get("active"):
        raise PrivacyError("unknown or inactive listing %r" % listing_id)
    if not responder_id or not responder_id.strip():
        raise PrivacyError("responder_id is required")
    if not message or not message.strip():
        raise PrivacyError("message is required")
    check_bounds(message, home)
    responder_id = responder_id.strip()
    return si_write(
        home,
        "responses",
        {
            "track": TRACK_SI,
            "listing_id": listing_id,
            "poster_id": listing["poster_id"],
            "responder_id": responder_id,
            "displayed_as": responder_id
            if reveal_profile
            else _alias(responder_id, listing_id),
            "revealed": bool(reveal_profile),
            "message": message.strip(),
            "sent_at": _utcnow(),
        },
    )


def _redact_for_poster(response: Dict[str, Any]) -> Dict[str, Any]:
    """The poster's view of a response — displayed identity only."""
    view = dict(response)
    view.pop("responder_id", None)
    view["from"] = response.get("displayed_as", response.get("responder_id"))
    return view


def read_responses_for_listing(
    listing_id: str, poster_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """All responses to one of the poster's listings. Poster only."""
    require_adult(home)
    listing = next(
        (l for l in si_read_all(home, "listings") if l["id"] == listing_id), None
    )
    if listing is None:
        raise PrivacyError("unknown listing %r" % listing_id)
    if listing["poster_id"] != poster_id:
        raise PrivacyDeniedError("only the listing's poster may read its responses")
    return [
        _redact_for_poster(r)
        for r in si_read_all(home, "responses")
        if r["listing_id"] == listing_id
    ]


def read_response(
    response_id: str, user_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Read one response. The listing's poster or the responder only.

    The poster gets the redacted view (displayed identity); the responder
    gets the full record including their own identity.
    """
    require_adult(home)
    response = next(
        (r for r in si_read_all(home, "responses") if r["id"] == response_id), None
    )
    if response is None:
        raise PrivacyError("unknown response %r" % response_id)
    if user_id == response["poster_id"]:
        return _redact_for_poster(response)
    if user_id == response["responder_id"]:
        return dict(response)
    raise PrivacyDeniedError("only the poster or the responder may read this")


def my_responses(responder_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The responder's own sent responses. Full records, own identity."""
    require_adult(home)
    return [
        dict(r)
        for r in si_read_all(home, "responses")
        if r["responder_id"] == responder_id
    ]
