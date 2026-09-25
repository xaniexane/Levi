"""Creator content service — publish, gate, list, revoke.

Creators publish content items: metadata plus an encrypted/protected blob
reference. Payloads given at publish time are stored through the creator
store patterns (:mod:`levi.creator.store`) — sealed with the Veil-lineage
envelope on the SI track, plain local JSONL on the AI track. Never
plaintext secrets; the store is not a secret store.

LAWS (shared with :mod:`levi.creator.subscriptions`):

- L2 — Access to gated content requires a Cybrus-verified subscription
  token, checked server-side in ``levi.creator.subscriptions.verify_access``
  on every access. This module owns the GATE (per-item or tier-based);
  the subscription module owns the ENFORCEMENT.
- L5 — Publishing passes the safety.py track gates (SI: adult gate +
  bounds; AI: SFW rules), fail-closed. A gate violation blocks the
  publish — it cannot be bypassed.
- Gating honesty: list views are metadata-only for viewers who are not
  entitled (payload references stay out of list views).

Gate kinds: ``tier`` (requires a subscription at rank >= the item's
tier rank), ``grant`` (per-subscriber grants — PPV-style), ``public``
(everyone). A creator always sees their own content.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import subscriptions as _subs
from levi.creator.store import (
    ai_read_all,
    ai_update,
    ai_write,
    si_read_all,
    si_update,
    si_write,
)

CONTENT_KINDS = ("post", "photo", "video", "audio")

GATE_TIER = "tier"
GATE_GRANT = "grant"
GATE_PUBLIC = "public"


class ContentError(ValueError):
    """A content operation was invalid."""


def _read_all(track: str, home: Optional[Path], kind: str) -> List[Dict[str, Any]]:
    return si_read_all(home, kind) if track == TRACK_SI else ai_read_all(home, kind)


def _write(track: str, home: Optional[Path], kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
    return si_write(home, kind, record) if track == TRACK_SI else ai_write(home, kind, record)


def _update(
    track: str, home: Optional[Path], kind: str, record_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    return (
        si_update(home, kind, record_id, updates)
        if track == TRACK_SI
        else ai_update(home, kind, record_id, updates)
    )


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# -- Publishing ---------------------------------------------------------


def publish(
    creator_id: str,
    title: str,
    description: str,
    kind: str,
    track: str,
    home: Optional[Path] = None,
    tier_id: Optional[str] = None,
    data_b64: Optional[str] = None,
    blob_ref: Optional[str] = None,
    grants: Optional[List[str]] = None,
    public: bool = False,
) -> Dict[str, Any]:
    """Publish a content item.

    Gate: exactly one of ``tier_id`` (tier-based gating), ``grants``
    (per-subscriber grants — PPV-style), or ``public=True``. Payload:
    either ``data_b64`` (stored sealed through the store — the SI track
    seals it, the AI track keeps it local) or ``blob_ref`` (an opaque
    external reference — never a secret). L5 safety gates apply to the
    title/description and cannot be bypassed.
    """
    _subs._guard(track, home, title, description)  # L5: gate + rules first
    creator = _subs.get_profile(creator_id, track, home)
    if kind not in CONTENT_KINDS:
        raise ContentError("kind must be one of %r" % (CONTENT_KINDS,))
    chosen = [tier_id is not None, bool(grants), bool(public)]
    if sum(chosen) != 1:
        raise ContentError(
            "exactly one gate is required: tier_id, grants, or public=True"
        )
    if tier_id is not None:
        tier = _subs.get_tier(tier_id, track, home)
        if tier["creator_id"] != creator_id:
            raise ContentError("tier %r does not belong to creator %r" % (tier_id, creator_id))
        gate: Dict[str, Any] = {
            "kind": GATE_TIER,
            "tier_id": tier_id,
            "tier_rank": tier.get("rank", 0),
            "tier_name": tier["name"],
        }
    elif grants:
        gate = {"kind": GATE_GRANT, "subscribers": sorted(set(grants))}
    else:
        gate = {"kind": GATE_PUBLIC}

    if data_b64 is not None and blob_ref is not None:
        raise ContentError("give data_b64 or blob_ref, not both")
    blob_id: Optional[str] = None
    if data_b64 is not None:
        try:
            base64.b64decode(data_b64.encode("ascii"))
        except Exception as exc:
            raise ContentError("data_b64 is not valid base64: %s" % exc) from exc
        # Stored through the store patterns: sealed on SI, plain on AI.
        # Payloads are protected blobs — never secrets, never plaintext
        # credentials; publishing a secret here is a caller error, not a
        # feature (the L4 rule rides along).
        blob = _write(
            track,
            home,
            "content_blobs",
            {
                "track": track,
                "creator_id": creator["id"],
                "kind": kind,
                "data_b64": data_b64,
                "created_at": _utcnow_iso(),
            },
        )
        blob_id = blob["id"]
    return _write(
        track,
        home,
        "content_items",
        {
            "track": track,
            "creator_id": creator["id"],
            "title": title,
            "description": description,
            "kind": kind,
            "blob_id": blob_id,
            "blob_ref": blob_ref,
            "gate": gate,
            "status": "live",
            "created_at": _utcnow_iso(),
        },
    )


def get_item(content_id: str, track: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch one content item (full record). Gate applies."""
    _subs._guard(track, home)
    item = next(
        (i for i in _read_all(track, home, "content_items") if i["id"] == content_id),
        None,
    )
    if item is None:
        raise ContentError("unknown content %r" % content_id)
    return item


def _teaser(item: Dict[str, Any]) -> Dict[str, Any]:
    """Metadata-only view: payload references stay out of list views for
    viewers who are not entitled (the M1 attachment-sealing honesty)."""
    return {
        "id": item["id"],
        "creator_id": item["creator_id"],
        "title": item["title"],
        "description": item["description"],
        "kind": item["kind"],
        "gate_kind": item["gate"]["kind"],
        "gate_tier_name": item["gate"].get("tier_name"),
        "status": item["status"],
        "created_at": item["created_at"],
        "accessible": False,
    }


def _full(item: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(_teaser(item))
    out["accessible"] = True
    out["blob_id"] = item.get("blob_id")
    out["blob_ref"] = item.get("blob_ref")
    return out


def list_content(
    creator_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The creator's own content — full records (creator's own view)."""
    _subs._guard(track, home)
    _subs.get_profile(creator_id, track, home)
    return [
        _full(i)
        for i in _read_all(track, home, "content_items")
        if i["creator_id"] == creator_id
    ]


def list_for_viewer(
    creator_id: str,
    viewer_id: str,
    track: str,
    home: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Content as a viewer sees it: full records where entitled,
    metadata-only teasers where not. Payload references never leak to
    non-entitled viewers."""
    _subs._guard(track, home)
    _subs.get_profile(creator_id, track, home)
    if viewer_id == creator_id:
        return list_content(creator_id, track, home)
    level = _subs.access_level(viewer_id, creator_id, track, home)
    out = []
    for item in _read_all(track, home, "content_items"):
        if item["creator_id"] != creator_id:
            continue
        granted, _ = evaluate_gate(
            item,
            creator_id=creator_id,
            subscriber_id=viewer_id,
            tier_rank=level["tier_rank"],
            track=track,
            home=home,
        )
        out.append(_full(item) if granted else _teaser(item))
    return out


def revoke(
    content_id: str, creator_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Revoke a content item. Creator only. Revoked items deny all access
    (even valid tokens) and stay listed as revoked."""
    _subs._guard(track, home)
    item = get_item(content_id, track, home)
    if item["creator_id"] != creator_id:
        raise ContentError("this content is not yours")
    if item["status"] == "revoked":
        return item
    return _update(
        track,
        home,
        "content_items",
        content_id,
        {"status": "revoked", "revoked_at": _utcnow_iso()},
    )


# -- Per-item grants (PPV-style) ----------------------------------------


def grant(
    content_id: str,
    creator_id: str,
    subscriber_id: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Grant one subscriber access to a grant-gated item. Creator only."""
    _subs._guard(track, home)
    item = get_item(content_id, track, home)
    if item["creator_id"] != creator_id:
        raise ContentError("this content is not yours")
    if item["gate"]["kind"] != GATE_GRANT:
        raise ContentError("grants apply only to grant-gated items")
    current = list(item["gate"].get("subscribers", []))
    if subscriber_id not in current:
        current.append(subscriber_id)
    gate = dict(item["gate"])
    gate["subscribers"] = sorted(current)
    return _update(track, home, "content_items", content_id, {"gate": gate})


def ungrant(
    content_id: str,
    creator_id: str,
    subscriber_id: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Remove a subscriber's grant. Creator only."""
    _subs._guard(track, home)
    item = get_item(content_id, track, home)
    if item["creator_id"] != creator_id:
        raise ContentError("this content is not yours")
    if item["gate"]["kind"] != GATE_GRANT:
        raise ContentError("grants apply only to grant-gated items")
    gate = dict(item["gate"])
    gate["subscribers"] = [s for s in gate.get("subscribers", []) if s != subscriber_id]
    return _update(track, home, "content_items", content_id, {"gate": gate})


def grants_for(
    subscriber_id: str, creator_id: str, track: str, home: Optional[Path] = None
) -> Set[str]:
    """Content ids this subscriber holds grants for (live items only)."""
    out: Set[str] = set()
    for item in _read_all(track, home, "content_items"):
        if (
            item["creator_id"] == creator_id
            and item["status"] == "live"
            and item["gate"]["kind"] == GATE_GRANT
            and subscriber_id in item["gate"].get("subscribers", [])
        ):
            out.add(item["id"])
    return out


# -- The gate (evaluated server-side by verify_access) --------------------


def evaluate_gate(
    item: Dict[str, Any],
    *,
    creator_id: str,
    subscriber_id: str,
    tier_rank: Optional[int],
    track: str,
    home: Optional[Path] = None,
) -> tuple:
    """Decide access for one item. Pure decision logic — no tokens, no
    stores, no trust. Returns ``(granted: bool, reason: str)``.

    Rules, in order: revoked denies everything; the creator always sees
    their own; tier gate needs subscriber rank >= item tier rank;
    grant gate needs the subscriber on the grant list; public grants all.
    """
    _ = (track, home)  # the gate is the same on both tracks; signature parity
    if item.get("status") == "revoked":
        return False, "content revoked"
    if subscriber_id == creator_id:
        return True, "creator owns this content"
    gate = item.get("gate", {})
    kind = gate.get("kind")
    if kind == GATE_PUBLIC:
        return True, "public content"
    if kind == GATE_GRANT:
        if subscriber_id in gate.get("subscribers", []):
            return True, "per-item grant"
        return False, "no grant for this subscriber"
    if kind == GATE_TIER:
        need = int(gate.get("tier_rank", 0))
        if tier_rank is not None and int(tier_rank) >= need:
            return True, "tier rank %d >= required %d" % (tier_rank, need)
        return False, "requires tier rank %d (subscriber has %s)" % (need, tier_rank)
    return False, "unknown gate kind"
