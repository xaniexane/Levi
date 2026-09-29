"""Cybrus broker — QR invite: creator-to-user distribution.

His words: "that's where the qe [QR] code comes in for creator to user
distribution and also just a secure channel for someone to message on"
— "to their closed circle".

A creator issues an invite; the invite's URI payload is what gets
rendered as a QR code (rendering the matrix is the client's job — the
payload is plain text and this module never touches pixels). A user
scans it; redemption verifies the signed ticket and provisions the
user's brokered circle account through the normal broker gates
(human approval + tier quota), then returns a circle admission ticket
for the chat layer.

QR LAWS (machine-checked in tests/test_cybrus_broker_qr.py)
-----------------------------------------------------------
- **Q1 SINGLE-USE.** An invite redeems at most ``max_uses`` times;
  further redemptions fail closed.
- **Q2 EXPIRY.** Expired invites fail closed.
- **Q3 SIGNED.** The ticket is HMAC-SHA256-signed under a keeper-held
  key file (0600, generated once). Forged or tampered tickets fail.
- **Q4 NO-SECRETS-IN-QR.** The QR payload carries no secrets — only a
  signed ticket; credentials are minted server-side on redemption.
- **Q5 CREATOR-BOUND.** The ticket is bound to its creator and circle;
  redemption admits to that circle only.
- **Q6 BROKER-GATED.** Redemption provisions through
  :class:`~levi.cybrus.broker.CredentialBroker` with the human gate and
  the redeemer's tier quota — an invite is not a minting bypass, so a
  limited user cannot mint unlimited through invites.
- **Q7 AUDIT.** Issuance and redemption are audit-logged, metadata only.

Handshake contract with the chat layer (``veil_chat.py`` — NOT rewritten)
--------------------------------------------------------------------------
On redemption the broker returns ``admission``: an HMAC-signed
``{user, circle, creator, invite_id, admitted_at}`` ticket. The chat
layer verifies it with :func:`verify_admission` before adding the user
to the closed-circle conversation. The chat layer owns the channel; the
broker owns the invite and the admission ticket. Revoking a membership
is the chat layer's job.

His-words vs my-fill: his is the QR-as-distribution + closed circle.
My fill is the ticket mechanics (HMAC, single-use, expiry, server-side
use counter) and the rule that redemption runs the standard broker
gates.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

_QR_STORE = "broker_qr_invites"
_QR_KEY_FILE = "broker_qr_invite.key"
_QR_SCHEME = "cybrus://invite/"


class QRError(Exception):
    """QR invite failures (validation, expiry, replay, gate)."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(value: str) -> str:
    return str(value)[:8]


def _paths():
    from levi.cybrus import _paths as p

    return p


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> None:
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(actor), dict(details or {}))


def _clean(value: str, what: str) -> str:
    from levi.cybrus.broker import _clean_name as _cn

    return _cn(value, what)


def _invite_key() -> bytes:
    """Load-or-create the keeper-held invite signing key (0600)."""
    p = _paths()
    key_path = p.cybrus_dir() / _QR_KEY_FILE
    if key_path.exists():
        raw = key_path.read_bytes()
        if len(raw) == 32:
            return raw
        raise QRError("invite signing key file is corrupted")
    raw = secrets.token_bytes(32)
    p.atomic_write_bytes(key_path, raw, 0o600)
    return raw


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii") + b"=" * (-len(text) % 4))


def _sign(payload: Dict[str, Any]) -> str:
    body = _b64e(json.dumps(payload, sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(_invite_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _verify(token: str) -> Dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        payload = json.loads(_b64d(body).decode("utf-8"))
    except Exception as exc:
        raise QRError("invite ticket is malformed") from exc
    expect = _b64e(hmac.new(_invite_key(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expect, sig):
        raise QRError("invite ticket signature invalid (forged or tampered)")
    if not isinstance(payload, dict):
        raise QRError("invite ticket is malformed")
    return payload


def _load_invites() -> Dict[str, Dict]:
    p = _paths()
    data = p.load_json_store(p.store_path(_QR_STORE))
    return data if isinstance(data, dict) else {}


def _save_invites(invites: Dict[str, Dict]) -> None:
    p = _paths()
    path = p.store_path(_QR_STORE)
    with p.store_lock(path):
        p.save_json_store(path, invites)


def _require_creator(creator: str, session) -> str:
    """Creator gate: asserted founder names require a live FounderSession."""
    from levi.cybrus.identity import is_founder_identity

    creator = _clean(creator, "creator")
    if is_founder_identity(creator):
        from levi.cybrus.founder_gateway import FounderSession, FounderSessionError

        if not isinstance(session, FounderSession):
            raise QRError(
                f"identity {creator!r} is a founder identity: creator invites "
                "require a live authenticated FounderSession"
            )
        try:
            session.assert_live()
        except FounderSessionError as exc:
            raise QRError(f"founder session is not live: {exc}") from exc
    return creator


def issue_invite(
    creator: str,
    circle: str,
    session=None,
    max_uses: int = 1,
    ttl_hours: float = 72.0,
) -> Dict[str, Any]:
    """Issue a creator invite; returns the ticket + QR payload.

    ``qr_payload`` is the text the client's QR renderer encodes
    (``cybrus://invite/<ticket>``). No secrets inside (Q4).
    """
    creator = _require_creator(creator, session)
    circle = _clean(circle, "circle")
    if not isinstance(max_uses, int) or max_uses < 1:
        raise QRError("max_uses must be a positive int")
    if not (0 < float(ttl_hours) <= 24 * 90):
        raise QRError("ttl_hours must be within (0, 2160]")
    now = time.time()
    invite_id = uuid.uuid4().hex
    payload = {
        "v": 1,
        "id": invite_id,
        "creator": creator,
        "circle": circle,
        "max_uses": max_uses,
        "exp": now + float(ttl_hours) * 3600.0,
        "nonce": secrets.token_hex(8),
    }
    token = _sign(payload)
    invites = _load_invites()
    invites[invite_id] = {
        "id": invite_id,
        "creator": creator,
        "circle": circle,
        "max_uses": max_uses,
        "uses": 0,
        "exp": payload["exp"],
        "created_at": _utcnow_iso(),
    }
    _save_invites(invites)
    _audit(
        "broker.qr.issued",
        creator,
        {
            "invite_id": _short(invite_id),
            "circle": circle,
            "max_uses": max_uses,
            "ttl_hours": float(ttl_hours),
        },
    )
    return {
        "invite_id": invite_id,
        "creator": creator,
        "circle": circle,
        "qr_payload": _QR_SCHEME + token,
        "expires_at": _utcnow_iso(),
    }


def qr_payload_for(token: str) -> str:
    """Wrap a raw ticket in the QR URI scheme (client renders the matrix)."""
    return _QR_SCHEME + token.strip()


def redeem_invite(
    qr_payload_or_token: str, user_identity: str, vault_passphrase: str
) -> Tuple[Dict[str, Any], str]:
    """Redeem a scanned invite: verify, provision, admit.

    Verifies the ticket (Q1/Q2/Q3/Q5), then provisions the user's
    brokered circle account through :class:`CredentialBroker` — the
    human gate and the redeemer's tier quota apply (Q6). Returns
    ``(account_record, admission_ticket)``; the admission ticket is the
    chat layer's handshake (verified with :func:`verify_admission`).
    """
    from levi.cybrus.broker import CredentialBroker

    raw = str(qr_payload_or_token or "").strip()
    if raw.startswith(_QR_SCHEME):
        raw = raw[len(_QR_SCHEME):]
    payload = _verify(raw)
    now = time.time()
    if float(payload.get("exp", 0)) < now:
        raise QRError("invite has expired")
    invite_id = str(payload.get("id", ""))
    invites = _load_invites()
    record_inv = invites.get(invite_id)
    if record_inv is None:
        raise QRError("invite is unknown (revoked or never issued)")
    if int(record_inv.get("uses", 0)) >= int(record_inv.get("max_uses", 1)):
        raise QRError("invite has already been fully redeemed")
    if (
        record_inv.get("creator") != payload.get("creator")
        or record_inv.get("circle") != payload.get("circle")
    ):
        raise QRError("invite ticket does not match its issued record")

    user = _clean(user_identity, "user_identity")
    circle = str(record_inv["circle"])
    broker = CredentialBroker(vault_passphrase)
    # The broker's human gate + tier quota fire here (Q6): the invite is
    # distribution, not a minting bypass.
    account, _password = broker.provision(
        platform=f"circle.{circle}",
        signup_url=f"https://cybrus.circle/{circle}",
        identity=user,
        username=user,
    )
    p = _paths()
    path = p.store_path(_QR_STORE)
    with p.store_lock(path):
        invites = _load_invites()
        rec = invites.get(invite_id)
        if rec is None or int(rec.get("uses", 0)) >= int(rec.get("max_uses", 1)):
            raise QRError("invite was redeemed concurrently")
        rec["uses"] = int(rec.get("uses", 0)) + 1
        p.save_json_store(path, invites)
    admission = _sign(
        {
            "v": 1,
            "kind": "admission",
            "user": user,
            "circle": circle,
            "creator": record_inv["creator"],
            "invite_id": invite_id,
            "admitted_at": _utcnow_iso(),
        }
    )
    _audit(
        "broker.qr.redeemed",
        user,
        {
            "invite_id": _short(invite_id),
            "circle": circle,
            "creator": record_inv["creator"],
            "account_id": _short(account["id"]),
        },
    )
    return account, admission


def verify_admission(admission_ticket: str) -> Dict[str, Any]:
    """Verify a circle admission ticket for the chat layer.

    Returns the admission claims ``{user, circle, creator, invite_id,
    admitted_at}``; raises :class:`QRError` on forgery/tamper. The chat
    layer calls this before adding the user to the closed-circle
    conversation.
    """
    payload = _verify(str(admission_ticket or "").strip())
    if payload.get("kind") != "admission":
        raise QRError("not an admission ticket")
    for field in ("user", "circle", "creator", "invite_id", "admitted_at"):
        if field not in payload:
            raise QRError(f"admission ticket missing {field!r}")
    return {k: payload[k] for k in ("user", "circle", "creator", "invite_id", "admitted_at")}
