"""Veil Companions — Plaiground AI companions as native Veil chat contacts.

What this is
------------
A :class:`VeilCompanions` that extends :class:`levi.cybrus.veil_chat.VeilChat`
with local AI-companion peers. A user opens Veil, sees their Plaiground
companions alongside human contacts, and chats with them through the same
sealed interface. The companion's messages go through Veil's envelope /
ratchet machinery exactly like any other conversation — the transcript is
encrypted at rest, tamper-evident, forward-secret per the chain ratchet.

How a companion peer works
--------------------------
A companion is a *virtual* peer: both sides of the conversation live on
the keeper's own device. Instead of an X25519 handshake with a remote
party, :meth:`open_companion_conversation` performs a *local
self-handshake* — fresh random chain roots sealed under a fresh epoch
key, exactly like :meth:`VeilChat._store_epoch` does for human
conversations. The keeper's outgoing messages seal via
:meth:`VeilChat.send_message` (send chain); the companion's replies are
sealed as incoming envelopes by advancing the *recv* chain
(:meth:`_companion_incoming`). Same envelope format, same AAD binding,
same ratchet destruction, same layered at-rest wrapping.

The companion's virtual identity (a stable X25519 public key + grouped-hex
fingerprint) derives deterministically from the keeper's master key via
HKDF — it never leaves the device and is never a real remote identity.
Peer records carry ``kind="companion"`` so the UI can badge them; human
peers keep ``kind="human"`` (default, back-compatible).

The brain runs locally
----------------------
Replies come from :class:`levi.plaiground.chat.ChatSession` — in-process,
deterministic, no network, no external model. Exchanges are journaled via
:mod:`levi.plaiground.depth` for companion continuity (rapport, recall).

Laws (machine-readable in ``LAWS``, checked by :func:`verify_laws`)
------------------------------------------------------------------
- VC1 GATE-FIRST — every public entry calls
  :func:`levi.plaiground.gate.require_adult` before touching companion
  state. Veil never bypasses the Plaiground gate.
- VC2 BOUNDS — user-supplied text passes
  :func:`levi.plaiground.bounds.check_bounds` before the brain sees it.
- VC3 SEALED-TRANSCRIPT — companion messages use the same envelope /
  ratchet machinery as human messages. No plaintext side channel.
- VC4 LOCAL-BRAIN — the companion brain runs in-process. No network.
- VC5 NO-BYPASS — companion definitions are created/read only through
  plaiground's own gate-checked functions.
- VC6 QR-SIGNED — companion invites are HMAC-signed, single-use,
  expiring; redemption re-validates the definition through plaiground.
- VC7 AUDIT-METADATA-ONLY — the Cybrus audit log carries conversation
  ids and counts, never message plaintext.
- VC8 NO-CANCELLATION — inherited from VeilChat: companion peers and
  conversations follow the same no-drop rules as human ones.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.cybrus._paths import atomic_write_bytes, store_lock
from levi.cybrus.audit import AuditEngine
from levi.cybrus.veil import (
    VeilError,
    _b64d,
    _b64e,
    _hkdf,
    _seal_backend,
    _utcnow,
    fingerprint,
)
from levi.cybrus.veil_chat import (
    _PROTOCOL_VERSION,
    _zero,
    VeilChat,
    VeilChatError,
    x25519_public,
)
from levi.plaiground.bounds import check_bounds
from levi.plaiground.chat import ChatSession
from levi.plaiground.companions import (
    create_companion,
    get_companion,
    list_companions,
)
from levi.plaiground.depth import remember as depth_remember
from levi.plaiground.gate import gate_dir, require_adult

# ---------------------------------------------------------------------------
# Laws
# ---------------------------------------------------------------------------

LAWS = (
    ("VC1", "GATE-FIRST",
     "Every public entry calls require_adult() before touching companion state."),
    ("VC2", "BOUNDS",
     "User-supplied text passes check_bounds() before the brain sees it."),
    ("VC3", "SEALED-TRANSCRIPT",
     "Companion messages use the same envelope/ratchet machinery as human messages."),
    ("VC4", "LOCAL-BRAIN",
     "The companion brain runs in-process; no network, no external model."),
    ("VC5", "NO-BYPASS",
     "Companion definitions go through plaiground's own gate-checked functions only."),
    ("VC6", "QR-SIGNED",
     "Companion invites are HMAC-signed, single-use, expiring; redemption re-validates."),
    ("VC7", "AUDIT-METADATA-ONLY",
     "Audit log carries conversation ids and counts, never message plaintext."),
    ("VC8", "NO-CANCELLATION",
     "Companion peers/conversations follow VeilChat's no-drop rules."),
)


def verify_laws() -> List[tuple]:
    """Check the integration laws that are statically checkable."""
    out = []
    src = Path(__file__).read_text(encoding="utf-8")
    # VC1: every public method of VeilCompanions calls require_adult first.
    import ast
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "VeilCompanions")
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and not node.name.startswith("_"):
            found = False
            for c in ast.walk(node):
                if not isinstance(c, ast.Call):
                    continue
                f = c.func
                if isinstance(f, ast.Name) and f.id == "require_adult":
                    found = True
                    break
                if isinstance(f, ast.Attribute) and f.attr == "require_adult":
                    found = True
                    break
            out.append(("VC1", found,
                        "public method %s gate-checked" % node.name))
    # VC4: no network imports in this module (scan import statements only,
    # so the banned-name documentation literal doesn't false-positive).
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    banned = {"socket", "urllib", "http", "requests"}
    out.append(("VC4", not (imported & banned),
                "no network imports (found: %s)"
                % sorted(imported & banned) if imported & banned
                else "no network imports"))
    return out


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BINDINGS_FILE = "companion_bindings.json"
_INVITES_FILE = "companion_invites.json"
_QR_SCHEME = "cybrus://companion/"
_PEER_PREFIX = "companion-"

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.'-]{0,47}$")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "companion"


def _short(value: str) -> str:
    return value[:12]


class VeilCompanionError(VeilChatError):
    """Companion-integration failures. Fails closed, like everything here."""


class VeilCompanions(VeilChat):
    """VeilChat with local AI-companion peers.

    Construct exactly like :class:`VeilChat`::

        vc = VeilCompanions(passphrase)
        conv_id = vc.open_companion_conversation("Nova")
        result = vc.send_to_companion(conv_id, "hey, how's your night going?")
        print(result["reply"])
    """

    def __init__(self, passphrase: str, home: Optional[Path] = None) -> None:
        super().__init__(passphrase, home=home)
        self._sessions: Dict[str, ChatSession] = {}
        self._audit = AuditEngine()

    # -- audit ---------------------------------------------------------------
    def _audit_event(self, event: str, details: Optional[Dict] = None) -> None:
        try:
            self._audit.append(event, "keeper", details or {})
        except Exception:
            pass  # audit failure never breaks the chat path

    # -- virtual companion identity ------------------------------------------
    def _companion_peer_id(self, companion_name: str) -> str:
        return _PEER_PREFIX + _slugify(companion_name)

    def _companion_keypair(self, peer_id: str) -> tuple:
        """Deterministic virtual X25519 identity for a companion peer.

        Derived from the keeper's master key via HKDF — stable per
        keeper+companion, never leaves the device, never a real remote
        identity. Returns (priv_bytes, pub_bytes, fingerprint)."""
        master = self._require_unlocked()
        raw = _hkdf(master, b"veil-companion-id-salt-v1",
                    b"veil-companion-id-v1|" + peer_id.encode("utf-8"), 32)
        priv = bytearray(raw)
        priv[0] &= 248
        priv[31] &= 127
        priv[31] |= 64
        priv_b = bytes(priv)
        pub_b = x25519_public(priv_b)
        return priv_b, pub_b, fingerprint(pub_b)

    def register_companion_peer(self, companion_name: str) -> Dict:
        """Register (or fetch) the virtual peer for a companion.

        Gate-checked. The peer record carries kind="companion" and is
        marked verified-by-local (no remote ceremony applies — the keeper
        is both sides). Originals-first holds: re-registering the same
        companion is idempotent; a *different* definition under the same
        name does not silently re-key the peer.
        """
        require_adult()
        if not _NAME_RE.match(companion_name or ""):
            raise VeilCompanionError("bad companion name %r" % companion_name)
        # VC5: the definition must exist and come through plaiground.
        get_companion(companion_name)
        peer_id = self._companion_peer_id(companion_name)
        _priv, pub, fp = self._companion_keypair(peer_id)
        record = self.add_peer(peer_id, pub, name=companion_name)
        peers = self._read_peers()
        rec = peers[peer_id]
        rec["kind"] = "companion"
        rec["companion_name"] = companion_name
        rec["verified"] = True
        rec["verified_by"] = "local-companion"
        self._write_peers(peers)
        return rec

    # -- bindings sidecar ------------------------------------------------------
    def _bindings_path(self) -> Path:
        return self._home / _BINDINGS_FILE

    def _read_bindings(self) -> Dict:
        p = self._bindings_path()
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_bindings(self, bindings: Dict) -> None:
        p = self._bindings_path()
        with store_lock(p):
            atomic_write_bytes(
                p, json.dumps(bindings, indent=2, sort_keys=True).encode("utf-8"))
        os.chmod(p, 0o600)

    # -- conversation bootstrap (local self-handshake) -------------------------
    def open_companion_conversation(
        self, companion_name: str, tone: str = "warm"
    ) -> str:
        """Open a sealed Veil conversation with a companion.

        Gate-checked (VC1). Performs the local self-handshake: fresh
        random chain roots + fresh epoch key, stored via the same
        :meth:`VeilChat._store_epoch` path human conversations use.
        Returns the conv_id.
        """
        require_adult()
        peer = self.register_companion_peer(companion_name)
        peer_id = peer["peer_id"]
        conv_id = uuid.uuid4().hex
        send0 = secrets.token_bytes(32)
        recv0 = secrets.token_bytes(32)
        epoch_key = secrets.token_bytes(32)
        self._store_epoch(conv_id, peer_id, send0, recv0, epoch_key,
                          rotate=False)
        bindings = self._read_bindings()
        bindings[conv_id] = {
            "companion_name": companion_name,
            "tone": tone,
            "opened_at": _utcnow(),
        }
        self._write_bindings(bindings)
        self._audit_event("veil.companion.opened", {
            "conv_id": _short(conv_id),
            "companion": companion_name,
        })
        return conv_id

    def _binding_for(self, conv_id: str) -> Dict:
        bindings = self._read_bindings()
        b = bindings.get(conv_id)
        if not b:
            raise VeilCompanionError("conversation is not a companion chat")
        return b

    def _session_for(self, conv_id: str) -> ChatSession:
        b = self._binding_for(conv_id)
        sess = self._sessions.get(conv_id)
        if sess is None:
            sess = ChatSession(b["companion_name"], tone=b.get("tone", "warm"))
            self._sessions[conv_id] = sess
        return sess

    # -- messaging ---------------------------------------------------------------
    def _companion_incoming(self, conv_id: str, plaintext: bytes,
                            sender_fp: str) -> Dict:
        """Seal a companion reply as an *incoming* envelope.

        Mirrors :meth:`VeilChat.send_message` but advances the recv chain:
        same envelope format, same AAD binding, same layered at-rest
        wrapping, same ratchet destruction. The sender_fp is the
        companion's virtual fingerprint, so the transcript distinguishes
        sides exactly like a human conversation.
        """
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise VeilCompanionError("plaintext must be non-empty bytes")
        self._require_unlocked()
        conv = self._read_conv(conv_id)
        epoch = int(conv["epoch"])
        state = self._load_chain_state(conv_id, epoch)
        send_chain = bytearray(_b64d(state["send_chain"]))
        recv_chain = bytearray(_b64d(state["recv_chain"]))
        try:
            msg_key, next_chain = self._chain_advance(bytes(recv_chain))
            seq = int(state["recv_seq"]) + 1
            header = {
                "protocol_version": _PROTOCOL_VERSION,
                "conv_id": conv_id,
                "epoch": epoch,
                "sender_fp": sender_fp,
                "seq": seq,
                "sent_at": _utcnow(),
            }
            blob = _seal_backend(msg_key, bytes(plaintext),
                                 self._envelope_aad(header))
            self._wrap_msgkey(conv_id, epoch, sender_fp, seq, msg_key)
            envelope = dict(header)
            envelope["blob"] = _b64e(blob)
            _zero(recv_chain)
            recv_chain = bytearray(next_chain)
            self._save_chain_state(
                conv_id, epoch, bytes(send_chain), bytes(recv_chain),
                int(state["send_seq"]), seq,
            )
        finally:
            _zero(send_chain)
            _zero(recv_chain)
        self._store_envelope(conv_id, envelope)
        return envelope

    def send_to_companion(self, conv_id: str, text: str) -> Dict:
        """One full turn with a companion: seal the user's message, run
        the local brain, seal the reply. Gate-checked (VC1), bounds-checked
        (VC2). Returns the reply text plus both sealed envelopes.

        Nothing leaves the device: the brain runs in-process (VC4), and
        both directions are sealed through Veil's machinery (VC3).
        """
        require_adult()
        binding = self._binding_for(conv_id)
        companion_name = binding["companion_name"]
        text = check_bounds(text)
        if not text or not text.strip():
            raise VeilCompanionError("message must not be empty")
        if len(text) > 4000:
            raise VeilCompanionError("message too long")
        # Outgoing: the keeper's side, sealed through the send chain.
        out_env = self.send_message(conv_id, text.encode("utf-8"))
        # The brain, locally.
        session = self._session_for(conv_id)
        reply = session.say(text)
        # Incoming: the companion's side, sealed through the recv chain.
        _priv, _pub, comp_fp = self._companion_keypair(
            self._companion_peer_id(companion_name))
        in_env = self._companion_incoming(conv_id, reply.encode("utf-8"),
                                          comp_fp)
        # Continuity: journal the exchange (bounds-checked inside depth).
        try:
            depth_remember(companion_name,
                           "Veil turn — user: %s | %s: %s"
                           % (text[:500], companion_name, reply[:500]))
        except Exception:
            pass  # journaling never breaks the chat path
        self._audit_event("veil.companion.turn", {
            "conv_id": _short(conv_id),
            "companion": companion_name,
            "out_seq": out_env["seq"],
            "in_seq": in_env["seq"],
        })
        return {
            "reply": reply,
            "conv_id": conv_id,
            "companion": companion_name,
            "out_envelope_seq": out_env["seq"],
            "in_envelope_seq": in_env["seq"],
        }

    # -- unified contact / conversation list --------------------------------------
    def list_chats(self) -> List[Dict]:
        """Every conversation with its peer kind: ``human`` or
        ``companion``. Companions render with a badge in the UI; the
        crypto underneath is identical."""
        require_adult()
        peers = self._read_peers()
        bindings = self._read_bindings()
        out = []
        for conv in self.list_conversations():
            peer = peers.get(conv["peer_id"], {})
            kind = peer.get("kind", "human")
            item = {
                "conv_id": conv["conv_id"],
                "peer_id": conv["peer_id"],
                "name": peer.get("name") or peer.get("companion_name", ""),
                "kind": kind,
                "epoch": conv["epoch"],
                "send_seq": conv["send_seq"],
                "recv_seq": conv["recv_seq"],
            }
            if kind == "companion":
                b = bindings.get(conv["conv_id"], {})
                item["companion_name"] = b.get("companion_name")
                item["tone"] = b.get("tone", "warm")
            out.append(item)
        return out

    def companion_history(self, conv_id: str) -> List[Dict]:
        """Plaintext turn history for a companion conversation (the live
        session's view). Gate-checked. For the sealed at-rest journal see
        :meth:`fetch_envelopes`."""
        require_adult()
        self._binding_for(conv_id)  # raises if not a companion chat
        return self._session_for(conv_id).history()

    # -- QR distribution ------------------------------------------------------------
    def _invite_key(self) -> bytes:
        master = self._require_unlocked()
        return _hkdf(master, b"veil-companion-invite-salt-v1",
                     b"veil-companion-invite-v1", 32)

    def _sign_ticket(self, payload: Dict) -> str:
        body = _b64e(json.dumps(payload, sort_keys=True).encode("utf-8"))
        sig = _b64e(hmac.new(self._invite_key(), body.encode("ascii"),
                             hashlib.sha256).digest())
        return "%s.%s" % (body, sig)

    def _verify_ticket(self, token: str) -> Dict:
        try:
            body, sig = token.split(".", 1)
            payload = json.loads(_b64d(body).decode("utf-8"))
        except Exception as exc:
            raise VeilCompanionError("companion ticket malformed") from exc
        expect = _b64e(hmac.new(self._invite_key(), body.encode("ascii"),
                                hashlib.sha256).digest())
        if not hmac.compare_digest(expect, sig):
            raise VeilCompanionError("companion ticket signature invalid")
        if not isinstance(payload, dict):
            raise VeilCompanionError("companion ticket malformed")
        return payload

    def _read_invites(self) -> Dict:
        p = self._home / _INVITES_FILE
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_invites(self, invites: Dict) -> None:
        p = self._home / _INVITES_FILE
        with store_lock(p):
            atomic_write_bytes(
                p, json.dumps(invites, indent=2, sort_keys=True).encode("utf-8"))
        os.chmod(p, 0o600)

    def companion_invite_qr(self, companion_name: str, max_uses: int = 1,
                            ttl_hours: float = 72.0) -> Dict:
        """Issue a signed companion-share ticket. The returned
        ``qr_payload`` (``cybrus://companion/<ticket>``) is what the
        client's QR renderer encodes. Gate-checked (VC1, VC6).

        The ticket carries the persona definition (name, traits,
        boundaries) plus a definition hash — no secrets, single-use by
        default, expiring.
        """
        require_adult()
        definition = get_companion(companion_name)  # VC5: via plaiground
        if not isinstance(max_uses, int) or max_uses < 1:
            raise VeilCompanionError("max_uses must be a positive int")
        if not (0 < float(ttl_hours) <= 24 * 90):
            raise VeilCompanionError("ttl_hours must be within (0, 2160]")
        now = time.time()
        invite_id = uuid.uuid4().hex
        definition_hash = hashlib.sha256(
            json.dumps(definition, sort_keys=True).encode("utf-8")).hexdigest()
        payload = {
            "v": 1,
            "id": invite_id,
            "companion": definition["name"],
            "traits": definition.get("traits", []),
            "boundaries": definition.get("boundaries", []),
            "definition_hash": definition_hash,
            "max_uses": max_uses,
            "exp": now + float(ttl_hours) * 3600.0,
            "nonce": secrets.token_hex(8),
        }
        ticket = self._sign_ticket(payload)
        invites = self._read_invites()
        invites[invite_id] = {
            "id": invite_id,
            "companion": definition["name"],
            "max_uses": max_uses,
            "uses": 0,
            "exp": payload["exp"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_invites(invites)
        self._audit_event("veil.companion.invite_issued", {
            "invite_id": _short(invite_id),
            "companion": definition["name"],
            "max_uses": max_uses,
        })
        return {
            "invite_id": invite_id,
            "companion": definition["name"],
            "qr_payload": _QR_SCHEME + ticket,
            "expires_at": datetime.fromtimestamp(
                payload["exp"], timezone.utc).isoformat(),
        }

    def redeem_companion_qr(self, qr_payload_or_ticket: str) -> Dict:
        """Redeem a companion-share ticket: verify, then provision the
        persona locally through plaiground's own gate-checked
        :func:`create_companion` (VC5, VC6).

        Fails closed when: the ticket is forged/expired/used-up, or the
        Plaiground gate is locked on this device — a companion can never
        be defined with the gate off (VC1).
        """
        require_adult()  # VC1 first: no definition with the gate off
        token = qr_payload_or_ticket.strip()
        if token.startswith(_QR_SCHEME):
            token = token[len(_QR_SCHEME):]
        payload = self._verify_ticket(token)
        if time.time() > float(payload.get("exp", 0)):
            raise VeilCompanionError("companion invite expired")
        invites = self._read_invites()
        inv = invites.get(payload.get("id", ""))
        if inv is None:
            raise VeilCompanionError("unknown companion invite")
        if int(inv.get("uses", 0)) >= int(inv.get("max_uses", 1)):
            raise VeilCompanionError("companion invite already redeemed")
        # Re-validate the persona through plaiground (VC5/VC6): the ticket
        # is data, create_companion is the law.
        record = create_companion(
            payload["companion"],
            traits=list(payload.get("traits", [])) or None,
            boundaries=list(payload.get("boundaries", [])) or None,
        )
        inv["uses"] = int(inv.get("uses", 0)) + 1
        self._write_invites(invites)
        self._audit_event("veil.companion.invite_redeemed", {
            "invite_id": _short(str(payload.get("id", ""))),
            "companion": record["name"],
        })
        return {
            "companion": record["name"],
            "traits": record["traits"],
            "boundaries": record["boundaries"],
        }

    # -- companion management (through plaiground, gate-checked) -------------------
    def create_companion(self, name: str, traits=None, boundaries=None) -> Dict:
        """Define a companion persona. Thin pass-through to plaiground —
        the gate, validation, and storage all live there (VC5)."""
        require_adult()
        record = create_companion(name, traits=traits, boundaries=boundaries)
        self._audit_event("veil.companion.created", {"companion": record["name"]})
        return record

    def available_companions(self) -> List[str]:
        """Companion names defined on this device. Gate-checked."""
        require_adult()
        return list_companions()
