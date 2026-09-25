"""AI media — SFW photos and videos as first-class content drops.

The reformed counterpart to the SI private media: same shape (kind,
tier gating, per-subscriber grants, private-by-default), clean rules —
every title passes the SFW check, the payload is general-audience, the
store is plain local JSONL. No gate on this track.
"""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_AI
from levi.creator.ai.rules import check_sfw
from levi.creator.store import ai_read_all, ai_write

MEDIA_KINDS = ("photo", "video")
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
    """Post an SFW photo/video drop. Rules-enforced, private by default."""
    if kind not in MEDIA_KINDS:
        raise MediaError("kind must be one of %r" % (MEDIA_KINDS,))
    title = check_sfw(title or "", home)
    safe_name = os.path.basename((filename or "").strip())
    if not safe_name:
        raise MediaError("filename is required")
    raw = _b64_len_ok(data_b64)
    if tier_id is not None:
        tiers = [t for t in ai_read_all(home, "creator_tiers") if t["id"] == tier_id]
        if not tiers or tiers[0]["creator_handle"] != creator_handle:
            raise MediaError("unknown tier %r for creator %r" % (tier_id, creator_handle))
    record = ai_write(
        home,
        "creator_media",
        {
            "track": TRACK_AI,
            "creator_handle": creator_handle,
            "kind": kind,
            "title": title,
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
    media = next(
        (m for m in ai_read_all(home, "creator_media") if m["id"] == media_id), None
    )
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
    media = _get_media(media_id, home)
    if media["creator_handle"] != creator_handle:
        raise AccessDeniedError("only the owning creator can grant access")
    if not subscriber_id or not subscriber_id.strip():
        raise MediaError("subscriber_id is required")
    return ai_write(
        home,
        "creator_media_grants",
        {
            "track": TRACK_AI,
            "media_id": media_id,
            "subscriber_id": subscriber_id.strip(),
            "granted_by": creator_handle,
            "granted_at": _utcnow(),
        },
    )


def can_view(media_id: str, user_id: str, home: Optional[Path] = None) -> bool:
    """Access check. Never raises on unknown media — returns False."""
    media = next(
        (m for m in ai_read_all(home, "creator_media") if m["id"] == media_id), None
    )
    if media is None:
        return False
    if user_id == media["creator_handle"]:
        return True
    if media.get("tier_id"):
        subs = ai_read_all(home, "creator_subscriptions")
        if any(
            s["subscriber_id"] == user_id
            and s["tier_id"] == media["tier_id"]
            and s["status"] != "cancelled"
            for s in subs
        ):
            return True
    grants = ai_read_all(home, "creator_media_grants")
    return any(
        g["media_id"] == media_id and g["subscriber_id"] == user_id for g in grants
    )


def view(media_id: str, user_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Return the media manifest + payload. Denied unless entitled."""
    media = _get_media(media_id, home)
    if not can_view(media_id, user_id, home):
        raise AccessDeniedError("not entitled to view this media")
    return dict(media)


def list_media(
    creator_handle: str, user_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Media the viewer may see — metadata only, payloads stay out."""
    out = []
    for media in ai_read_all(home, "creator_media"):
        if media["creator_handle"] != creator_handle:
            continue
        if not can_view(media["id"], user_id, home):
            continue
        out.append({k: v for k, v in media.items() if k != "data_b64"})
    return out
