"""Veil Messenger — AI track (Echoverse).

The reformed counterpart to the SI messenger: same shape (outbox,
ternary delivery, receipts, attested bundles, attachments with
per-tier grants), clean rules — message text passes the SFW check,
records are plain local JSONL, and there is NO adult gate on this
track. The AI track is readable by design; it says so plainly instead
of performing privacy it doesn't have (the encryption-theater
reversal).

Track law: this module touches ONLY the AI store (``ai_*``), the AI
rules, and the AI chat containers. It never touches the SI track, the
Plaiground gate, or the sealing module. Track isolation is asserted
by test, not just by convention.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_AI
from levi.creator.ai import chats as ai_chats
from levi.creator.ai.rules import check_sfw
from levi.creator.store import ai_read_all, ai_update, ai_write
from levi.creator.veil import (
    ATTEST_ALG,
    ATTEST_V,
    ATTACH_TIERS,
    DEFAULT_ATTACH_TIER,
    MAX_ATTACHMENT_BYTES,
    AttestationError,
    DeliveryDeniedError,
    MessengerError,
    QUEUED,
    SYNCED,
    DELIVERED,
)

# -- Store kinds (new, AI-only) ---------------------------------------------
_K_MESSAGES = "veil_ai_messages"
_K_OUTBOX = "veil_ai_outbox"
_K_RECEIPTS = "veil_ai_receipts"
_K_ATTACHMENTS = "veil_ai_attachments"
_K_GRANTS = "veil_ai_grants"
_K_IMPORTS = "veil_ai_imports"

_ATTEST_FILE = "attest.key"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ai_dir(home: Optional[Path]) -> Path:
    from levi.creator.store import _ai_dir as _store_ai_dir

    return _store_ai_dir(home)


def _attest_key(home: Optional[Path]) -> bytes:
    """Per-track attestation key (AI dir, 0600). Never the SI keeper key."""
    p = _ai_dir(home) / _ATTEST_FILE
    if p.exists():
        data = p.read_bytes()
        if len(data) == 32:
            return data
    p.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    os.chmod(p, 0o600)
    return key


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _member_chat(
    chat_id: str, user_id: str, home: Optional[Path], require_open: bool = False
) -> Dict[str, Any]:
    """Membership enforced on every send AND every read — no gate on this track."""
    for chat in ai_chats.list_chats(user_id, home):
        if chat["id"] == chat_id:
            if require_open and not chat.get("open", True):
                raise MessengerError("this chat is closed — readable, silent")
            return chat
    raise DeliveryDeniedError("not a member of this chat")


# -- Ternary delivery: queue -> flush -> export ------------------------------


def queue_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Stage a message in the outbox (QUEUED). Explicit flush delivers it."""
    _member_chat(chat_id, sender_id, home, require_open=True)
    clean = check_sfw(body or "", home)
    entry = ai_write(
        home,
        _K_OUTBOX,
        {
            "track": TRACK_AI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "body": clean,
            "state": QUEUED,
            "queued_at": _utcnow(),
        },
    )
    return {"outbox_id": entry["id"], "chat_id": chat_id, "state": QUEUED}


def flush_outbox(
    home: Optional[Path] = None, chat_id: Optional[str] = None
) -> List[str]:
    """Owner-initiated local flush: QUEUED -> DELIVERED with receipts."""
    delivered: List[str] = []
    for entry in ai_read_all(home, _K_OUTBOX):
        if entry.get("state") != QUEUED:
            continue
        if chat_id is not None and entry.get("chat_id") != chat_id:
            continue
        try:
            _member_chat(entry["chat_id"], entry["sender_id"], home, require_open=True)
        except (DeliveryDeniedError, MessengerError):
            continue  # stays QUEUED — fail closed
        msg = ai_write(
            home,
            _K_MESSAGES,
            {
                "track": TRACK_AI,
                "chat_id": entry["chat_id"],
                "sender_id": entry["sender_id"],
                "body": entry["body"],
                "queued_at": entry["queued_at"],
                "delivered_at": _utcnow(),
            },
        )
        ai_write(
            home,
            _K_RECEIPTS,
            {
                "track": TRACK_AI,
                "msg_id": msg["id"],
                "chat_id": entry["chat_id"],
                "state": DELIVERED,
                "at": _utcnow(),
                "verifier": "local-flush",
            },
        )
        ai_update(
            home, _K_OUTBOX, entry["id"], {"state": DELIVERED, "msg_id": msg["id"]}
        )
        delivered.append(msg["id"])
    return delivered


def send_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Queue + flush in one call: instant local delivery, no server."""
    entry = queue_message(chat_id, sender_id, body, home)
    ids = flush_outbox(home, chat_id=chat_id)
    if not ids:
        raise MessengerError("message queued but flush refused to deliver it")
    return {"msg_id": ids[-1], "outbox_id": entry["outbox_id"], "state": DELIVERED}


def outbox(
    home: Optional[Path] = None,
    chat_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Outbox listing — metadata plus body length, no surprises."""
    rows = []
    for entry in ai_read_all(home, _K_OUTBOX):
        if chat_id is not None and entry.get("chat_id") != chat_id:
            continue
        if user_id is not None and entry.get("sender_id") != user_id:
            continue
        rows.append(dict(entry))
    return rows


def delivery_receipts(
    home: Optional[Path] = None,
    chat_id: Optional[str] = None,
    msg_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Local delivery receipts: the proof delivery happened on-device."""
    rows = []
    for rec in ai_read_all(home, _K_RECEIPTS):
        if chat_id is not None and rec.get("chat_id") != chat_id:
            continue
        if msg_id is not None and rec.get("msg_id") != msg_id:
            continue
        rows.append(dict(rec))
    return rows


# -- Reading ----------------------------------------------------------------


def read_thread(
    chat_id: str, user_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Read a chat's messages. Members only; closed chats stay readable.

    Plain records on this track — no sealing theater. What you read is
    what the local store holds.
    """
    _member_chat(chat_id, user_id, home, require_open=False)
    return [
        {
            "id": rec["id"],
            "chat_id": chat_id,
            "sender_id": rec["sender_id"],
            "body": rec["body"],
            "queued_at": rec.get("queued_at"),
            "delivered_at": rec.get("delivered_at"),
        }
        for rec in ai_read_all(home, _K_MESSAGES)
        if rec.get("chat_id") == chat_id
    ]


# -- Portability: attested bundles, owner-initiated --------------------------


def _import_map(
    manifest_chat_id: str, signer: str, home: Optional[Path]
) -> Optional[str]:
    """Where did this owner's earlier import of this bundled chat land?"""
    for r in ai_read_all(home, _K_IMPORTS):
        if r.get("manifest_chat_id") == manifest_chat_id and r.get("signer") == signer:
            return r.get("local_chat_id")
    return None


def _locate_local_chat(
    manifest: Dict[str, Any],
    importer_id: str,
    members: List[str],
    old_chat_id: str,
    home: Optional[Path],
) -> Dict[str, Any]:
    """Find or create the local chat container; re-imports of the same
    bundle map back to the same local chat via import provenance."""
    containers = ai_chats.list_chats(importer_id, home)
    local = next((c for c in containers if c["id"] == old_chat_id), None)
    if local is None:
        mapped = _import_map(old_chat_id, importer_id, home)
        if mapped is not None:
            local = next((c for c in containers if c["id"] == mapped), None)
    if local is not None:
        return local
    owner = str(manifest.get("owner") or importer_id)
    if manifest.get("kind") == "dm":
        others = [m for m in members if m != owner]
        if not others:
            raise MessengerError("bundled dm has no other party")
        local = ai_chats.create_chat(owner, others[0], home)
    else:
        local = ai_chats.create_group(owner, manifest.get("name") or "", members, home)
    ai_write(
        home,
        _K_IMPORTS,
        {
            "track": TRACK_AI,
            "signer": importer_id,
            "manifest_chat_id": old_chat_id,
            "local_chat_id": local["id"],
            "imported_at": _utcnow(),
        },
    )
    return local


def export_bundle(
    chat_id: str, user_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Export a chat's history as an attested bundle. Owner-initiated."""
    chat = _member_chat(chat_id, user_id, home, require_open=False)
    messages = read_thread(chat_id, user_id, home)
    bundle = {
        "v": 1,
        "track": TRACK_AI,
        "chat": {
            "id": chat["id"],
            "kind": chat.get("kind"),
            "owner": chat.get("owner"),
            "name": chat.get("name"),
            "members": list(chat.get("members", [])),
            "open": bool(chat.get("open", True)),
        },
        "messages": messages,
        "exported_by": user_id,
        "exported_at": _utcnow(),
    }
    attestation = {
        "v": ATTEST_V,
        "alg": ATTEST_ALG,
        "signer": user_id,
        "chat_id": chat_id,
        "exported_at": bundle["exported_at"],
    }
    mac = hmac.new(_attest_key(home), _canonical(bundle), hashlib.sha256).hexdigest()
    attestation["mac"] = mac
    msg_ids = {m["id"] for m in messages}
    for entry in ai_read_all(home, _K_OUTBOX):
        if entry.get("state") == DELIVERED and entry.get("msg_id") in msg_ids:
            ai_update(home, _K_OUTBOX, entry["id"], {"state": SYNCED})
    for rec in ai_read_all(home, _K_RECEIPTS):
        if rec.get("msg_id") in msg_ids and rec.get("state") == DELIVERED:
            ai_update(home, _K_RECEIPTS, rec["id"], {"state": SYNCED})
    return {"bundle": bundle, "attestation": attestation}


def import_bundle(
    doc: Dict[str, Any], importer_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Import an attested bundle; trust recomputed against the importer's
    own chat container — the bundle's word about membership is never
    taken on faith."""
    bundle = (doc or {}).get("bundle")
    att = (doc or {}).get("attestation")
    if not isinstance(bundle, dict) or not isinstance(att, dict):
        raise AttestationError("not a bundle document")
    if att.get("alg") != ATTEST_ALG or att.get("v") != ATTEST_V:
        raise AttestationError("unknown attestation algorithm/version")
    expect = hmac.new(_attest_key(home), _canonical(bundle), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, str(att.get("mac") or "")):
        raise AttestationError("bundle attestation failed — not from this owner")
    if bundle.get("track") != TRACK_AI:
        raise AttestationError(
            "bundle track %r is not the AI track" % bundle.get("track")
        )
    if att.get("signer") != importer_id:
        raise AttestationError("bundle was attested by a different owner")
    manifest = bundle.get("chat") or {}
    old_chat_id = str(manifest.get("id") or "")
    members = list(manifest.get("members") or [])
    if importer_id not in members:
        raise DeliveryDeniedError("importer is not a member of the bundled chat")
    # Trust recompute: the importer's own chat container decides.
    local = _locate_local_chat(manifest, importer_id, members, old_chat_id, home)
    new_chat_id = local["id"]
    local_members = set(local.get("members", []))
    existing = {
        (r.get("sender_id"), r.get("body")) for r in ai_read_all(home, _K_MESSAGES)
    }
    imported = 0
    for msg in bundle.get("messages") or []:
        sender = str(msg.get("sender_id") or "")
        if sender not in members or sender not in local_members:
            raise MessengerError(
                "bundled message from %r is not a member of this chat — refused"
                % sender
            )
        if (sender, msg.get("body")) in existing:
            continue  # idempotent re-import
        saved = ai_write(
            home,
            _K_MESSAGES,
            {
                "track": TRACK_AI,
                "chat_id": new_chat_id,
                "sender_id": sender,
                "body": check_sfw(msg.get("body") or "", home),
                "queued_at": msg.get("queued_at") or _utcnow(),
                "delivered_at": _utcnow(),
            },
        )
        ai_write(
            home,
            _K_RECEIPTS,
            {
                "track": TRACK_AI,
                "msg_id": saved["id"],
                "chat_id": new_chat_id,
                "state": SYNCED,
                "at": _utcnow(),
                "verifier": "import",
            },
        )
        existing.add((sender, msg.get("body")))
        imported += 1
    return {"chat_id": new_chat_id, "imported": imported}


# -- Attachments: payloads at rest, per-tier grants, metadata-only lists ----


def seal_attachment(
    chat_id: str,
    sender_id: str,
    name: str,
    mime: str,
    payload: bytes,
    tier: str = DEFAULT_ATTACH_TIER,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Store a media payload with a per-tier grant (open/entry/standard/
    flagship). Plain at rest on this track — said plainly, as always."""
    chat = _member_chat(chat_id, sender_id, home, require_open=True)
    if tier not in ATTACH_TIERS:
        raise MessengerError("tier must be one of %s" % (ATTACH_TIERS,))
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise MessengerError("attachment payload is required")
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise MessengerError("attachment exceeds %d bytes" % MAX_ATTACHMENT_BYTES)
    clean_name = check_sfw(name or "", home) or "attachment"
    saved = ai_write(
        home,
        _K_ATTACHMENTS,
        {
            "track": TRACK_AI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "name": clean_name,
            "mime": (mime or "application/octet-stream").strip(),
            "size": len(payload),
            "tier": tier,
            "payload_hex": bytes(payload).hex(),
            "sealed_at": _utcnow(),
        },
    )
    ai_write(
        home,
        _K_GRANTS,
        {
            "track": TRACK_AI,
            "attachment_id": saved["id"],
            "tier": tier,
            "members": list(chat.get("members", [])),
            "granted_at": _utcnow(),
        },
    )
    return {
        "id": saved["id"],
        "chat_id": chat_id,
        "name": clean_name,
        "mime": saved["mime"],
        "size": saved["size"],
        "tier": tier,
    }


def _get_attachment_record(attachment_id: str, home: Optional[Path]) -> Dict[str, Any]:
    rec = next(
        (r for r in ai_read_all(home, _K_ATTACHMENTS) if r["id"] == attachment_id),
        None,
    )
    if rec is None:
        raise MessengerError("unknown attachment %r" % attachment_id)
    return rec


def _grant_for(attachment_id: str, home: Optional[Path]) -> Dict[str, Any]:
    grant = next(
        (
            g
            for g in ai_read_all(home, _K_GRANTS)
            if g["attachment_id"] == attachment_id
        ),
        None,
    )
    if grant is None:
        raise MessengerError("no grant for attachment %r" % attachment_id)
    return grant


def list_attachments(
    chat_id: str, user_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Attachment listings are metadata-only — payloads never ride along."""
    _member_chat(chat_id, user_id, home, require_open=False)
    return [
        {
            "id": r["id"],
            "chat_id": r["chat_id"],
            "sender_id": r["sender_id"],
            "name": r["name"],
            "mime": r["mime"],
            "size": r["size"],
            "tier": r["tier"],
            "sealed_at": r["sealed_at"],
        }
        for r in ai_read_all(home, _K_ATTACHMENTS)
        if r.get("chat_id") == chat_id
    ]


def get_attachment(
    attachment_id: str, user_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Fetch one attachment: membership AND the per-tier grant must allow it."""
    rec = _get_attachment_record(attachment_id, home)
    _member_chat(rec["chat_id"], user_id, home, require_open=False)
    grant = _grant_for(attachment_id, home)
    if user_id not in grant.get("members", []):
        raise DeliveryDeniedError("the grant for this attachment does not cover you")
    return {
        "id": rec["id"],
        "name": rec["name"],
        "mime": rec["mime"],
        "size": rec["size"],
        "tier": grant.get("tier"),
        "payload": bytes.fromhex(rec["payload_hex"]),
    }


def grant_attachment(
    attachment_id: str,
    owner_id: str,
    member_ids: List[str],
    tier: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Narrow (or widen) who the grant covers. Chat owner only."""
    rec = _get_attachment_record(attachment_id, home)
    chat = _member_chat(rec["chat_id"], owner_id, home, require_open=False)
    if chat.get("owner") != owner_id:
        raise DeliveryDeniedError("only the chat owner changes grants")
    clean = [m.strip() for m in (member_ids or []) if m and m.strip()]
    outsiders = [m for m in clean if m not in set(chat.get("members", []))]
    if outsiders:
        raise MessengerError("grant covers non-members: %s" % outsiders)
    updates: Dict[str, Any] = {"members": clean, "granted_at": _utcnow()}
    if tier is not None:
        if tier not in ATTACH_TIERS:
            raise MessengerError("tier must be one of %s" % (ATTACH_TIERS,))
        updates["tier"] = tier
        ai_update(home, _K_ATTACHMENTS, attachment_id, {"tier": tier})
    return ai_update(home, _K_GRANTS, _grant_for(attachment_id, home)["id"], updates)
