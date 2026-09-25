"""Veil Messenger — SI track (Plaiground).

Hardened messaging on the SI side: adult-gated, per-message sealed
envelopes, membership enforced on every send and read, closed chats
readable but silent, offline-first outbox with local delivery receipts,
owner-initiated attested bundle export/import, and attachment sealing
with per-tier grants.

Track law: this module touches ONLY the SI store (``si_*``), the
Plaiground gate, the bounds check, and the Veil-lineage sealing. It
never touches the AI track. Every public entry calls ``require_adult``
first.

The sealing construction is Encrypt-then-MAC (VEIL1: HMAC-SHA256 keyed
HKDF + SHA-256-CTR XOR keystream, keeper-held key) — see
:mod:`levi.creator.veil.threat_model`. It is NOT AES-GCM, and this
module never claims otherwise.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.seal import SealError, keeper_key, open_bytes, seal_bytes
from levi.creator.si import chats as si_chats
from levi.creator.store import si_read_all, si_update, si_write
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
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

# -- Store kinds (new, SI-only) --------------------------------------------
_K_MESSAGES = "veil_si_messages"
_K_OUTBOX = "veil_si_outbox"
_K_RECEIPTS = "veil_si_receipts"
_K_ATTACHMENTS = "veil_si_attachments"
_K_GRANTS = "veil_si_grants"
_K_IMPORTS = "veil_si_imports"

_ATTEST_LABEL = b"veil1-attest"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg_ctx(chat_id: str) -> str:
    """Sealing context bound to one chat — envelopes can't be transplanted."""
    return "veil1/si/msg/%s" % chat_id


def _att_ctx(chat_id: str) -> str:
    return "veil1/si/attach/%s" % chat_id


def _attest_key(home: Optional[Path]) -> bytes:
    return hmac.new(keeper_key(home), _ATTEST_LABEL, hashlib.sha256).digest()


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _member_chat(
    chat_id: str, user_id: str, home: Optional[Path], require_open: bool = False
) -> Dict[str, Any]:
    """Return the chat container iff user_id is a member. Paired enforcement.

    Called on every send AND every read. Closed chats are readable
    (require_open=False) but silent (require_open=True for sends).
    """
    require_adult(home)
    for chat in si_chats.list_chats(user_id, home):
        if chat["id"] == chat_id:
            if require_open and not chat.get("open", True):
                raise MessengerError("this chat is closed — readable, silent")
            return chat
    raise DeliveryDeniedError("not a member of this chat")


# -- Ternary delivery: queue -> flush -> export -----------------------------


def queue_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Seal a message into the outbox (state QUEUED). Nothing is delivered yet.

    Sync is explicit and owner-initiated: a queued message stays queued
    until :func:`flush_outbox` runs. No ambient delivery, ever.
    """
    _member_chat(chat_id, sender_id, home, require_open=True)
    clean = (body or "").strip()
    if not clean:
        raise MessengerError("message body is required")
    check_bounds(clean, home)
    envelope = seal_bytes(
        _canonical(
            {
                "chat_id": chat_id,
                "sender_id": sender_id,
                "body": clean,
                "queued_at": _utcnow(),
            }
        ),
        keeper_key(home),
        _msg_ctx(chat_id),
    )
    entry = si_write(
        home,
        _K_OUTBOX,
        {
            "track": TRACK_SI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "envelope": envelope,
            "state": QUEUED,
            "queued_at": _utcnow(),
        },
    )
    return {"outbox_id": entry["id"], "chat_id": chat_id, "state": QUEUED}


def flush_outbox(
    home: Optional[Path] = None, chat_id: Optional[str] = None
) -> List[str]:
    """Owner-initiated local flush: QUEUED -> DELIVERED with receipts.

    Each flushed entry is re-checked (membership, chat still open,
    envelope integrity) before anything is written — proposer/verifier,
    the paired-mind shape. A failed entry stays QUEUED (fail-closed).
    Returns the delivered message ids.
    """
    require_adult(home)
    delivered: List[str] = []
    key = keeper_key(home)
    for entry in si_read_all(home, _K_OUTBOX):
        if entry.get("state") != QUEUED:
            continue
        if chat_id is not None and entry.get("chat_id") != chat_id:
            continue
        # Verifier half: re-check everything before persisting.
        try:
            _member_chat(entry["chat_id"], entry["sender_id"], home, require_open=True)
            open_bytes(entry["envelope"], key, _msg_ctx(entry["chat_id"]))
        except (DeliveryDeniedError, MessengerError, SealError):
            continue  # stays QUEUED — fail closed, no half-writes
        msg = si_write(
            home,
            _K_MESSAGES,
            {
                "track": TRACK_SI,
                "chat_id": entry["chat_id"],
                "sender_id": entry["sender_id"],
                "envelope": entry["envelope"],
                "queued_at": entry["queued_at"],
                "delivered_at": _utcnow(),
            },
        )
        si_write(
            home,
            _K_RECEIPTS,
            {
                "track": TRACK_SI,
                "msg_id": msg["id"],
                "chat_id": entry["chat_id"],
                "state": DELIVERED,
                "at": _utcnow(),
                "verifier": "local-flush",
            },
        )
        si_update(
            home, _K_OUTBOX, entry["id"], {"state": DELIVERED, "msg_id": msg["id"]}
        )
        delivered.append(msg["id"])
    return delivered


def send_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Queue + flush in one call: sub-interaction local delivery, no server.

    Returns the delivered message id and its receipt.
    """
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
    """Outbox listing — metadata only, sealed payloads stay out of views."""
    require_adult(home)
    rows = []
    for entry in si_read_all(home, _K_OUTBOX):
        if chat_id is not None and entry.get("chat_id") != chat_id:
            continue
        if user_id is not None and entry.get("sender_id") != user_id:
            continue
        rows.append({k: v for k, v in entry.items() if k != "envelope"})
    return rows


def delivery_receipts(
    home: Optional[Path] = None,
    chat_id: Optional[str] = None,
    msg_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Local delivery receipts: the proof delivery happened on-device."""
    require_adult(home)
    rows = []
    for rec in si_read_all(home, _K_RECEIPTS):
        if chat_id is not None and rec.get("chat_id") != chat_id:
            continue
        if msg_id is not None and rec.get("msg_id") != msg_id:
            continue
        rows.append(dict(rec))
    return rows


# -- Reading: membership enforced, tamper-evident ---------------------------


def read_thread(
    chat_id: str, user_id: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Read a chat's messages. Members only; closed chats stay readable.

    Every inner envelope is opened against the chat-bound context: a
    flipped byte fails MAC verification, and an envelope moved from
    another chat fails the context check. Either way a SealError rises —
    tamper-evidence, not silent corruption.
    """
    _member_chat(chat_id, user_id, home, require_open=False)
    key = keeper_key(home)
    ctx = _msg_ctx(chat_id)
    out = []
    for rec in si_read_all(home, _K_MESSAGES):
        if rec.get("chat_id") != chat_id:
            continue
        payload = json.loads(open_bytes(rec["envelope"], key, ctx).decode("utf-8"))
        out.append(
            {
                "id": rec["id"],
                "chat_id": chat_id,
                "sender_id": payload["sender_id"],
                "body": payload["body"],
                "queued_at": payload["queued_at"],
                "delivered_at": rec.get("delivered_at"),
            }
        )
    return out


# -- Portability: attested bundles, owner-initiated -------------------------


def _import_map(
    manifest_chat_id: str, signer: str, home: Optional[Path]
) -> Optional[str]:
    """Where did this owner's earlier import of this bundled chat land?"""
    for r in si_read_all(home, _K_IMPORTS):
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
    """Find or create the local chat container for an imported bundle.

    An earlier import of the same bundle maps back to the same local
    chat (import provenance), so re-importing an updated bundle lands
    in the right place instead of spawning duplicate chats.
    """
    containers = si_chats.list_chats(importer_id, home)
    local = next((c for c in containers if c["id"] == old_chat_id), None)
    if local is None:
        mapped = _import_map(old_chat_id, importer_id, home)
        if mapped is not None:
            local = next((c for c in containers if c["id"] == mapped), None)
    if local is not None:
        return local
    # Create the container through the public chat API (no edits to it).
    owner = str(manifest.get("owner") or importer_id)
    if manifest.get("kind") == "dm":
        others = [m for m in members if m != owner]
        if not others:
            raise MessengerError("bundled dm has no other party")
        local = si_chats.create_chat(owner, others[0], home)
    else:
        local = si_chats.create_group(owner, manifest.get("name") or "", members, home)
    si_write(
        home,
        _K_IMPORTS,
        {
            "track": TRACK_SI,
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
    """Export a chat's history as an attested bundle. Owner-initiated.

    The bundle carries plaintext message bodies plus an HMAC attestation
    proving it came from the owner's machine — origin, NOT
    confidentiality (see threat_model). Included messages move
    DELIVERED -> SYNCED.
    """
    chat = _member_chat(chat_id, user_id, home, require_open=False)
    messages = read_thread(chat_id, user_id, home)
    bundle = {
        "v": 1,
        "track": TRACK_SI,
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
    # Mark included messages SYNCED.
    msg_ids = {m["id"] for m in messages}
    for entry in si_read_all(home, _K_OUTBOX):
        if entry.get("state") == DELIVERED and entry.get("msg_id") in msg_ids:
            si_update(home, _K_OUTBOX, entry["id"], {"state": SYNCED})
    for rec in si_read_all(home, _K_RECEIPTS):
        if rec.get("msg_id") in msg_ids and rec.get("state") == DELIVERED:
            si_update(home, _K_RECEIPTS, rec["id"], {"state": SYNCED})
    return {"bundle": bundle, "attestation": attestation}


def import_bundle(
    doc: Dict[str, Any], importer_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Import an attested bundle. Verifies attestation, then recomputes
    trust against the importer's own chat container — the bundle's word
    about membership is never taken on faith.
    """
    require_adult(home)
    bundle = (doc or {}).get("bundle")
    att = (doc or {}).get("attestation")
    if not isinstance(bundle, dict) or not isinstance(att, dict):
        raise AttestationError("not a bundle document")
    if att.get("alg") != ATTEST_ALG or att.get("v") != ATTEST_V:
        raise AttestationError("unknown attestation algorithm/version")
    expect = hmac.new(_attest_key(home), _canonical(bundle), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, str(att.get("mac") or "")):
        raise AttestationError("bundle attestation failed — not from this owner")
    if bundle.get("track") != TRACK_SI:
        raise AttestationError(
            "bundle track %r is not the SI track" % bundle.get("track")
        )
    if att.get("signer") != importer_id:
        raise AttestationError(
            "bundle was attested by a different owner — single-owner "
            "portability only in this build (see threat_model)"
        )
    manifest = bundle.get("chat") or {}
    old_chat_id = str(manifest.get("id") or "")
    members = list(manifest.get("members") or [])
    if importer_id not in members:
        raise DeliveryDeniedError("importer is not a member of the bundled chat")
    # Trust recompute: the importer's own chat container decides.
    local = _locate_local_chat(manifest, importer_id, members, old_chat_id, home)
    new_chat_id = local["id"]
    local_members = set(local.get("members", []))
    key = keeper_key(home)
    imported = 0
    for msg in bundle.get("messages") or []:
        sender = str(msg.get("sender_id") or "")
        if sender not in members or sender not in local_members:
            raise MessengerError(
                "bundled message from %r is not a member of this chat — refused"
                % sender
            )
        # Integrity of the bundle itself is carried by the attestation
        # (verified above); bodies arrive as plaintext in the bundle by
        # design. Here each message is re-sealed under the local (possibly
        # remapped) chat context, which binds it to this chat.
        record = next(
            (
                r
                for r in si_read_all(home, _K_MESSAGES)
                if r.get("chat_id") == new_chat_id
                and r.get("sender_id") == sender
                and json.loads(
                    open_bytes(r["envelope"], key, _msg_ctx(new_chat_id)).decode(
                        "utf-8"
                    )
                ).get("body")
                == msg.get("body")
            ),
            None,
        )
        if record is not None:
            continue  # already here — idempotent re-import
        payload = _canonical(
            {
                "chat_id": new_chat_id,
                "sender_id": sender,
                "body": msg.get("body"),
                "queued_at": msg.get("queued_at") or _utcnow(),
            }
        )
        envelope = seal_bytes(payload, key, _msg_ctx(new_chat_id))
        saved = si_write(
            home,
            _K_MESSAGES,
            {
                "track": TRACK_SI,
                "chat_id": new_chat_id,
                "sender_id": sender,
                "envelope": envelope,
                "queued_at": msg.get("queued_at") or _utcnow(),
                "delivered_at": _utcnow(),
            },
        )
        si_write(
            home,
            _K_RECEIPTS,
            {
                "track": TRACK_SI,
                "msg_id": saved["id"],
                "chat_id": new_chat_id,
                "state": SYNCED,
                "at": _utcnow(),
                "verifier": "import",
            },
        )
        imported += 1
    return {"chat_id": new_chat_id, "imported": imported}


# -- Attachments: sealed payloads, per-tier grants, metadata-only lists ----


def seal_attachment(
    chat_id: str,
    sender_id: str,
    name: str,
    mime: str,
    payload: bytes,
    tier: str = DEFAULT_ATTACH_TIER,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Seal a media payload at rest with a per-tier grant.

    Giants do locked/unlocked; we do the ladder — open / entry /
    standard / flagship. The initial grant covers the chat's current
    members; the owner narrows it with :func:`grant_attachment`.
    """
    chat = _member_chat(chat_id, sender_id, home, require_open=True)
    if tier not in ATTACH_TIERS:
        raise MessengerError("tier must be one of %s" % (ATTACH_TIERS,))
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise MessengerError("attachment payload is required")
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise MessengerError("attachment exceeds %d bytes" % MAX_ATTACHMENT_BYTES)
    clean_name = (name or "").strip() or "attachment"
    check_bounds(clean_name, home)
    envelope = seal_bytes(bytes(payload), keeper_key(home), _att_ctx(chat_id))
    saved = si_write(
        home,
        _K_ATTACHMENTS,
        {
            "track": TRACK_SI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "name": clean_name,
            "mime": (mime or "application/octet-stream").strip(),
            "size": len(payload),
            "tier": tier,
            "envelope": envelope,
            "sealed_at": _utcnow(),
        },
    )
    si_write(
        home,
        _K_GRANTS,
        {
            "track": TRACK_SI,
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
        (r for r in si_read_all(home, _K_ATTACHMENTS) if r["id"] == attachment_id),
        None,
    )
    if rec is None:
        raise MessengerError("unknown attachment %r" % attachment_id)
    return rec


def _grant_for(attachment_id: str, home: Optional[Path]) -> Dict[str, Any]:
    grant = next(
        (
            g
            for g in si_read_all(home, _K_GRANTS)
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
        for r in si_read_all(home, _K_ATTACHMENTS)
        if r.get("chat_id") == chat_id
    ]


def get_attachment(
    attachment_id: str, user_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Open one attachment: membership AND the per-tier grant must allow it."""
    require_adult(home)
    rec = _get_attachment_record(attachment_id, home)
    _member_chat(rec["chat_id"], user_id, home, require_open=False)
    grant = _grant_for(attachment_id, home)
    if user_id not in grant.get("members", []):
        raise DeliveryDeniedError("the grant for this attachment does not cover you")
    payload = open_bytes(rec["envelope"], keeper_key(home), _att_ctx(rec["chat_id"]))
    return {
        "id": rec["id"],
        "name": rec["name"],
        "mime": rec["mime"],
        "size": rec["size"],
        "tier": grant.get("tier"),
        "payload": payload,
    }


def grant_attachment(
    attachment_id: str,
    owner_id: str,
    member_ids: List[str],
    tier: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Narrow (or widen) who the grant covers. Chat owner only."""
    require_adult(home)
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
        si_update(home, _K_ATTACHMENTS, attachment_id, {"tier": tier})
    return si_update(home, _K_GRANTS, _grant_for(attachment_id, home)["id"], updates)
