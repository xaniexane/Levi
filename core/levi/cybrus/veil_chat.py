"""Veil Chat — end-to-end encrypted conversations on top of ``veil.py``.

What this is
------------
A two-party E2E messenger layer built on the keeper's Veil crypto core
(``levi.cybrus.veil``). Each keeper runs their own ``VeilChat`` rooted at
their own vault (``~/.levi/cybrus/veil/e2e/``, ``LEVI_HOME`` honored); two
keepers talk by exchanging handshake offers/answers and sealed envelopes.
Nothing here invents crypto: X25519 key agreement is RFC 7748, envelopes
are AES-256-GCM (or veil.py's honestly-labeled stdlib fallback) via
veil.py's versioned ``_seal_backend``/``_open_backend``, keys derive via
HKDF-SHA256, the passphrase KDF is scrypt/PBKDF2 exactly like veil.py.

The protocol, in plain words
----------------------------
1. **Identity.** Each keeper's static X25519 identity key is *derived* from
   their passphrase (HKDF over the master key) — there is no identity
   private key at rest to steal. The public key's grouped-hex fingerprint
   is the verification ceremony (compare out of band, like veil.py).
   Identity keys authenticate; they never encrypt.
2. **Handshake (ECDH, MITM-resistant).** To open a conversation, both sides
   generate fresh *ephemeral* X25519 keypairs and exchange the publics.
   The chain root mixes three DHs: ephemeral×ephemeral plus both
   static×ephemeral combinations with the registered identity keys
   (Noise-XX/X3DH pattern). An active attacker substituting ephemerals
   cannot compute the static terms without a static private key, so they
   cannot derive the chains — the fingerprint ceremony on the registered
   identity keys is therefore meaningful. Offers and answers each carry
   an HMAC authenticator under the static-static DH, so forged offers,
   forged answers, and answers from the wrong peer fail closed before
   any key is derived. Ephemeral keys are zeroized the moment the
   handshake finishes.
3. **Ratchet.** Every message advances the sender's chain:
   ``msg_key = HKDF(chain, "msg")``, then ``chain = HKDF(chain, "next")``
   and the old chain key is **destroyed** (zeroized in memory, the sealed
   copy on disk overwritten). A seized current chain key decrypts nothing
   sent before it — that is the forward secrecy, and it is one-way by
   construction.
4. **Envelopes.** Sealed envelopes carry sender fingerprint, conversation
   id, epoch, and a per-sender strictly increasing sequence number, all
   bound into the AAD. Tampered envelopes, replays, and out-of-order
   messages fail closed.
5. **At rest, layered.** Message keys are wrapped (sealed) under their
   epoch key; epoch keys are wrapped under a master-derived wrap key; the
   wrap key is derived on demand and never stored. Owner-only files
   (0o600), atomic writes, the ``_paths`` store conventions. Rotating the
   epoch (fresh handshake) keeps the previous epoch for in-flight
   envelopes and **destroys** older ones — sealed epoch keys deleted,
   wrapped message keys pruned, memory zeroized.

Honest limits: see ``NON_CLAIMS`` and ``crypto_report()``. In particular:
the pure-Python X25519 fallback is not constant-time; the ratchet is
symmetric per direction (no DH ratchet — concurrent in-flight messages
from the *same* sender are fine, out-of-order arrival fails closed and
must be re-sent); identity keys are passphrase-derived, so a new
passphrase is a new identity.

Operating laws (built in, not just followed)
-------------------------------------------
Chauncey's seven operating laws are runtime-checkable invariants here,
declared as L6–L12 in the machine-readable ``LAWS`` tuple (L1–L5 are the
crypto laws) and checked by ``verify_laws()`` plus the invariant tests:

- keeper's law / anticipation — every refusal names its remedy;
  preconditions (locked stores, owner-only perms) are verified, not assumed
- originals-first — registered peers are originals, never silently re-keyed
- law→guard→prove — laws declared first, guards enforce, invariant tests
  check (honestly named: never "formally proven")
- no-cancellation — no API removes another conversation, a peer with
  conversations, an envelope, or a relay descriptor
- nothing-thrown-away — state only grows; the ONE exception is key
  destruction, which IS the forward-secrecy requirement (documented as such)
- forward-motion — pending handshakes are listed in ``crypto_report()``,
  never silently stuck
- honesty over polish — ``crypto_report()`` states the real posture

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import uuid
from pathlib import Path
from typing import Optional

from levi.cybrus import veil as _veil
from levi.cybrus._paths import atomic_write_bytes, cybrus_dir, store_lock
from levi.cybrus.enforce import cybrus_guarded
from levi.cybrus.veil import (
    VeilError,
    _b64d,
    _b64e,
    _derive_master,
    _hkdf,
    _kdf_default,
    _open_backend,
    _seal_backend,
    _utcnow,
    fingerprint,
)

# ---------------------------------------------------------------------------
# X25519 key agreement (RFC 7748) — backend resolved once, reported honestly
# ---------------------------------------------------------------------------

_X25519_PRIME = 2**255 - 19
_X25519_A24 = 121665  # (486662 - 2) / 4, per RFC 7748 section 5


def _x25519_impl_name() -> str:
    """Resolve the X25519 backend: the ``cryptography`` package when
    importable, else the pure-Python RFC 7748 implementation, else
    unavailable (handshakes fail closed)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (  # type: ignore
            X25519PrivateKey,
        )

        return "cryptography"
    except Exception:
        return "pure-python"


_X25519_SOURCE = _x25519_impl_name()


def _decode_scalar_25519(k: bytes) -> int:
    """Clamp 32 random bytes into an X25519 scalar (RFC 7748, section 5)."""
    if len(k) != 32:
        raise VeilChatError("X25519 scalar must be 32 bytes")
    b = bytearray(k)
    b[0] &= 248
    b[31] &= 127
    b[31] |= 64
    return int.from_bytes(bytes(b), "little")


def _cswap(swap: int, x: int, y: int) -> tuple[int, int]:
    dummy = (-swap) & (x ^ y)
    return (x ^ dummy, y ^ dummy)


def _x25519_ladder(k: int, u: int) -> int:
    """Montgomery ladder, RFC 7748 section 5. Correct, not constant-time:
    this is the labeled fallback, never the preferred path when the
    ``cryptography`` package is present."""
    p = _X25519_PRIME
    x1 = u
    x2, z2, x3, z3 = 1, 0, u, 1
    swap = 0
    for t in range(254, -1, -1):
        kt = (k >> t) & 1
        swap ^= kt
        x2, x3 = _cswap(swap, x2, x3)
        z2, z3 = _cswap(swap, z2, z3)
        swap = kt
        a = (x2 + z2) % p
        aa = (a * a) % p
        b_ = (x2 - z2) % p
        bb = (b_ * b_) % p
        e = (aa - bb) % p
        c = (x3 + z3) % p
        d = (x3 - z3) % p
        da = (d * a) % p
        cb = (c * b_) % p
        x3 = pow(da + cb, 2, p)
        z3 = (pow(da - cb, 2, p) * x1) % p
        x2 = (aa * bb) % p
        z2 = (e * (aa + _X25519_A24 * e)) % p
    x2, x3 = _cswap(swap, x2, x3)
    z2, z3 = _cswap(swap, z2, z3)
    return (x2 * pow(z2, p - 2, p)) % p


def _x25519_pure(private_key: bytes, public_key: bytes) -> bytes:
    """X25519 via the pure-Python Montgomery ladder. Verified against the
    RFC 7748 section 5.2, 6.1, and iterated test vectors in
    ``tests/test_veil_chat.py``. Fallback-grade: not constant-time."""
    if len(public_key) != 32:
        raise VeilChatError("X25519 public key must be 32 bytes")
    k = _decode_scalar_25519(private_key)
    u = int.from_bytes(public_key, "little") & ((1 << 255) - 1)
    return _x25519_ladder(k, u).to_bytes(32, "little")


def _x25519_pure_public(private_key: bytes) -> bytes:
    k = _decode_scalar_25519(private_key)
    return _x25519_ladder(k, 9).to_bytes(32, "little")


def x25519_backend() -> str:
    """Honestly labeled X25519 backend: ``"cryptography-x25519"``,
    ``"pure-python-fallback"``, or ``"unavailable"``."""
    return {
        "cryptography": "cryptography-x25519",
        "pure-python": "pure-python-fallback",
    }.get(_X25519_SOURCE, "unavailable")


def _x25519_available() -> bool:
    return _X25519_SOURCE in ("cryptography", "pure-python")


def x25519(private_key: bytes, public_key: bytes) -> bytes:
    """X25519 ECDH shared secret. Fails closed when no backend exists —
    never silently substitutes something weaker."""
    if len(private_key) != 32 or len(public_key) != 32:
        raise VeilChatError("X25519 keys must be 32 bytes")
    if _X25519_SOURCE == "cryptography":
        from cryptography.hazmat.primitives.asymmetric.x25519 import (  # type: ignore
            X25519PrivateKey,
            X25519PublicKey,
        )

        priv = X25519PrivateKey.from_private_bytes(private_key)
        pub = X25519PublicKey.from_public_bytes(public_key)
        return priv.exchange(pub)
    if _X25519_SOURCE == "pure-python":
        return _x25519_pure(private_key, public_key)
    raise VeilChatError(
        "no X25519 backend available (cryptography package missing and "
        "pure-Python fallback disabled); refusing to handshake"
    )


def x25519_public(private_key: bytes) -> bytes:
    """Public key for a 32-byte private key. Fails closed like :func:`x25519`."""
    if len(private_key) != 32:
        raise VeilChatError("X25519 private key must be 32 bytes")
    if _X25519_SOURCE == "cryptography":
        from cryptography.hazmat.primitives.asymmetric.x25519 import (  # type: ignore
            X25519PrivateKey,
        )

        return X25519PrivateKey.from_private_bytes(
            private_key
        ).public_key().public_bytes_raw()
    if _X25519_SOURCE == "pure-python":
        return _x25519_pure_public(private_key)
    raise VeilChatError("no X25519 backend available; refusing to derive public key")


class VeilChatError(VeilError):
    """All Veil Chat failures: locked vaults, bad handshakes, tampered or
    replayed envelopes, destroyed epochs. Fail-closed by construction."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROTOCOL_VERSION = 1
_E2E_SUBDIR = "e2e"
_CONFIG_FILE = "config.json"
_IDENTITY_FILE = "identity.json"
_PEERS_FILE = "peers.json"
_CONV_DIR = "conversations"
_MSGKEY_DIR = "msgkeys"
_MESSAGES_DIR = "messages"

_INFO_IDENTITY = b"veilchat-identity-v1\x00"
_INFO_WRAP = b"veilchat-wrap-v1\x00"
_INFO_CHAIN = b"veilchat-chain-v1\x00"
_INFO_MSG = b"veilchat-msg-v1\x00"
_INFO_CHAIN_NEXT = b"veilchat-chain-next-v1\x00"
_INFO_CHAIN_ROOT = b"veilchat-chainroot-v1\x00"
_INFO_OFFER_AUTH = b"veilchat-offer-auth-v1\x00"
_INFO_ANSWER_AUTH = b"veilchat-answer-auth-v1\x00"

_EPOCH_GRACE = 1  # previous epoch stays openable for in-flight envelopes


# ---------------------------------------------------------------------------
# VeilChat — the keeper's E2E conversation endpoint
# ---------------------------------------------------------------------------


class VeilChat:
    """One keeper's end of every E2E conversation.

    Rooted at ``<cybrus>/veil/e2e/`` (owner-only). The passphrase derives
    the master key (scrypt/PBKDF2, pinned per vault like veil.py); the
    master derives the static identity key, the per-conversation wrap keys,
    and nothing else. Chain keys and message keys live in memory only while
    a send/receive is in flight and sealed under epoch keys at rest.
    """

    def __init__(self, passphrase: str, home: Optional[Path] = None) -> None:
        base = Path(home) if home is not None else cybrus_dir() / "veil"
        self._home = base / _E2E_SUBDIR
        self._home.mkdir(parents=True, exist_ok=True)
        os.chmod(self._home, 0o700)
        self._master: Optional[bytearray] = None
        self._salt: bytes = b""
        self._kdf: str = _kdf_default()
        # Pending handshakes: conv_id -> {"eph_priv": bytearray,
        # "peer_id": str, "rotate": bool}. Memory-only: a restart before the
        # handshake finishes means starting over (documented, fail-closed).
        self._pending: dict[str, dict] = {}
        self._load_or_init(passphrase)

    # -- vault open / lock -------------------------------------------------

    def _path(self, name: str) -> Path:
        return self._home / name

    def _load_or_init(self, passphrase: str) -> None:
        cfg_path = self._path(_CONFIG_FILE)
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                salt = _b64d(cfg["salt"])
                verifier = _b64d(cfg["verifier"])
                kdf = cfg.get("kdf", "pbkdf2")
            except (KeyError, ValueError, OSError) as exc:
                raise VeilChatError("chat config unreadable: %s" % exc) from exc
            if kdf not in ("scrypt", "pbkdf2"):
                raise VeilChatError("chat config unreadable: unknown kdf %r" % (kdf,))
            candidate = bytearray(_derive_master(passphrase, salt, kdf))
            expect = hmac.new(
                bytes(candidate), b"veilchat-verify-v1", hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expect, verifier):
                _zero(candidate)
                raise VeilChatError("wrong passphrase")
            self._salt, self._kdf, self._master = salt, kdf, candidate
        else:
            salt = secrets.token_bytes(16)
            kdf = _kdf_default()
            master = bytearray(_derive_master(passphrase, salt, kdf))
            verifier = hmac.new(
                bytes(master), b"veilchat-verify-v1", hashlib.sha256
            ).digest()
            cfg = {
                "salt": _b64e(salt),
                "verifier": _b64e(verifier),
                "kdf": kdf,
                "created_at": _utcnow(),
                "protocol_version": _PROTOCOL_VERSION,
            }
            atomic_write_bytes(cfg_path, json.dumps(cfg, indent=2).encode("utf-8"))
            self._salt, self._kdf, self._master = salt, kdf, master
        self._write_identity()

    @property
    def is_locked(self) -> bool:
        return self._master is None

    def _require_unlocked(self) -> bytes:
        if self._master is None:
            raise VeilChatError("chat vault is locked")
        return bytes(self._master)

    def lock(self) -> None:
        """Best-effort zeroize the master key and every pending ephemeral."""
        if self._master is not None:
            _zero(self._master)
            self._master = None
        for pending in self._pending.values():
            _zero(pending["eph_priv"])
        self._pending.clear()

    def unlock(self, passphrase: str) -> None:
        if self._master is not None:
            return
        cfg = json.loads(self._path(_CONFIG_FILE).read_text(encoding="utf-8"))
        salt, kdf = _b64d(cfg["salt"]), cfg.get("kdf", "pbkdf2")
        candidate = bytearray(_derive_master(passphrase, salt, kdf))
        expect = hmac.new(
            bytes(candidate), b"veilchat-verify-v1", hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expect, _b64d(cfg["verifier"])):
            _zero(candidate)
            raise VeilChatError("wrong passphrase")
        self._salt, self._kdf, self._master = salt, kdf, candidate

    # -- identity ----------------------------------------------------------

    def _identity_priv(self) -> bytes:
        """Static identity private key: derived from the master key, never
        stored. A new passphrase is a new identity (documented limit)."""
        master = self._require_unlocked()
        return _hkdf(master, self._salt, _INFO_IDENTITY, 32)

    def _identity_pub(self) -> bytes:
        return x25519_public(self._identity_priv())

    def _write_identity(self) -> None:
        """Publish the public identity (public key + fingerprint). The
        private half is derived on demand and never written."""
        pub = self._identity_pub()
        record = {
            "public_key": _b64e(pub),
            "fingerprint": fingerprint(pub),
            "x25519_backend": x25519_backend(),
            "created_at": _utcnow(),
            "protocol_version": _PROTOCOL_VERSION,
        }
        atomic_write_bytes(
            self._path(_IDENTITY_FILE), json.dumps(record, indent=2).encode("utf-8")
        )

    def identity(self) -> dict:
        """Public identity: X25519 public key and its fingerprint for the
        out-of-band verification ceremony."""
        return json.loads(self._path(_IDENTITY_FILE).read_text(encoding="utf-8"))

    def crypto_report(self) -> dict:
        """Honest crypto posture: every backend named, nothing implied.

        Also the forward-motion ledger (L11): pending handshakes are
        listed with metadata only, so interrupted work is visible and
        resumable instead of silently stuck."""
        return {
            "x25519": x25519_backend(),
            "x25519_note": (
                "NOT constant-time; fallback-grade"
                if _X25519_SOURCE == "pure-python"
                else ("RFC 7748 via the cryptography package"
                      if _X25519_SOURCE == "cryptography"
                      else "UNAVAILABLE — handshakes fail closed")
            ),
            "envelope_aead": (
                "aes-256-gcm" if _veil._AESGCM is not None else "stdlib-fallback"
            ),
            "kdf": self._kdf,
            "protocol_version": _PROTOCOL_VERSION,
            "forward_secrecy": (
                "ephemeral-ephemeral ECDH handshake; per-message symmetric "
                "chain ratchet, old chain keys destroyed; epoch rotation via "
                "fresh handshake destroys epochs older than one grace epoch"
            ),
            "peers_registered": len(self._read_peers()),
            "conversations": len(self.list_conversations()),
            "pending_handshakes": [
                {
                    "conv_id": cid,
                    "peer_id": p["peer_id"],
                    "rotate": bool(p["rotate"]),
                }
                for cid, p in self._pending.items()
            ],
            "laws": [lid for lid, _ in LAWS],
        }

    def verify_laws(self) -> list[tuple[str, bool, str]]:
        """Runtime law checks against this keeper's live stores.

        Returns ``(law_id, holds, detail)`` per law — the guard gate for
        the operating laws (L6–L12) plus spot-checks of the crypto laws.
        Honest naming: these are machine-checked invariants, not proof.
        """
        results: list[tuple[str, bool, str]] = []

        def check(law: str, ok: bool, detail: str = "") -> None:
            results.append((law, ok, detail))

        rep = self.crypto_report()
        # L5/L12 — the reported posture matches reality.
        check("L5", rep["x25519"] == x25519_backend(), rep["x25519"])
        check(
            "L5",
            (rep["envelope_aead"] == "aes-256-gcm") == (_veil._AESGCM is not None),
            rep["envelope_aead"],
        )
        check("L12", len(NON_CLAIMS) >= 5, "%d non-claims" % len(NON_CLAIMS))
        check("L12", "laws" in rep and len(rep["laws"]) == len(LAWS), "laws listed")

        # L1 — sealed stores hold no raw key material: only wrapped_*
        # fields may carry key bytes; identity/peers are public-only.
        bad_fields: list[str] = []

        def _scan(obj, path: str) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    kl = k.lower()
                    if kl in ("chain_key", "epoch_key", "message_key", "private_key",
                              "master_key", "eph_priv"):
                        bad_fields.append("%s/%s" % (path, k))
                    _scan(v, path + "/" + k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _scan(v, "%s[%d]" % (path, i))

        conv_dir = self._home / _E2E_SUBDIR / _CONV_DIR
        if conv_dir.exists():
            for f in sorted(conv_dir.glob("*.json")):
                try:
                    _scan(json.loads(f.read_text(encoding="utf-8")), f.name)
                except (ValueError, OSError):
                    bad_fields.append(f.name + "/unreadable")
        check("L1", not bad_fields, "; ".join(bad_fields) or "stores hold wrapped keys only")

        # L2 — the epoch window: at most grace+1 epochs retained per conv.
        wide = []
        for conv in self.list_conversations():
            epochs = self._read_conv(conv["conv_id"]).get("epochs", {})
            if len(epochs) > _EPOCH_GRACE + 1:
                wide.append(conv["conv_id"][:8])
        check("L2", not wide, "; ".join(wide) or "epoch window respected")

        # L3 — every journaled envelope carries the AAD-bound fields.
        bad_env: list[str] = []
        for conv in self.list_conversations():
            for env in self.fetch_envelopes(conv["conv_id"]):
                if env.get("protocol_version") != _PROTOCOL_VERSION or not all(
                    k in env for k in ("conv_id", "epoch", "sender_fp", "seq", "blob")
                ):
                    bad_env.append(conv["conv_id"][:8])
                    break
        check("L3", not bad_env, "; ".join(bad_env) or "envelopes well-formed")

        # L6 — anticipation: owner-only perms on the secret-bearing stores.
        bad_perm = [
            p.name for p in (self._home / _E2E_SUBDIR).rglob("*")
            if p.is_file() and p.suffix != ".lock"
            and stat.S_IMODE(p.stat().st_mode) != 0o600
        ]
        check("L6", not bad_perm, "; ".join(bad_perm) or "owner-only perms hold")

        # L7 — originals-first: registered fingerprints still match the
        # registered keys (no silent re-keying, no tampering).
        bad_fp = [
            pid for pid, rec in self._read_peers().items()
            if rec.get("fingerprint") != fingerprint(_b64d(rec["public_key"]))
        ]
        check("L7", not bad_fp, "; ".join(bad_fp) or "peer originals intact")

        # L9 — no-cancellation: every conversation's peer still resolves.
        peers = self._read_peers()
        dangling = [
            c["conv_id"][:8] for c in self.list_conversations()
            if c["peer_id"] not in peers
        ]
        check("L9", not dangling, "; ".join(dangling) or "no dangling conversations")

        # L10 — nothing-thrown-away: the module exposes no deletion API
        # for messages, conversations, or peers-with-conversations.
        check(
            "L10",
            not any(hasattr(VeilChat, n) for n in ("delete_envelope", "delete_conversation", "purge_journal")),
            "no deletion API",
        )

        # L11 — forward-motion: pending handshakes are visible metadata.
        check("L11", isinstance(rep.get("pending_handshakes"), list), "%d pending" % len(rep.get("pending_handshakes", [])))
        return results

    # -- peers ---------------------------------------------------------------

    def _read_peers(self) -> dict:
        path = self._path(_PEERS_FILE)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise VeilChatError("peers registry unreadable: %s" % exc) from exc
        return data if isinstance(data, dict) else {}

    def _write_peers(self, peers: dict) -> None:
        with store_lock(self._path(_PEERS_FILE)):
            atomic_write_bytes(
                self._path(_PEERS_FILE),
                json.dumps(peers, indent=2, sort_keys=True).encode("utf-8"),
            )

    def add_peer(self, peer_id: str, public_key: bytes, name: str = "") -> dict:
        """Register a peer's *public* X25519 key. Trust is TOFU plus the
        fingerprint ceremony — verify out of band, then mark verified.

        Originals-first (L7): a peer id is never silently re-keyed.
        Re-adding the *same* key is idempotent; a *different* key for an
        existing id fails closed — call remove_peer() first (which itself
        refuses while conversations reference the peer, L9)."""
        _veil._sanitize(peer_id, "peer_id")
        self._require_unlocked()
        if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
            raise VeilChatError("peer public key must be 32 bytes")
        peers = self._read_peers()
        if peer_id in peers:
            existing = _b64d(peers[peer_id]["public_key"])
            if hmac.compare_digest(existing, bytes(public_key)):
                return peers[peer_id]
            raise VeilChatError(
                "peer %r is already registered with a different key — "
                "originals are never silently re-keyed; call remove_peer() "
                "first" % peer_id
            )
        peers[peer_id] = {
            "peer_id": peer_id,
            "name": name[:64],
            "public_key": _b64e(bytes(public_key)),
            "fingerprint": fingerprint(bytes(public_key)),
            "verified": False,
            "added_at": _utcnow(),
        }
        self._write_peers(peers)
        return peers[peer_id]

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer registration. No-cancellation (L9): refuses while
        any conversation references the peer — this module never drops a
        conversation's peer out from under it."""
        _veil._sanitize(peer_id, "peer_id")
        self._require_unlocked()
        peers = self._read_peers()
        if peer_id not in peers:
            raise VeilChatError("unknown peer %r" % peer_id)
        for conv in self.list_conversations():
            if conv["peer_id"] == peer_id:
                raise VeilChatError(
                    "cannot remove peer %r: conversation %s references it"
                    % (peer_id, conv["conv_id"][:8])
                )
        del peers[peer_id]
        self._write_peers(peers)

    def verify_peer_fingerprint(self, peer_id: str, candidate: str) -> bool:
        """The ceremony: compare a fingerprint read out of band. Marks the
        peer verified on match."""
        peers = self._read_peers()
        record = peers.get(peer_id)
        if record is None:
            return False
        norm = " ".join(candidate.lower().split())
        if not hmac.compare_digest(norm, record["fingerprint"]):
            return False
        record["verified"] = True
        self._write_peers(peers)
        return True

    def get_peer(self, peer_id: str) -> dict:
        peers = self._read_peers()
        record = peers.get(peer_id)
        if record is None:
            raise VeilChatError("unknown peer %r" % peer_id)
        return record

    # -- handshake -----------------------------------------------------------

    def _peer_pub(self, peer_id: str) -> bytes:
        return _b64d(self.get_peer(peer_id)["public_key"])

    @staticmethod
    def _transcript(eph_a: bytes, eph_b: bytes, id_a: bytes, id_b: bytes) -> bytes:
        """Handshake transcript binding: both ephemeral publics and both
        identity publics, each pair sorted so both sides compute the
        identical transcript regardless of who offered. Direction is bound
        separately by the chain derivation's info string."""
        e1, e2 = (eph_a, eph_b) if eph_a < eph_b else (eph_b, eph_a)
        i1, i2 = (id_a, id_b) if id_a < id_b else (id_b, id_a)
        return b"veilchat-hs-v1\x00" + e1 + e2 + i1 + i2

    @staticmethod
    def _derive_chain0(
        ee: bytes, dh_resp_static__init_eph: bytes, dh_init_static__resp_eph: bytes,
        transcript: bytes, sender_pub: bytes, receiver_pub: bytes,
    ) -> bytes:
        """Directional chain root, bound to the static identity keys.

        Three DH components, ordered canonically by handshake role
        (initiator = offerer, responder = answerer) so both sides derive
        the identical root:

        - ``ee``: ephemeral × ephemeral (forward secrecy at the handshake)
        - ``dh_resp_static__init_eph``: responder static × initiator ephemeral
        - ``dh_init_static__resp_eph``: initiator static × responder ephemeral

        The two static-ephemeral terms are the MITM defense (Noise-XX /
        X3DH pattern): an active attacker substituting ephemerals cannot
        compute them without one side's static identity private key, so
        they cannot derive the chain root even though every public value
        is on the wire. The fingerprint ceremony on the registered
        identity keys is therefore meaningful — only the holder of the
        registered static key completes the handshake.
        """
        root = _hkdf(
            ee + dh_resp_static__init_eph + dh_init_static__resp_eph,
            transcript,
            _INFO_CHAIN_ROOT,
            32,
        )
        return _hkdf(
            root, transcript, _INFO_CHAIN + sender_pub + b"\x00" + receiver_pub, 32
        )

    @staticmethod
    def _static_shared(own_static_priv: bytes, peer_static_pub: bytes) -> bytes:
        """Static-static DH between the two identity keys. Symmetric: both
        sides derive the same value, and only the two identity-key holders
        can compute it. Authenticates offers and answers (a poor-man's
        signature from the existing X25519 identity keys — no new key
        type, no new trust ceremony)."""
        shared = x25519(own_static_priv, peer_static_pub)
        if shared == bytes(32):
            raise VeilChatError("static DH produced all-zero secret; aborting")
        return shared

    def _offer_auth(
        self, peer_pub: bytes, conv_id: str, eph_pub: bytes, sender_fp: str
    ) -> str:
        """HMAC proving the offer came from the holder of the static key
        registered for this peer. The answerer recomputes it with their
        own static private — a forger cannot."""
        ss = self._static_shared(self._identity_priv(), peer_pub)
        return hmac.new(
            ss,
            _INFO_OFFER_AUTH
            + conv_id.encode("utf-8") + b"\x00"
            + eph_pub + b"\x00"
            + sender_fp.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _answer_auth(
        self, peer_pub: bytes, conv_id: str, eph_pub: bytes, transcript: bytes
    ) -> str:
        """HMAC proving the answer came from the registered peer's static
        key, bound to this exact handshake transcript. The offerer
        recomputes it — a forged answer (wrong peer, replayed onto a new
        offer) fails closed."""
        ss = self._static_shared(self._identity_priv(), peer_pub)
        return hmac.new(
            ss,
            _INFO_ANSWER_AUTH
            + conv_id.encode("utf-8") + b"\x00"
            + eph_pub + b"\x00"
            + transcript,
            hashlib.sha256,
        ).hexdigest()

    def handshake_offer(self, peer_id: str, conv_id: Optional[str] = None) -> dict:
        """Begin an ECDH handshake: fresh ephemeral keypair, offer carries
        the ephemeral public. Pass ``conv_id`` to re-handshake (epoch
        rotation) an existing conversation instead of opening a new one."""
        if not _x25519_available():
            raise VeilChatError(
                "no X25519 backend available; refusing to handshake"
            )
        self._require_unlocked()
        peer = self.get_peer(peer_id)  # unknown peer fails closed
        peer_pub = _b64d(peer["public_key"])
        if conv_id is not None:
            conv = self._read_conv(conv_id)
            if conv["peer_id"] != peer_id:
                raise VeilChatError("re-handshake peer mismatch")
        else:
            conv_id = uuid.uuid4().hex
        eph_priv = bytearray(secrets.token_bytes(32))
        try:
            eph_pub = x25519_public(bytes(eph_priv))
        except Exception:
            _zero(eph_priv)
            raise
        sender_fp = self.identity()["fingerprint"]
        self._pending[conv_id] = {
            "eph_priv": eph_priv,
            "eph_pub": eph_pub,
            "peer_id": peer_id,
            "rotate": conv_id is not None and self._conv_exists(conv_id),
        }
        return {
            "protocol_version": _PROTOCOL_VERSION,
            "conv_id": conv_id,
            "peer_id": peer_id,
            "eph_pub": _b64e(eph_pub),
            "sender_fp": sender_fp,
            # Proves the offer came from the holder of OUR static key, as
            # registered for this peer. Anyone else answering it, or anyone
            # forging it, fails the answerer's check.
            "auth": self._offer_auth(peer_pub, conv_id, eph_pub, sender_fp),
            "offered_at": _utcnow(),
        }

    def handshake_answer(self, offer: dict) -> dict:
        """Answer a handshake offer: fresh ephemeral, chain roots derived
        from the ephemeral-ephemeral DH *and* both static-ephemeral DHs
        (the MITM defense — see ``_derive_chain0``). The answer carries
        our ephemeral public plus an authenticator proving it came from
        the registered peer's static key; no third message is needed —
        both sides derive the same chains."""
        if not _x25519_available():
            raise VeilChatError("no X25519 backend available; refusing to handshake")
        self._require_unlocked()
        if not isinstance(offer, dict) or offer.get("protocol_version") != _PROTOCOL_VERSION:
            raise VeilChatError("bad handshake offer")
        conv_id = offer.get("conv_id", "")
        _veil._sanitize(conv_id, "conv_id")
        peer_eph_pub = _b64d(str(offer.get("eph_pub", "")))
        if len(peer_eph_pub) != 32:
            raise VeilChatError("bad ephemeral public key in offer")
        sender_fp = str(offer.get("sender_fp", ""))
        peer_id = self._peer_id_for_fingerprint(sender_fp)
        peer_pub = self._peer_pub(peer_id)
        # The offer must authenticate as the registered peer's static key.
        # A forged offer (substituted ephemeral, spoofed fingerprint) fails
        # here, before any key material is derived.
        expect_auth = self._offer_auth(peer_pub, conv_id, peer_eph_pub, sender_fp)
        if not hmac.compare_digest(str(offer.get("auth", "")), expect_auth):
            raise VeilChatError("handshake offer authentication failed")
        my_eph_priv = bytearray(secrets.token_bytes(32))
        try:
            my_eph_pub = x25519_public(bytes(my_eph_priv))
            ee = x25519(bytes(my_eph_priv), peer_eph_pub)
            # Responder static x initiator ephemeral...
            dh_resp_static__init_eph = x25519(self._identity_priv(), peer_eph_pub)
            # ...initiator static x responder ephemeral.
            dh_init_static__resp_eph = x25519(bytes(my_eph_priv), peer_pub)
        finally:
            _zero(my_eph_priv)
        if (
            ee == bytes(32)
            or dh_resp_static__init_eph == bytes(32)
            or dh_init_static__resp_eph == bytes(32)
        ):
            raise VeilChatError("handshake produced all-zero secret; aborting")
        my_pub = self._identity_pub()
        transcript = self._transcript(my_eph_pub, peer_eph_pub, my_pub, peer_pub)
        rotate = self._conv_exists(conv_id)
        if rotate and self._read_conv(conv_id)["peer_id"] != peer_id:
            raise VeilChatError("re-handshake peer mismatch")
        # Directional chain roots: (me -> peer) and (peer -> me).
        send0 = self._derive_chain0(
            ee, dh_resp_static__init_eph, dh_init_static__resp_eph,
            transcript, my_pub, peer_pub,
        )
        recv0 = self._derive_chain0(
            ee, dh_resp_static__init_eph, dh_init_static__resp_eph,
            transcript, peer_pub, my_pub,
        )
        epoch_key = secrets.token_bytes(32)
        self._store_epoch(conv_id, peer_id, send0, recv0, epoch_key, rotate=rotate)
        return {
            "protocol_version": _PROTOCOL_VERSION,
            "conv_id": conv_id,
            "eph_pub": _b64e(my_eph_pub),
            "sender_fp": self.identity()["fingerprint"],
            "auth": self._answer_auth(peer_pub, conv_id, my_eph_pub, transcript),
            "answered_at": _utcnow(),
        }

    def handshake_finish(self, answer: dict) -> str:
        """Complete our offered handshake: verify the answer came from the
        registered peer's static key, then derive the same directional
        chains the answerer derived. The ephemeral private is zeroized
        here — it never touches disk."""
        if not _x25519_available():
            raise VeilChatError("no X25519 backend available; refusing to handshake")
        self._require_unlocked()
        if not isinstance(answer, dict) or answer.get("protocol_version") != _PROTOCOL_VERSION:
            raise VeilChatError("bad handshake answer")
        conv_id = answer.get("conv_id", "")
        pending = self._pending.get(conv_id)
        if pending is None:
            raise VeilChatError("no pending handshake for this conversation")
        peer_eph_pub = _b64d(str(answer.get("eph_pub", "")))
        if len(peer_eph_pub) != 32:
            raise VeilChatError("bad ephemeral public key in answer")
        peer_id = pending["peer_id"]
        my_eph_pub = pending["eph_pub"]
        my_pub, peer_pub = self._identity_pub(), self._peer_pub(peer_id)
        transcript = self._transcript(my_eph_pub, peer_eph_pub, my_pub, peer_pub)
        # The answer must authenticate as the pending peer's static key,
        # bound to this exact transcript. A forged or relayed answer from
        # anyone else fails here — the conversation is never corrupted.
        expect_auth = self._answer_auth(peer_pub, conv_id, peer_eph_pub, transcript)
        if not hmac.compare_digest(str(answer.get("auth", "")), expect_auth):
            raise VeilChatError("handshake answer authentication failed")
        try:
            ee = x25519(bytes(pending["eph_priv"]), peer_eph_pub)
            # Responder static x initiator ephemeral (== answerer's term)...
            dh_resp_static__init_eph = x25519(bytes(pending["eph_priv"]), peer_pub)
            # ...initiator static x responder ephemeral (== answerer's term).
            dh_init_static__resp_eph = x25519(self._identity_priv(), peer_eph_pub)
        finally:
            _zero(pending["eph_priv"])
            del self._pending[conv_id]
        if (
            ee == bytes(32)
            or dh_resp_static__init_eph == bytes(32)
            or dh_init_static__resp_eph == bytes(32)
        ):
            raise VeilChatError("handshake produced all-zero secret; aborting")
        send0 = self._derive_chain0(
            ee, dh_resp_static__init_eph, dh_init_static__resp_eph,
            transcript, my_pub, peer_pub,
        )
        recv0 = self._derive_chain0(
            ee, dh_resp_static__init_eph, dh_init_static__resp_eph,
            transcript, peer_pub, my_pub,
        )
        epoch_key = secrets.token_bytes(32)
        self._store_epoch(
            conv_id, peer_id, send0, recv0, epoch_key, rotate=pending["rotate"]
        )
        return conv_id

    def _peer_id_for_fingerprint(self, fp: str) -> str:
        norm = " ".join(fp.lower().split())
        for peer_id, record in self._read_peers().items():
            if hmac.compare_digest(record["fingerprint"], norm):
                return peer_id
        raise VeilChatError("handshake from unknown peer fingerprint")

    # -- conversation store (sealed, layered) ----------------------------------

    def _conv_path(self, conv_id: str) -> Path:
        _veil._sanitize(conv_id, "conv_id")
        d = self._home / _CONV_DIR
        d.mkdir(exist_ok=True)
        return d / (conv_id + ".json")

    def _conv_exists(self, conv_id: str) -> bool:
        try:
            return self._conv_path(conv_id).exists()
        except VeilChatError:
            return False

    def _read_conv(self, conv_id: str) -> dict:
        path = self._conv_path(conv_id)
        if not path.exists():
            raise VeilChatError("unknown conversation")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise VeilChatError("conversation store unreadable: %s" % exc) from exc
        if not isinstance(data, dict) or data.get("conv_id") != conv_id:
            raise VeilChatError("conversation store corrupt")
        return data

    def _write_conv(self, conv: dict) -> None:
        path = self._conv_path(conv["conv_id"])
        with store_lock(path):
            atomic_write_bytes(
                path, json.dumps(conv, indent=2, sort_keys=True).encode("utf-8")
            )

    def _wrap_key(self, conv_id: str) -> bytes:
        """Master-derived wrap key: seals epoch keys. Derived on demand,
        never stored — but a master-key compromise unwraps the *live*
        epochs (documented residual, same as veil.py)."""
        master = self._require_unlocked()
        return _hkdf(master, self._salt, _INFO_WRAP + conv_id.encode("utf-8"), 32)

    @staticmethod
    def _conv_aad(conv_id: str, epoch: int, purpose: bytes) -> bytes:
        return purpose + conv_id.encode("utf-8") + b"\x00" + str(epoch).encode("ascii")

    def _store_epoch(
        self,
        conv_id: str,
        peer_id: str,
        send0: bytes,
        recv0: bytes,
        epoch_key: bytes,
        rotate: bool,
    ) -> int:
        """Persist a new epoch, layered: chain state sealed under the epoch
        key; the epoch key sealed under the master-derived wrap key.
        Rotation keeps one grace epoch and DESTROYS older ones — sealed
        epoch keys deleted, wrapped message keys pruned, memory zeroized."""
        wrap = self._wrap_key(conv_id)
        if rotate:
            conv = self._read_conv(conv_id)
            epoch = int(conv["epoch"]) + 1
            sealed_epoch_keys = conv["sealed_epoch_keys"]
            sealed_chains = conv["sealed_chains"]
            send_seq = int(conv["send_seq"])
            recv_seq = int(conv["recv_seq"])
        else:
            epoch = 1
            sealed_epoch_keys, sealed_chains = {}, {}
            send_seq, recv_seq = 0, 0
        sealed_epoch_keys[str(epoch)] = _b64e(
            _seal_backend(
                wrap, epoch_key, self._conv_aad(conv_id, epoch, b"veilchat-epochkey")
            )
        )
        chain_state = json.dumps(
            {
                "send_chain": _b64e(send0),
                "recv_chain": _b64e(recv0),
                "send_seq": send_seq,
                "recv_seq": recv_seq,
            },
            sort_keys=True,
        ).encode("utf-8")
        sealed_chains[str(epoch)] = _b64e(
            _seal_backend(
                epoch_key,
                chain_state,
                self._conv_aad(conv_id, epoch, b"veilchat-chainstate"),
            )
        )
        # Grace window: current + previous live; older are destroyed.
        for old in [e for e in sealed_epoch_keys if int(e) < epoch - _EPOCH_GRACE]:
            del sealed_epoch_keys[old]
        for old in [e for e in sealed_chains if int(e) < epoch - _EPOCH_GRACE]:
            del sealed_chains[old]
        conv = {
            "conv_id": conv_id,
            "peer_id": peer_id,
            "epoch": epoch,
            "send_seq": send_seq,
            "recv_seq": recv_seq,
            "sealed_epoch_keys": sealed_epoch_keys,
            "sealed_chains": sealed_chains,
            "updated_at": _utcnow(),
        }
        self._write_conv(conv)
        if rotate:
            self._prune_msgkeys(conv_id, epoch)
        return epoch

    def _epoch_key(self, conv_id: str, epoch: int) -> bytes:
        conv = self._read_conv(conv_id)
        sealed = conv["sealed_epoch_keys"].get(str(epoch))
        if not sealed:
            raise VeilChatError(
                "epoch %d of conversation destroyed or unknown" % epoch
            )
        return _open_backend(
            self._wrap_key(conv_id),
            _b64d(sealed),
            self._conv_aad(conv_id, epoch, b"veilchat-epochkey"),
        )

    def _load_chain_state(self, conv_id: str, epoch: int) -> dict:
        conv = self._read_conv(conv_id)
        sealed = conv["sealed_chains"].get(str(epoch))
        if not sealed:
            raise VeilChatError(
                "chain state for epoch %d destroyed or unknown" % epoch
            )
        raw = _open_backend(
            self._epoch_key(conv_id, epoch),
            _b64d(sealed),
            self._conv_aad(conv_id, epoch, b"veilchat-chainstate"),
        )
        return json.loads(raw.decode("utf-8"))

    def _save_chain_state(
        self, conv_id: str, epoch: int, send_chain: bytes, recv_chain: bytes,
        send_seq: int, recv_seq: int,
    ) -> None:
        conv = self._read_conv(conv_id)
        chain_state = json.dumps(
            {
                "send_chain": _b64e(bytes(send_chain)),
                "recv_chain": _b64e(bytes(recv_chain)),
                "send_seq": send_seq,
                "recv_seq": recv_seq,
            },
            sort_keys=True,
        ).encode("utf-8")
        conv["sealed_chains"][str(epoch)] = _b64e(
            _seal_backend(
                self._epoch_key(conv_id, epoch),
                chain_state,
                self._conv_aad(conv_id, epoch, b"veilchat-chainstate"),
            )
        )
        conv["send_seq"] = send_seq
        conv["recv_seq"] = recv_seq
        conv["updated_at"] = _utcnow()
        self._write_conv(conv)

    @staticmethod
    def _chain_advance(chain_key: bytes) -> tuple[bytes, bytes]:
        """One ratchet step: derive the message key, then the next chain
        key. The caller MUST destroy the old chain key after this returns."""
        if len(chain_key) != 32:
            raise VeilChatError("chain key must be 32 bytes")
        msg_key = _hkdf(chain_key, b"", _INFO_MSG, 32)
        next_chain = _hkdf(chain_key, b"", _INFO_CHAIN_NEXT, 32)
        return msg_key, next_chain

    # -- messaging -------------------------------------------------------------

    @staticmethod
    def _envelope_aad(header: dict) -> bytes:
        return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def send_message(self, conv_id: str, plaintext: bytes) -> dict:
        """Seal one message: advance our send chain, wrap the message key
        under the epoch key (layered at-rest), destroy the old chain key.
        Returns the sealed envelope (safe to hand to any transport)."""
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise VeilChatError("plaintext must be non-empty bytes")
        self._require_unlocked()
        conv = self._read_conv(conv_id)
        epoch = int(conv["epoch"])
        state = self._load_chain_state(conv_id, epoch)
        send_chain = bytearray(_b64d(state["send_chain"]))
        recv_chain = bytearray(_b64d(state["recv_chain"]))
        try:
            msg_key, next_chain = self._chain_advance(bytes(send_chain))
            seq = int(state["send_seq"]) + 1
            header = {
                "protocol_version": _PROTOCOL_VERSION,
                "conv_id": conv_id,
                "epoch": epoch,
                "sender_fp": self.identity()["fingerprint"],
                "seq": seq,
                "sent_at": _utcnow(),
            }
            blob = _seal_backend(msg_key, bytes(plaintext), self._envelope_aad(header))
            # Layered at-rest: the message key, wrapped under the epoch key.
            self._wrap_msgkey(conv_id, epoch, header["sender_fp"], seq, msg_key)
            envelope = dict(header)
            envelope["blob"] = _b64e(blob)
            # Ratchet forward: the old chain key is destroyed here.
            _zero(send_chain)
            send_chain = bytearray(next_chain)
            self._save_chain_state(
                conv_id, epoch, bytes(send_chain), bytes(recv_chain),
                seq, int(state["recv_seq"]),
            )
        finally:
            _zero(send_chain)
            _zero(recv_chain)
        self._store_envelope(conv_id, envelope)
        return envelope

    def receive_message(self, envelope: dict) -> dict:
        """Open and authenticate an envelope. Fails closed on: bad version,
        unknown conversation, unknown/destroyed epoch, tampered blob or
        header, replayed or out-of-order sequence."""
        if not isinstance(envelope, dict):
            raise VeilChatError("envelope must be a dict")
        if envelope.get("protocol_version") != _PROTOCOL_VERSION:
            raise VeilChatError("unsupported protocol version")
        conv_id = envelope.get("conv_id", "")
        conv = self._read_conv(conv_id)
        epoch = envelope.get("epoch")
        if not isinstance(epoch, int) or epoch < 1:
            raise VeilChatError("bad epoch")
        sender_fp = str(envelope.get("sender_fp", ""))
        try:
            peer_id = self._peer_id_for_fingerprint(sender_fp)
        except VeilChatError:
            raise VeilChatError("envelope from unknown peer")
        if peer_id != conv["peer_id"]:
            raise VeilChatError("envelope peer does not match conversation")
        if sender_fp == self.identity()["fingerprint"]:
            raise VeilChatError("refusing own envelope (send/recv chains differ)")
        seq = envelope.get("seq")
        if not isinstance(seq, int) or seq < 1:
            raise VeilChatError("bad sequence number")
        self._require_unlocked()
        state = self._load_chain_state(conv_id, epoch)
        if seq != int(state["recv_seq"]) + 1:
            raise VeilChatError(
                "out-of-order or replayed message (got seq %d, expected %d)"
                % (seq, int(state["recv_seq"]) + 1)
            )
        header = {
            k: envelope[k]
            for k in (
                "protocol_version", "conv_id", "epoch",
                "sender_fp", "seq", "sent_at",
            )
        }
        blob = _b64d(str(envelope.get("blob", "")))
        send_chain = bytearray(_b64d(state["send_chain"]))
        recv_chain = bytearray(_b64d(state["recv_chain"]))
        try:
            msg_key, next_chain = self._chain_advance(bytes(recv_chain))
            try:
                plaintext = _open_backend(msg_key, blob, self._envelope_aad(header))
            except VeilError as exc:
                # The inner veil AEAD speaks VeilError; the public chat API
                # speaks VeilChatError. Tampered blobs fail closed here.
                raise VeilChatError("envelope authentication failed") from exc
            self._wrap_msgkey(conv_id, epoch, sender_fp, seq, msg_key)
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
        return {
            "plaintext": plaintext,
            "conv_id": conv_id,
            "epoch": epoch,
            "sender_fp": sender_fp,
            "seq": seq,
            "sent_at": envelope.get("sent_at"),
        }

    @cybrus_guarded(service="levi.veilchat", callee="levi.onion", action="onion_send")
    def send_via_onion(self, conv_id: str, plaintext: bytes, deliver):
        """Seal a chat envelope and hand it to the onion transport.

        The chat -> onion handoff is an internal service call
        (``levi.veilchat`` -> ``levi.onion``) and crosses the Cybrus choke
        point BEFORE the body runs: unauthenticated, over-limit, or
        policy-denied means the envelope is never even sealed — the body
        never runs on refusal. Pass ``cybrus_credential=`` (or
        ``cybrus_api_key=`` + ``cybrus_gateway=``); the guard pops the
        ``cybrus_*`` kwargs and never logs them. ``cybrus_payload_ref=``
        may carry the conversation id — metadata only, never content
        (the choke point deliberately has no payload parameter).

        ``deliver`` is the transport callable (e.g. a function driving a
        ``levi.cybrus.onion`` circuit); it receives the sealed envelope
        dict and returns the transport's delivery report.

        Deployment note: ``levi.veilchat`` and ``levi.onion`` must be
        registered as internal routes and the policy must allow
        ``(levi.veilchat, service.levi.onion, onion_send)`` — seed policy
        is default-deny, so this fails closed until the service owner
        adds the rule.
        """
        envelope = self.send_message(conv_id, plaintext)
        return {"envelope": envelope, "transport": deliver(envelope)}

    # -- message-key journal (wrapped per-epoch) ---------------------------------

    def _msgkey_path(self, conv_id: str) -> Path:
        _veil._sanitize(conv_id, "conv_id")
        d = self._home / _MSGKEY_DIR
        d.mkdir(exist_ok=True)
        return d / (conv_id + ".jsonl")

    def _msgkey_aad(self, conv_id: str, epoch: int, sender_fp: str, seq: int) -> bytes:
        return (
            b"veilchat-msgkey\x00"
            + conv_id.encode("utf-8") + b"\x00"
            + str(epoch).encode("ascii") + b"\x00"
            + sender_fp.encode("utf-8") + b"\x00"
            + str(seq).encode("ascii")
        )

    def _wrap_msgkey(
        self, conv_id: str, epoch: int, sender_fp: str, seq: int, msg_key: bytes
    ) -> None:
        """Wrap a used message key under its epoch key: the at-rest layer
        that keeps sealed envelopes re-openable while the epoch lives."""
        sealed = _seal_backend(
            self._epoch_key(conv_id, epoch),
            msg_key,
            self._msgkey_aad(conv_id, epoch, sender_fp, seq),
        )
        entry = {
            "epoch": epoch,
            "sender_fp": sender_fp,
            "seq": seq,
            "sealed": _b64e(sealed),
        }
        path = self._msgkey_path(conv_id)
        with store_lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
            os.chmod(path, 0o600)

    def _prune_msgkeys(self, conv_id: str, epoch: int) -> None:
        """Destroy wrapped message keys for epochs older than the grace
        window. Their envelopes become permanently unopenable — that is
        the forward secrecy working."""
        path = self._msgkey_path(conv_id)
        if not path.exists():
            return
        keep = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if int(entry.get("epoch", 0)) >= epoch - _EPOCH_GRACE:
                keep.append(line)
        with store_lock(path):
            atomic_write_bytes(
                path, ("\n".join(keep) + ("\n" if keep else "")).encode("utf-8")
            )

    def open_journal_envelope(self, conv_id: str, envelope: dict) -> bytes:
        """Re-open a stored sealed envelope using its wrapped message key.
        Works only while the envelope's epoch is live — a destroyed epoch
        fails closed (forward secrecy, not a bug)."""
        self._require_unlocked()
        epoch = envelope.get("epoch")
        sender_fp = str(envelope.get("sender_fp", ""))
        seq = envelope.get("seq")
        if not isinstance(epoch, int) or not isinstance(seq, int):
            raise VeilChatError("bad envelope")
        path = self._msgkey_path(conv_id)
        if not path.exists():
            raise VeilChatError("no wrapped message keys for this conversation")
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if (
                int(entry.get("epoch", -1)) == epoch
                and entry.get("sender_fp") == sender_fp
                and int(entry.get("seq", -1)) == seq
            ):
                try:
                    msg_key = _open_backend(
                        self._epoch_key(conv_id, epoch),
                        _b64d(entry["sealed"]),
                        self._msgkey_aad(conv_id, epoch, sender_fp, seq),
                    )
                except VeilError as exc:
                    raise VeilChatError(
                        "wrapped message key unopenable (epoch destroyed?)"
                    ) from exc
                header = {
                    k: envelope[k]
                    for k in (
                        "protocol_version", "conv_id", "epoch",
                        "sender_fp", "seq", "sent_at",
                    )
                }
                try:
                    return _open_backend(
                        msg_key, _b64d(str(envelope["blob"])),
                        self._envelope_aad(header),
                    )
                except VeilError as exc:
                    raise VeilChatError(
                        "journal envelope authentication failed"
                    ) from exc
        raise VeilChatError("wrapped message key not found (epoch destroyed?)")

    # -- envelope journal (ciphertext only) --------------------------------------

    def _messages_path(self, conv_id: str) -> Path:
        _veil._sanitize(conv_id, "conv_id")
        d = self._home / _MESSAGES_DIR
        d.mkdir(exist_ok=True)
        return d / (conv_id + ".jsonl")

    def _store_envelope(self, conv_id: str, envelope: dict) -> None:
        path = self._messages_path(conv_id)
        with store_lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(envelope, sort_keys=True) + "\n")
            os.chmod(path, 0o600)

    def fetch_envelopes(self, conv_id: str) -> list:
        """Fetch the sealed envelope journal (still sealed — ciphertext
        only, re-openable via :meth:`open_journal_envelope` while the
        epoch lives)."""
        path = self._messages_path(conv_id)
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # -- conversations -----------------------------------------------------------

    def list_conversations(self) -> list[dict]:
        out = []
        d = self._home / _CONV_DIR
        if not d.exists():
            return out
        for path in sorted(d.glob("*.json")):
            try:
                conv = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            out.append(
                {
                    "conv_id": conv.get("conv_id"),
                    "peer_id": conv.get("peer_id"),
                    "epoch": conv.get("epoch"),
                    "send_seq": conv.get("send_seq"),
                    "recv_seq": conv.get("recv_seq"),
                }
            )
        return out

    def rotate_epoch(self, conv_id: str) -> dict:
        """Convenience: start a re-handshake (epoch rotation) for a live
        conversation. Returns the offer; feed the answer to
        :meth:`handshake_finish` as usual."""
        conv = self._read_conv(conv_id)
        return self.handshake_offer(conv["peer_id"], conv_id=conv_id)


def _zero(buf: bytearray) -> None:
    for i in range(len(buf)):
        buf[i] = 0


# ---------------------------------------------------------------------------
# Threat register + explicit non-claims
# ---------------------------------------------------------------------------

THREATS: list[dict[str, str]] = [
    {
        "id": "x25519-downgrade",
        "asset": "handshake key agreement",
        "attack": "attacker (or a broken environment) silently swaps the "
        "X25519 implementation for something weaker",
        "mitigation": "backend resolved once at import and reported by "
        "x25519_backend() and crypto_report(); no backend at all fails "
        "closed — handshakes raise instead of proceeding",
        "residual": "the pure-Python fallback is not constant-time "
        "(timing side channels); it is labeled fallback-grade",
        "status": "implemented",
    },
    {
        "id": "handshake-mitm",
        "asset": "conversation confidentiality (who holds the chain keys)",
        "attack": "active attacker substitutes their own ephemeral keys "
        "during the handshake, or forges offers/answers",
        "mitigation": "the chain root mixes ephemeral-ephemeral AND both "
        "static-ephemeral DHs (Noise-XX/X3DH pattern): the attacker cannot "
        "compute the static terms without a static private key. Offers and "
        "answers carry HMAC authenticators under the static-static DH, so "
        "forgeries fail closed before any key is derived. Identity "
        "fingerprints are still verified out of band via "
        "verify_peer_fingerprint().",
        "residual": "a keeper who skips the ceremony and registers an "
        "attacker's key trusts the attacker (TOFU) — the crypto cannot "
        "distinguish a registered attacker key from the real one",
        "status": "implemented",
    },
    {
        "id": "old-chain-key-seizure",
        "asset": "past message plaintext",
        "attack": "attacker seizes the device and recovers the current "
        "chain key, then tries to decrypt earlier messages",
        "mitigation": "the ratchet is one-way: each message derives "
        "msg_key then next_chain from the old chain and DESTROYS the old "
        "chain (memory zeroized, sealed copy overwritten). Past chain "
        "keys cannot be recomputed from the current one.",
        "residual": "wrapped message keys of the LIVE epochs remain "
        "sealed under epoch keys, which are sealed under the "
        "master-derived wrap key — a master-key compromise exposes live "
        "epochs; destroyed epochs stay dark",
        "status": "implemented",
    },
    {
        "id": "replay-reorder",
        "asset": "conversation ordering and freshness",
        "attack": "attacker re-injects or reorders sealed envelopes",
        "mitigation": "per-sender strictly increasing sequence numbers "
        "bound into the AAD; any gap or repeat fails closed",
        "residual": "out-of-order arrival fails closed rather than being "
        "buffered — the sender must re-send (documented limit, no DH "
        "ratchet in this build)",
        "status": "implemented",
    },
    {
        "id": "plaintext-on-disk",
        "asset": "message plaintext and key material at rest",
        "attack": "attacker reads the vault files from disk",
        "mitigation": "no plaintext message or key material is ever "
        "written: envelopes are sealed, chain state and epoch keys are "
        "sealed under the wrap key, message keys are sealed under epoch "
        "keys; owner-only files (0o600/0o700)",
        "residual": "metadata (peer ids, fingerprints, counters, "
        "timestamps) is plaintext — traffic-shape, not content",
        "status": "implemented",
    },
]

NON_CLAIMS: list[str] = [
    "No post-quantum resistance (X25519 is elliptic-curve).",
    "The pure-Python X25519 fallback is correct (RFC 7748 vectors) but "
    "not constant-time — timing side channels are a real residual; the "
    "cryptography package is the preferred backend and is always named "
    "in crypto_report().",
    "Forward secrecy is epoch- and chain-scoped, not absolute: destroyed "
    "epochs and old chain keys are dark, but the live epochs are sealed "
    "under a master-derived wrap key — a master-key compromise exposes "
    "them.",
    "No out-of-order tolerance: envelopes must arrive in sequence per "
    "sender; a gap fails closed and the message must be re-sent. (No DH "
    "ratchet in this build.)",
    "Identity keys are derived from the passphrase — a new passphrase is "
    "a new identity, and there is no identity portability in this build.",
    "No traffic-analysis resistance and no network transport in this "
    "module — envelopes are sealed bytes; delivery is the onion module's "
    "job (and that module is explicit about its own limits).",
]

#: The declared laws, machine-readable (L8: law→guard→prove — the laws
#: live in code, not just prose; verify_laws() and the invariant tests
#: check them at runtime).
LAWS = (
    ("L1", "No plaintext message or key material touches disk or wire — sealed envelopes and wrapped keys only."),
    ("L2", "Old chain keys and destroyed-epoch keys are unrecoverable (forward secrecy); nothing else is ever deleted."),
    ("L3", "Tampered envelopes, forged handshakes, replays, and out-of-order sequences fail closed."),
    ("L4", "The transport learns nothing: envelopes are opaque sealed bytes to any carrier."),
    ("L5", "The crypto backend is always reported honestly, never silently downgraded."),
    ("L6", "Keeper's law / anticipation: every refusal names its remedy; preconditions (locked stores, owner-only perms) are verified, not assumed."),
    ("L7", "Originals-first: registered peers are originals — never silently re-keyed; their fingerprints are integrity-checked."),
    ("L8", "Law->guard->prove: laws declared first, enforced by guards, machine-checked by invariant tests (honestly named, never 'formally proven')."),
    ("L9", "No-cancellation: no API removes another conversation, a peer with conversations, an envelope, or a relay descriptor."),
    ("L10", "Nothing-thrown-away: state only grows — journals append. The one exception is key destruction, which IS the forward-secrecy requirement and is documented as such."),
    ("L11", "Forward-motion: interrupted work is visible and resumable — pending handshakes are listed, never silently stuck."),
    ("L12", "Honesty over polish: crypto_report() states the real posture — backends, limits, non-claims, nothing implied."),
)


def check_invariants() -> list[tuple[str, bool, str]]:
    """Structural invariants the keeper can audit without reading crypto."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    required = ("id", "asset", "attack", "mitigation", "residual", "status")
    for threat in THREATS:
        missing = [k for k in required if not threat.get(k)]
        check(
            "threat %s is fully specified" % threat.get("id", "?"),
            not missing,
            ("missing: " + ", ".join(missing)) if missing else "ok",
        )
    check("every threat names its residual risk", all(t.get("residual") for t in THREATS))
    check("non-claims documented", len(NON_CLAIMS) >= 5, "%d" % len(NON_CLAIMS))
    check("protocol version pinned", _PROTOCOL_VERSION == 1, "v1")
    check(
        "x25519 backend is honestly one of the known labels",
        x25519_backend()
        in ("cryptography-x25519", "pure-python-fallback", "unavailable"),
        x25519_backend(),
    )
    # Directional chain derivation must separate the two directions.
    c1 = _hkdf(b"s" * 32, b"t" * 64, _INFO_CHAIN + b"A" + b"\x00" + b"B", 32)
    c2 = _hkdf(b"s" * 32, b"t" * 64, _INFO_CHAIN + b"B" + b"\x00" + b"A", 32)
    check("directional chains are independent", c1 != c2)
    # The ratchet must be one-way: next chain must differ from, and not
    # reveal, the previous chain.
    m1, n1 = VeilChat._chain_advance(b"c" * 32)
    check("ratchet advances (next != current)", n1 != b"c" * 32)
    check("message key differs from chain key", m1 != b"c" * 32 and m1 != n1)
    # Envelope header fields that MUST be AAD-bound.
    aad = VeilChat._envelope_aad(
        {
            "protocol_version": 1, "conv_id": "x", "epoch": 1,
            "sender_fp": "x", "seq": 1, "sent_at": "x",
        }
    )
    check(
        "envelope AAD binds conv, epoch, sender, seq",
        all(t in aad for t in (b'"conv_id"', b'"epoch"', b'"sender_fp"', b'"seq"')),
    )
    # Law->guard->prove: the laws are declared in code, with unique ids.
    law_ids = [lid for lid, _ in LAWS]
    check("laws declared (L1..L12)", len(law_ids) == 12, "%d" % len(law_ids))
    check("law ids unique", len(set(law_ids)) == len(law_ids))
    check(
        "every law has a statement",
        all(text and text.strip() for _, text in LAWS),
    )
    return results


__all__ = [
    "VeilChat",
    "VeilChatError",
    "LAWS",
    "THREATS",
    "NON_CLAIMS",
    "check_invariants",
    "x25519",
    "x25519_public",
    "x25519_backend",
]
