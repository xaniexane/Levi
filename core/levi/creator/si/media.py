"""SI private media — photos and videos as first-class content drops.

Private by default: a media drop is viewable by the owning creator, by
subscribers of the gated tier (a non-cancelled subscription), or by
explicitly granted subscribers — nobody else. The payload is sealed at
rest with the Veil-lineage envelope; nothing about the content leaks
into plaintext store files.

All entries are gate-locked (Plaiground law: adult-only, default OFF,
minors hard-locked out) and titles pass the bounds check.

Honest limits: media bytes live in the sealed local store (sane cap
below) — this is private local delivery, not a CDN. Payment is
paper-only until a Cybrus rail exists, so tier gating checks the
subscription record (non-cancelled), not a settled payment.
"""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_delete, si_read_all, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

MEDIA_KINDS = ("photo", "video")
# Sane local cap: sealed bytes stay in the local store, not a CDN.
_MAX_BYTES = 8 * 1024 * 1024


class MediaError(ValueError):
    """A media operation was invalid."""


class AccessDeniedError(PermissionError):
    """The viewer is not entitled to this media."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _b64_len_ok(data_b64: str) -> bytes:
    try:
        raw = base64.b64decode(data_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise MediaError("media data is not valid base64: %s" % exc) from exc
    if len(raw) > _MAX_BYTES:
        raise MediaError("media exceeds the %d-byte local cap" % _MAX_BYTES)
    if not raw:
        raise MediaError("media data is empty")
    return raw


def post_media(
    creator_handle: str,
    kind: str,
    title: str,
    filename: str,
    data_b64: str,
    tier_id: Optional[str] = None,
    grants: Optional[List[str]] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Post a private photo/video drop. Gate-locked, bounds-checked, sealed.

    Private by default: without a tier_id or grants, only the creator can
    view it. Open it via a subscription tier or per-subscriber grants.
    """
    require_adult(home)
    if kind not in MEDIA_KINDS:
        raise MediaError("kind must be one of %r" % (MEDIA_KINDS,))
    check_bounds(title or "", home)
    safe_name = os.path.basename((filename or "").strip())
    if not safe_name:
        raise MediaError("filename is required")
    raw = _b64_len_ok(data_b64)
    if tier_id is not None:
        tiers = [t for t in si_read_all(home, "tiers") if t["id"] == tier_id]
        if not tiers or tiers[0]["creator_handle"] != creator_handle:
            raise MediaError("unknown tier %r for creator %r" % (tier_id, creator_handle))
    record = si_write(
        home,
        "media",
        {
            "track": TRACK_SI,
            "creator_handle": creator_handle,
            "kind": kind,
            "title": (title or "").strip(),
            "filename": safe_name,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data_b64": data_b64,
            "tier_id": tier_id,
            "posted_at": _utcnow(),
        },
    )
    for subscriber_id in grants or []:
        grant_access(record["id"], creator_handle, subscriber_id, home)
    return record


def _get_media(media_id: str, home: Optional[Path]) -> Dict[str, Any]:
    media = next((m for m in si_read_all(home, "media") if m["id"] == media_id), None)
    if media is None:
        raise MediaError("unknown media %r" % media_id)
    return media


def grant_access(
    media_id: str,
    creator_handle: str,
    subscriber_id: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Grant one subscriber access to a media drop. Creator only."""
    require_adult(home)
    media = _get_media(media_id, home)
    if media["creator_handle"] != creator_handle:
        raise AccessDeniedError("only the owning creator can grant access")
    if not subscriber_id or not subscriber_id.strip():
        raise MediaError("subscriber_id is required")
    return si_write(
        home,
        "media_grants",
        {
            "track": TRACK_SI,
            "media_id": media_id,
            "subscriber_id": subscriber_id.strip(),
            "granted_by": creator_handle,
            "granted_at": _utcnow(),
        },
    )


def revoke_access(
    media_id: str,
    creator_handle: str,
    subscriber_id: str,
    home: Optional[Path] = None,
) -> bool:
    """Revoke a per-subscriber grant. Creator only. Returns True if removed."""
    require_adult(home)
    media = _get_media(media_id, home)
    if media["creator_handle"] != creator_handle:
        raise AccessDeniedError("only the owning creator can revoke access")
    grants = si_read_all(home, "media_grants")
    target = next(
        (
            g
            for g in grants
            if g["media_id"] == media_id and g["subscriber_id"] == subscriber_id
        ),
        None,
    )
    if target is None:
        return False
    return si_delete(home, "media_grants", target["id"])


def can_view(media_id: str, user_id: str, home: Optional[Path] = None) -> bool:
    """Access check. Never raises on unknown media — returns False."""
    require_adult(home)
    media = next((m for m in si_read_all(home, "media") if m["id"] == media_id), None)
    if media is None:
        return False
    if user_id == media["creator_handle"]:
        return True
    if media.get("tier_id"):
        subs = si_read_all(home, "subscriptions")
        if any(
            s["subscriber_id"] == user_id
            and s["tier_id"] == media["tier_id"]
            and s["status"] != "cancelled"
            for s in subs
        ):
            return True
    grants = si_read_all(home, "media_grants")
    return any(
        g["media_id"] == media_id and g["subscriber_id"] == user_id for g in grants
    )


def view(media_id: str, user_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Return the media manifest + payload. Denied unless entitled."""
    require_adult(home)
    media = next((m for m in si_read_all(home, "media") if m["id"] == media_id), None)
    if media is None:
        raise MediaError("unknown media %r" % media_id)
    if not can_view(media_id, user_id, home):
        raise AccessDeniedError("not entitled to view this media")
    return dict(media)


def list_media(
    creator_handle: str, user_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Media the viewer may see — metadata only, payloads stay sealed."""
    require_adult(home)
    out = []
    for media in si_read_all(home, "media"):
        if media["creator_handle"] != creator_handle:
            continue
        if not can_view(media["id"], user_id, home):
            continue
        meta = {k: v for k, v in media.items() if k != "data_b64"}
        out.append(meta)
    return out
