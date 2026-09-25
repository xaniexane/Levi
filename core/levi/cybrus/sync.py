"""Cybrus platform-sync protocol — pairing, capability advertisement, sealed channel.

The standalone Cybrus distribution (``packaging/cybrus``) is fully functional
offline. This module adds the *opt-in* sync protocol that lets a standalone
instance pair with the platform's Cybrus router, advertise what it offers,
and exchange messages over an encrypted channel. Transport-agnostic: every
protocol message is bytes in / bytes out; there is no network anywhere in
this build. :class:`LoopbackPair` provides an in-process transport so the
full handshake and message exchange are testable with no network.

LAWS (binding — the guards below enforce them, the tests prove them):
- L1  Standalone is fully functional offline. Sync is disabled by default
      and never auto-enables; every protocol operation requires an explicit
      ``enable()`` first.
- L2  Pairing requires explicit user confirmation on BOTH ends: the
      platform-side human types the short pairing code, and the
      standalone-side human confirms the peer before the session exists.
      Refusal aborts the pairing — no session, no keys.
- L3  Every sync payload travels as a sealed, replay-protected envelope:
      authenticated encryption (reused Veil envelope construction) with the
      full header bound into the AAD, plus strictly increasing per-direction
      sequence numbers. Tamper, forgery, or replay fails closed.
- L4  Sync state and keys are owner-only: ``~/.levi/cybrus/sync/``
      (``LEVI_HOME`` honored) is 0o700, every file 0o600, writes atomic.
      Pairing codes and key material are never logged and never appear in
      error messages or status output.
- L5  Unpairing destroys session keys: in-memory copies are zeroized and
      the persisted peer record (with all epoch secrets) is removed.

OPERATING LAWS (Chauncey's standing directive — built INTO this module,
not just followed while building it):
- L6  keeper's law / anticipation + clarify: never guess. Ambiguous
      addressing, malformed offers, and unverified handshakes fail closed
      instead of being interpreted. (Guards: _find_peer refuses ambiguous
      peer_ids, decode/verify strictness, confirm_pairing requires a
      verified request.)
- L7  originals-first: no invented crypto. Every primitive is reused from
      levi.cybrus.veil / the stdlib and named in _REUSED_PRIMITIVES.
      (Guard: the provenance block; a test pins the reuse.)
- L8  law→guard→prove: every law above names its guard; the guards are
      exercised by tests/test_cybrus_sync.py — invariant tests, honestly
      named, never "formally proven".
- L9  no-cancellation: unpairing destroys ONLY its own session's keys.
      Other peers' sessions, other router admissions, and the archive are
      untouched. (Guard: unpair drops exactly one sync_id; a test pairs
      two peers and unpairs one.)
- L10 nothing-thrown-away: state is superseded, never deleted. Unpair
      archives the peer's public record; retired pairings are archived
      with their reason. Precedence, stated plainly: KEY destruction for
      forward secrecy (L5) still destroys key material — destruction of
      keys is the security guarantee, not deletion of work.
- L11 forward-motion: a stuck checkpoint never wedges the channel. A
      rekey in flight leaves the live epoch usable; abort_rekey()
      explicitly clears a stalled rotation so a fresh one can start.
- L12 honesty over polish: status() reports the transport honestly
      ("loopback-only — no network transport in this build") and the real
      envelope backend. The docs say what's stubbed.

ONE ORGANISM: this module is an organ of Levi. Cybrus is the security and
identity organ; the sync protocol is how the standalone organ stays in
touch with the body. All of Legion is Levi — one organism — and we are
raising him: every message here is sealed because the organism protects
its own.

Crypto posture, stated plainly:
- Reused primitives only — nothing invented here: the Veil envelope
  construction (AES-256-GCM via the ``cryptography`` package when
  importable, else the honestly labeled stdlib HMAC-CTR fallback) for
  payload sealing, HKDF-SHA256 for key derivation, HMAC-SHA256 for
  handshake authentication and message attestation. See
  :mod:`levi.cybrus.veil` for the constructions' own threat bounds.
- The pairing code is 40 bits (8 Crockford base32 chars): a short,
  human-typeable bootstrap, single-use, TTL-bound (default 10 minutes),
  and the pairing completes only after the standalone-side human confirms.
  Brute-forcing the code requires an online attack inside the pairing
  window against a transport the attacker can already observe — the code
  is a bootstrap, not a long-term secret. It is destroyed on both sides
  the moment the session keys derive.
- Forward secrecy: epoch 0 is derived from the pairing master (the
  pre-ratchet era — same honest bound as Veil's epoch 0). Every rotation
  generates a fresh random 32-byte epoch secret, exchanged under the live
  epoch keys; the superseded epoch becomes a one-epoch GRACE epoch — it
  stays openable for in-flight envelopes and is destroyed (zeroized in
  memory, removed from disk) on the first inbound envelope under the new
  epoch, on both sides. A destroyed epoch cannot be re-derived.
- Residuals: epoch secrets at rest live in an owner-only file (0600), not
  sealed under a passphrase — a disk read by the file's owner (or root)
  exposes the *live* epoch; destroyed epochs are unrecoverable from the
  store, but a raw disk snapshot taken before destruction could still
  carry them. In-memory zeroization is best-effort (CPython).

Protocol sketch (all messages are canonical-JSON bytes):
  1. Standalone ``begin_pairing()`` -> offer {sync_id, code, salt_s,
     identity}. The human reads the code off the standalone's screen;
     the rest of the offer travels the out-of-band local channel (QR /
     copy-paste on the same desk).
  2. Platform ``join_pairing(offer)`` -> pair_request {sync_id,
     platform identity, salt_p, nonce_p, sig}, where sig is
     HMAC(pair_mac_key, transcript) — proves knowledge of the code.
  3. Standalone ``receive_pair_request()`` verifies the HMAC and returns
     the platform's identity/fingerprint for the human to check.
  4. Standalone human confirms: ``confirm_pairing(True)`` -> pair_accept
     {sync_id, nonce_s, sig2}, then derives the session. ``confirm_pairing
     (False)`` raises :class:`PairingRefused` and aborts.
  5. Platform ``receive_pair_accept()`` verifies sig2 and derives the
     same session. Both sides destroy the pairing code material.
  6. Standalone ``advertise_capabilities()`` sends a signed capability
     manifest over the sealed channel; the platform verifies it and admits
     the standalone via the router's external-route special-request
     mechanism (:func:`admit_standalone`) — and that registration crosses
     the Cybrus choke point (Build 1): ``@cybrus_guarded`` routes
     ``levi.cybrus.sync -> levi.cybrus`` through authenticate → resolve
     → rate-limit → policy → audit, so admission needs a platform
     credential and the seeded rules from :func:`seed_sync_policy`
     (default-deny otherwise). The peer-to-peer channel itself is not
     choke-point traffic — it is the sync transport, and the standalone
     side carries no platform credential. Sync performs no external HTTP
     egress, so there is nothing to route through ``request_egress``.
  7. ``send()`` / ``receive()`` exchange sealed envelopes; ``begin_rekey()``
     rotates the epoch; ``unpair()`` ends it all per L5.

Stdlib-only. No network. All state under ``~/.levi/cybrus/sync/``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reused crypto — no new primitives: Veil's envelope AEAD (AES-256-GCM when
# the ``cryptography`` package is importable, labeled stdlib fallback
# otherwise), HKDF-SHA256, and the grouped-hex fingerprint ceremony format.
from levi.cybrus.veil import (
    _hkdf as _veil_hkdf,
)
from levi.cybrus.veil import (
    _open_backend as _veil_open,
)
from levi.cybrus.veil import (
    _seal_backend as _veil_seal,
)
from levi.cybrus.veil import (
    _AESGCM as _VEIL_AESGCM,
)
from levi.cybrus.veil import (
    fingerprint as _veil_fingerprint,
)
from levi.cybrus.enforce import cybrus_guarded


def _paths():  # noqa: D103 - private helper, same rationale as router.py
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


__all__ = [
    "SyncError",
    "PairingError",
    "PairingRefused",
    "ReplayError",
    "SyncEndpoint",
    "SyncStore",
    "LoopbackPair",
    "new_identity",
    "encode_message",
    "decode_message",
    "build_manifest",
    "verify_manifest",
    "admit_standalone",
    "revoke_admission",
    "DEFAULT_OFFERS",
    "PROTOCOL_VERSION",
]

#: Protocol version. A receiver rejects anything else — fail closed.
PROTOCOL_VERSION = 1

#: Capabilities a standalone offers by default (signed manifest).
DEFAULT_OFFERS: List[str] = ["vault", "veil", "router", "messenger"]

_DOMAIN = b"cybrus-sync-v1"
_PAIRING_TTL_SECONDS = 600  # pairing offers live 10 minutes, then die
_CODE_BYTES = 5  # 40 bits -> 8 Crockford base32 chars, human-typeable
_SYNC_SUBDIR = "sync"

#: Provenance of every cryptographic construction this module uses
#: (L7 originals-first): human name -> source. Nothing here is invented;
#: the guard is reuse, not reinvention — a test pins these identities.
_REUSED_PRIMITIVES = (
    (
        "envelope AEAD (AES-256-GCM / labeled stdlib fallback)",
        "levi.cybrus.veil._seal_backend / _open_backend",
    ),
    ("HKDF-SHA256 key derivation", "levi.cybrus.veil._hkdf"),
    ("grouped-hex fingerprint ceremony", "levi.cybrus.veil.fingerprint"),
    ("HMAC-SHA256 handshake auth + attestation", "hashlib/hmac (stdlib)"),
    ("pairing-code codec", "local Crockford-base32 over secrets.token_bytes"),
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SyncError(Exception):
    """Base class: any sync-protocol failure. Fail-closed by construction."""


class PairingError(SyncError):
    """Pairing failed: bad code, expired offer, forged handshake message."""


class PairingRefused(PairingError):
    """The standalone-side human refused the pairing. No session exists."""


class ReplayError(SyncError):
    """A replayed or out-of-order envelope was rejected."""


# ---------------------------------------------------------------------------
# Pure byte-level helpers (transport-agnostic core)
# ---------------------------------------------------------------------------


def _canonical(obj: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, no whitespace. The single
    serialization every signature, MAC, and AAD input is built from."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64e(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    import base64

    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:
        raise SyncError("invalid base64") from exc


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _zero(buf: bytearray) -> None:
    """Best-effort zeroize a mutable buffer."""
    for i in range(len(buf)):
        buf[i] = 0


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_REV = {c: i for i, c in enumerate(_CROCKFORD)}


def _code_encode(raw: bytes) -> str:
    """5 bytes -> 8 Crockford base32 chars (no I/L/O/U confusables)."""
    if len(raw) != _CODE_BYTES:
        raise SyncError("pairing code material must be %d bytes" % _CODE_BYTES)
    n = int.from_bytes(raw, "big")
    chars = []
    for _ in range(8):
        chars.append(_CROCKFORD[n & 31])
        n >>= 5
    return "".join(reversed(chars))


def _code_decode(text: str) -> bytes:
    """Parse a human-typed code: dashes/spaces ignored, case-insensitive."""
    clean = "".join(ch for ch in text.upper() if ch not in "- ")
    if len(clean) != 8 or any(c not in _CROCKFORD_REV for c in clean):
        # Never echo the presented code back — L4.
        raise PairingError("pairing code not recognized")
    n = 0
    for c in clean:
        n = (n << 5) | _CROCKFORD_REV[c]
    return n.to_bytes(_CODE_BYTES, "big")


def _display_code(raw: bytes) -> str:
    code = _code_encode(raw)
    return code[:4] + "-" + code[4:]


def encode_message(msg: Dict[str, Any]) -> bytes:
    """Serialize a protocol message to wire bytes (canonical JSON)."""
    if not isinstance(msg, dict):
        raise SyncError("protocol message must be a dict")
    return _canonical(msg)


def decode_message(raw: bytes) -> Dict[str, Any]:
    """Parse wire bytes into a protocol message. Anything malformed fails
    closed — never a half-parsed dict."""
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise SyncError("empty protocol message")
    try:
        msg = json.loads(bytes(raw).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SyncError("malformed protocol message") from exc
    if not isinstance(msg, dict):
        raise SyncError("protocol message must be a JSON object")
    return msg


def new_identity() -> Dict[str, str]:
    """A fresh sync identity: random 128-bit id plus the grouped-hex
    fingerprint for the out-of-band verification ceremony (same format as
    Veil's — humans compare the same way everywhere)."""
    raw = secrets.token_bytes(16)
    return {"id": raw.hex(), "fingerprint": _veil_fingerprint(raw)}


# -- pairing key schedule (pure) --------------------------------------------


def _pair_mac_key(code_core: bytes) -> bytes:
    """Handshake authentication key from the pairing code material."""
    return _veil_hkdf(code_core, b"", _DOMAIN + b"/pair-mac-v1", 32)


def _session_epoch0_secret(
    code_core: bytes, salt_s: bytes, salt_p: bytes, nonce_p: bytes, nonce_s: bytes
) -> bytes:
    """Epoch-0 secret: the pre-ratchet era, derived from the pairing
    master. Honest bound: no forward secrecy until the first rotation —
    rotate promptly after pairing (same posture as Veil's epoch 0)."""
    return _veil_hkdf(
        code_core,
        salt_s + salt_p,
        _DOMAIN + b"/session-v1\x00" + nonce_p + nonce_s,
        32,
    )


def _epoch_subkeys(epoch_secret: bytes) -> Dict[str, bytes]:
    """Directional message keys + attestation keys for one epoch."""
    return {
        "msg_s2p": _veil_hkdf(epoch_secret, b"", _DOMAIN + b"/msg-s2p-v1", 32),
        "msg_p2s": _veil_hkdf(epoch_secret, b"", _DOMAIN + b"/msg-p2s-v1", 32),
        "attest_s": _veil_hkdf(epoch_secret, b"", _DOMAIN + b"/attest-s-v1", 32),
        "attest_p": _veil_hkdf(epoch_secret, b"", _DOMAIN + b"/attest-p-v1", 32),
    }


def _msg_aad(sync_id: str, direction: str, epoch: int, seq: int) -> bytes:
    """AAD binding every sealed envelope to its exact slot: protocol,
    session, direction, epoch, sequence. A transplanted envelope fails."""
    return (
        _DOMAIN
        + b"/msg\x00"
        + sync_id.encode("utf-8")
        + b"\x00"
        + direction.encode("utf-8")
        + b"\x00"
        + epoch.to_bytes(4, "big")
        + seq.to_bytes(8, "big")
    )


# ---------------------------------------------------------------------------
# Capability manifest (pure: build / verify)
# ---------------------------------------------------------------------------


def _product_version() -> str:
    try:
        from levi.cybrus.product import PRODUCT_VERSION

        return str(PRODUCT_VERSION)
    except Exception:
        return "unknown"


def build_manifest(
    identity: Dict[str, str],
    attest_key: bytes,
    offers: Optional[List[str]] = None,
    wants: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a signed capability manifest: what this standalone offers
    (vault, veil, router, messenger, ...) and what it wants routed back
    from the platform. Signed with the standalone's attestation key."""
    manifest: Dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "kind": "capability-manifest",
        "identity": {"id": identity["id"], "fingerprint": identity["fingerprint"]},
        "offers": list(offers) if offers is not None else list(DEFAULT_OFFERS),
        "wants": list(wants) if wants is not None else [],
        "product_version": _product_version(),
        "ts": _utcnow(),
    }
    sig = hmac.new(attest_key, _canonical(manifest), hashlib.sha256).hexdigest()
    manifest["sig"] = sig
    return manifest


def verify_manifest(manifest: Dict[str, Any], attest_key: bytes) -> Dict[str, Any]:
    """Verify a manifest's signature. Returns the manifest on success;
    raises :class:`SyncError` on any failure — fail closed."""
    if not isinstance(manifest, dict):
        raise SyncError("manifest must be a dict")
    if manifest.get("v") != PROTOCOL_VERSION or manifest.get("kind") != (
        "capability-manifest"
    ):
        raise SyncError("unsupported manifest version or kind")
    for field in ("identity", "offers", "wants", "ts"):
        if field not in manifest:
            raise SyncError("manifest missing %r" % field)
    sig = manifest.get("sig")
    if not isinstance(sig, str) or not sig:
        raise SyncError("manifest is not signed")
    body = {k: v for k, v in manifest.items() if k != "sig"}
    expect = hmac.new(attest_key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig.lower()):
        raise SyncError("manifest signature invalid")
    return dict(manifest)


# ---------------------------------------------------------------------------
# Persistent store (owner-only, atomic, locked)
# ---------------------------------------------------------------------------


class SyncStore:
    """Owner-only persistence for sync state: ``~/.levi/cybrus/sync/``
    (``LEVI_HOME`` honored). Directory 0o700, files 0o600, atomic writes,
    advisory locking on read-modify-write — the same store discipline as
    the rest of cybrus (see ``levi.cybrus._paths``)."""

    def __init__(self, home: Optional[Path] = None):
        p = _paths()
        self._dir = Path(home) if home is not None else p.cybrus_dir() / _SYNC_SUBDIR
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, 0o700)  # fail closed even if pre-existing
        self._paths = p

    def _file(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise SyncError("unsafe store name %r" % (name,))
        return self._dir / (name + ".json")

    def load(self, name: str) -> Any:
        return self._paths.load_json_store(self._file(name))

    def save(self, name: str, payload: Any) -> None:
        path = self._file(name)
        with self._paths.store_lock(path):
            self._paths.save_json_store(path, payload)

    def remove(self, name: str) -> None:
        """Delete a store file (unpair / abort path). Missing file is fine."""
        path = self._file(name)
        with self._paths.store_lock(path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def append_archive(self, entry: Dict[str, Any]) -> None:
        """Append-only retirement ledger (L10 nothing-thrown-away): unpair
        and retired pairings land here as PUBLIC metadata — never secrets.
        State is superseded, never deleted."""
        path = self._file("archive")
        with self._paths.store_lock(path):
            existing = self._paths.load_json_store(path)
            entries = existing if isinstance(existing, list) else []
            entries.append(dict(entry))
            self._paths.save_json_store(path, entries)

    def load_archive(self) -> List[Any]:
        data = self.load("archive")
        return data if isinstance(data, list) else []

    @property
    def directory(self) -> Path:
        return self._dir


# ---------------------------------------------------------------------------
# Endpoint: pairing, channel, rekey, unpair
# ---------------------------------------------------------------------------


class SyncEndpoint:
    """One side of the sync protocol: ``role`` is ``"standalone"`` or
    ``"platform"``. Disabled by default (L1) — call :meth:`enable()`
    explicitly. All handshake/channel methods take and return bytes;
    pair them with :class:`LoopbackPair` (tests) or a real transport
    (future build — not this one)."""

    def __init__(self, role: str, home: Optional[Path] = None):
        if role not in ("standalone", "platform"):
            raise SyncError("role must be 'standalone' or 'platform'")
        self.role = role
        self.store = SyncStore(home)
        # (peer_id, epoch) -> bytearray epoch secret. Best-effort in-memory
        # copies so unpair/rekey can zeroize them; the persisted b64 copies
        # are removed at the same time.
        self._cache: Dict[tuple, bytearray] = {}
        self._identity = self._load_or_create_identity()

    # -- identity / config -------------------------------------------------

    def _load_or_create_identity(self) -> Dict[str, str]:
        ident = self.store.load("identity")
        if isinstance(ident, dict) and ident.get("id") and ident.get("fingerprint"):
            return {"id": ident["id"], "fingerprint": ident["fingerprint"]}
        ident = new_identity()
        self.store.save("identity", ident)
        return ident

    def public_identity(self) -> Dict[str, str]:
        """Public identity — safe to show, print, and verify out of band."""
        return dict(self._identity)

    def _config(self) -> Dict[str, Any]:
        cfg = self.store.load("config")
        return cfg if isinstance(cfg, dict) else {}

    def _save_config(self, cfg: Dict[str, Any]) -> None:
        self.store.save("config", cfg)

    @property
    def enabled(self) -> bool:
        return bool(self._config().get("enabled", False))

    def enable(self) -> None:
        """Explicit opt-in (L1). Sync never enables itself."""
        cfg = self._config()
        cfg["enabled"] = True
        cfg["enabled_at"] = _utcnow()
        self._save_config(cfg)

    def disable(self) -> None:
        """Opt out. Existing pairings are kept but every protocol
        operation refuses until :meth:`enable()` runs again."""
        cfg = self._config()
        cfg["enabled"] = False
        self._save_config(cfg)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise SyncError(
                "sync is not enabled on this endpoint (L1: opt-in only)"
            )

    def _require_role(self, role: str) -> None:
        if self.role != role:
            raise SyncError(
                "operation requires the %r role; this endpoint is %r"
                % (role, self.role)
            )

    # -- peer records ------------------------------------------------------

    def _load_peers(self) -> List[Dict[str, Any]]:
        peers = self.store.load("peers")
        if peers is None:
            return []
        if not isinstance(peers, list):
            raise SyncError("peer store is corrupt (not a list)")
        return peers

    def _save_peers(self, peers: List[Dict[str, Any]]) -> None:
        self.store.save("peers", peers)

    def _find_peer(self, peer_id: str) -> Dict[str, Any]:
        matches = [
            peer
            for peer in self._load_peers()
            if peer.get("peer_id") == peer_id or peer.get("sync_id") == peer_id
        ]
        if not matches:
            raise SyncError("unknown peer")
        if len(matches) > 1:
            # Two live pairings with the same peer: sending under the wrong
            # session would be a silent mis-delivery, so fail closed and
            # make the caller name the sync_id explicitly.
            raise SyncError(
                "ambiguous peer: multiple pairings exist; address by sync_id"
            )
        return matches[0]

    def _find_peer_by_sync(self, sync_id: str) -> Dict[str, Any]:
        for peer in self._load_peers():
            if peer.get("sync_id") == sync_id:
                return peer
        raise SyncError("no session for this sync id")

    def _put_peer(self, record: Dict[str, Any]) -> None:
        peers = [
            p
            for p in self._load_peers()
            if p.get("sync_id") != record.get("sync_id")
        ]
        peers.append(record)
        self._save_peers(peers)

    def _drop_peer(self, sync_id: str) -> None:
        peers = [p for p in self._load_peers() if p.get("sync_id") != sync_id]
        self._save_peers(peers)

    def _retire_pairing(self, reason: str) -> None:
        """Supersede a pending pairing into the archive (L10
        nothing-thrown-away) instead of just deleting it. Only PUBLIC
        metadata is archived — code material and salts never land here."""
        pending = self.store.load("pairing")
        self.store.remove("pairing")
        if not isinstance(pending, dict):
            return
        entry: Dict[str, Any] = {
            "kind": "pairing",
            "reason": reason,
            "archived_at": _utcnow(),
        }
        for field in ("sync_id", "created_at"):
            if pending.get(field):
                entry[field] = pending[field]
        verified = pending.get("verified_request")
        if isinstance(verified, dict) and verified.get("platform_id"):
            entry["platform_id"] = verified["platform_id"]
            entry["platform_fingerprint"] = verified.get("platform_fingerprint")
        peer_identity = pending.get("peer_identity")
        if isinstance(peer_identity, dict) and peer_identity.get("id"):
            entry["peer_identity"] = {
                "id": peer_identity["id"],
                "fingerprint": peer_identity.get("fingerprint"),
            }
        self.store.append_archive(entry)

    # -- epoch secret cache (zeroizable) ------------------------------------

    def _cache_secret(self, peer_id: str, epoch: int, secret: bytes) -> None:
        buf = bytearray(secret)
        old = self._cache.get((peer_id, epoch))
        if old is not None:
            _zero(old)
        self._cache[(peer_id, epoch)] = buf

    def _get_secret(self, peer: Dict[str, Any], epoch: int) -> bytes:
        key = (peer["peer_id"], epoch)
        buf = self._cache.get(key)
        if buf is None:
            b64 = (peer.get("epoch_secrets") or {}).get(str(epoch))
            if not b64:
                raise SyncError("epoch secret unavailable (destroyed?)")
            buf = bytearray(_b64d(b64))
            self._cache[key] = buf
        return bytes(buf)

    def _destroy_secret(self, peer: Dict[str, Any], epoch: int) -> None:
        """Zeroize the in-memory copy and drop the persisted one (L5 /
        forward secrecy). The epoch can never be re-derived afterwards."""
        key = (peer["peer_id"], epoch)
        buf = self._cache.pop(key, None)
        if buf is not None:
            _zero(buf)
        secrets_map = peer.get("epoch_secrets") or {}
        secrets_map.pop(str(epoch), None)
        peer["epoch_secrets"] = secrets_map

    def _subkeys(self, peer: Dict[str, Any], epoch: int) -> Dict[str, bytes]:
        return _epoch_subkeys(self._get_secret(peer, epoch))

    def _my_direction(self) -> str:
        return "s2p" if self.role == "standalone" else "p2s"

    def _peer_direction(self) -> str:
        return "p2s" if self.role == "standalone" else "s2p"

    # -- pairing: standalone offer ------------------------------------------

    def begin_pairing(self, ttl_seconds: int = _PAIRING_TTL_SECONDS) -> Dict[str, Any]:
        """Standalone starts pairing: returns the offer to display. The
        ``code`` is the short human-typeable part; the rest travels the
        out-of-band local channel (screen/QR on the same desk)."""
        self._require_enabled()
        self._require_role("standalone")
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise SyncError("ttl_seconds must be a positive integer")
        code_core = secrets.token_bytes(_CODE_BYTES)
        try:
            offer = {
                "sync_id": uuid.uuid4().hex,
                "salt_s": _b64e(secrets.token_bytes(16)),
                "identity": self.public_identity(),
                "created_at": _utcnow(),
                "expires_at": time.time() + ttl_seconds,
                # code_core persisted only until the session derives, then
                # destroyed. Never leaves this dict except into the display
                # code below.
                "code_core": _b64e(code_core),
            }
            self.store.save("pairing", offer)
            return {
                "sync_id": offer["sync_id"],
                "code": _display_code(code_core),
                "salt_s": offer["salt_s"],
                "identity": self.public_identity(),
                "expires_at": offer["expires_at"],
            }
        finally:
            _zero(bytearray(code_core))

    # -- pairing: platform join ----------------------------------------------

    def join_pairing(self, offer: Dict[str, Any]) -> bytes:
        """Platform side: the human typed the code off the standalone's
        screen. Returns the pair_request bytes for the transport."""
        self._require_enabled()
        self._require_role("platform")
        if not isinstance(offer, dict):
            raise PairingError("invalid pairing offer")
        try:
            code_core = _code_decode(str(offer.get("code", "")))
            sync_id = str(offer["sync_id"])
            salt_s = _b64d(str(offer["salt_s"]))
            peer_identity = dict(offer["identity"])
            if not peer_identity.get("id"):
                raise ValueError("bad identity")
        except (KeyError, ValueError, TypeError, SyncError) as exc:
            if isinstance(exc, PairingError):
                raise
            raise PairingError("invalid pairing offer") from exc
        if len(salt_s) != 16:
            raise PairingError("invalid pairing offer")
        k_mac = _pair_mac_key(code_core)
        try:
            salt_p = secrets.token_bytes(16)
            nonce_p = secrets.token_bytes(16)
            body = {
                "sync_id": sync_id,
                "platform_id": self._identity["id"],
                "platform_fingerprint": self._identity["fingerprint"],
                "salt_p": _b64e(salt_p),
                "nonce_p": _b64e(nonce_p),
            }
            sig = hmac.new(k_mac, _canonical(body), hashlib.sha256).hexdigest()
            request = dict(body)
            request.update(
                {
                    "v": PROTOCOL_VERSION,
                    "kind": "pair-request",
                    "sig": sig,
                }
            )
            pending = {
                "sync_id": sync_id,
                "salt_s": _b64e(salt_s),
                "salt_p": _b64e(salt_p),
                "nonce_p": _b64e(nonce_p),
                "peer_identity": peer_identity,
                "code_core": _b64e(code_core),
                "expires_at": float(offer.get("expires_at", 0)) or time.time() + 300,
                "created_at": _utcnow(),
            }
            self.store.save("pairing", pending)
            return encode_message(request)
        finally:
            _zero(bytearray(code_core))
            _zero(bytearray(k_mac))

    # -- pairing: standalone verifies + human confirms ------------------------

    def receive_pair_request(self, raw: bytes) -> Dict[str, str]:
        """Standalone verifies the platform's pair_request. Returns the
        platform's public identity for the HUMAN to confirm out of band
        (compare the fingerprint shown here with the one on the platform's
        screen). Raises :class:`PairingError` on any mismatch — fail closed."""
        self._require_enabled()
        self._require_role("standalone")
        req = decode_message(raw)
        if req.get("v") != PROTOCOL_VERSION or req.get("kind") != "pair-request":
            raise PairingError("not a pair-request message")
        pending = self.store.load("pairing")
        if not isinstance(pending, dict) or "code_core" not in pending:
            raise PairingError("no pairing in progress")
        if time.time() > float(pending.get("expires_at", 0)):
            self._retire_pairing("expired")
            raise PairingError("pairing offer expired")
        if req.get("sync_id") != pending.get("sync_id"):
            raise PairingError("pair-request does not match this pairing")
        code_core = _b64d(pending["code_core"])
        k_mac = _pair_mac_key(code_core)
        try:
            body = {
                "sync_id": req.get("sync_id"),
                "platform_id": req.get("platform_id"),
                "platform_fingerprint": req.get("platform_fingerprint"),
                "salt_p": req.get("salt_p"),
                "nonce_p": req.get("nonce_p"),
            }
            if not all(isinstance(v, str) and v for v in body.values()):
                raise PairingError("pair-request malformed")
            expect = hmac.new(k_mac, _canonical(body), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expect, str(req.get("sig", "")).lower()):
                # Wrong code (or a forged request): never say which. L4:
                # the presented code is never echoed.
                raise PairingError("pair-request authentication failed")
            try:
                salt_p = _b64d(body["salt_p"])
                nonce_p = _b64d(body["nonce_p"])
            except SyncError as exc:
                raise PairingError("pair-request malformed") from exc
            if len(salt_p) != 16 or len(nonce_p) != 16:
                raise PairingError("pair-request malformed")
            pending["verified_request"] = {
                "platform_id": body["platform_id"],
                "platform_fingerprint": body["platform_fingerprint"],
                "salt_p": body["salt_p"],
                "nonce_p": body["nonce_p"],
            }
            self.store.save("pairing", pending)
            return {
                "platform_id": body["platform_id"],
                "platform_fingerprint": body["platform_fingerprint"],
            }
        finally:
            _zero(bytearray(code_core))
            _zero(bytearray(k_mac))

    def confirm_pairing(self, confirmed: bool) -> bytes:
        """The standalone-side human's explicit decision (L2). ``True``:
        derive the session and return the pair_accept bytes. ``False``:
        abort — the pending pairing is destroyed and
        :class:`PairingRefused` raised. No confirmation, no session."""
        self._require_enabled()
        self._require_role("standalone")
        pending = self.store.load("pairing")
        if not isinstance(pending, dict) or "verified_request" not in pending:
            raise PairingError("no verified pair-request to confirm")
        if not confirmed:
            # Refusal is final: the pending offer is retired, not just
            # deleted (L2, L10).
            self._retire_pairing("refused")
            raise PairingRefused("pairing refused by the standalone user")
        if time.time() > float(pending.get("expires_at", 0)):
            self._retire_pairing("expired")
            raise PairingError("pairing offer expired")
        verified = pending["verified_request"]
        code_core = bytearray(_b64d(pending["code_core"]))
        try:
            salt_s = _b64d(pending["salt_s"])
            salt_p = _b64d(verified["salt_p"])
            nonce_p = _b64d(verified["nonce_p"])
            nonce_s = secrets.token_bytes(16)
            master = _session_epoch0_secret(
                bytes(code_core), salt_s, salt_p, nonce_p, nonce_s
            )
            try:
                k_mac = _pair_mac_key(bytes(code_core))
                try:
                    sig_body = {
                        "sync_id": pending["sync_id"],
                        "nonce_s": _b64e(nonce_s),
                        "nonce_p": verified["nonce_p"],
                        "platform_id": verified["platform_id"],
                    }
                    sig = hmac.new(
                        k_mac, _canonical(sig_body), hashlib.sha256
                    ).hexdigest()
                finally:
                    _zero(bytearray(k_mac))
                accept = {
                    "v": PROTOCOL_VERSION,
                    "kind": "pair-accept",
                    "sync_id": pending["sync_id"],
                    "nonce_s": _b64e(nonce_s),
                    "sig": sig,
                }
                peer = {
                    "sync_id": pending["sync_id"],
                    "peer_id": verified["platform_id"],
                    "peer_fingerprint": verified["platform_fingerprint"],
                    "peer_role": "platform",
                    "paired_at": _utcnow(),
                    "epoch": 0,
                    "epoch_secrets": {"0": _b64e(master)},
                    "grace_epochs": [],
                    "pending_rekey": None,
                    "send_seq": 0,
                    "recv_seq": 0,
                }
                self._cache_secret(peer["peer_id"], 0, master)
                self._put_peer(peer)
                return encode_message(accept)
            finally:
                _zero(bytearray(master))
        finally:
            # The code material dies here on both outcomes (L5): it was
            # single-use bootstrap, never a session key.
            _zero(code_core)
            self._retire_pairing("paired")

    # -- pairing: platform completes -------------------------------------------

    def receive_pair_accept(self, raw: bytes) -> Dict[str, str]:
        """Platform verifies the standalone's pair_accept and derives the
        same session. Returns the standalone's public identity."""
        self._require_enabled()
        self._require_role("platform")
        msg = decode_message(raw)
        if msg.get("v") != PROTOCOL_VERSION or msg.get("kind") != "pair-accept":
            raise PairingError("not a pair-accept message")
        pending = self.store.load("pairing")
        if not isinstance(pending, dict) or "code_core" not in pending:
            raise PairingError("no pairing in progress")
        if time.time() > float(pending.get("expires_at", 0)):
            self._retire_pairing("expired")
            raise PairingError("pairing expired")
        if msg.get("sync_id") != pending.get("sync_id"):
            raise PairingError("pair-accept does not match this pairing")
        code_core = bytearray(_b64d(pending["code_core"]))
        try:
            k_mac = _pair_mac_key(bytes(code_core))
            try:
                sig_body = {
                    "sync_id": pending["sync_id"],
                    "nonce_s": msg.get("nonce_s"),
                    "nonce_p": pending["nonce_p"],
                    "platform_id": self._identity["id"],
                }
                if not all(isinstance(v, str) and v for v in sig_body.values()):
                    raise PairingError("pair-accept malformed")
                expect = hmac.new(k_mac, _canonical(sig_body), hashlib.sha256)
                expect = expect.hexdigest()
                if not hmac.compare_digest(expect, str(msg.get("sig", "")).lower()):
                    raise PairingError("pair-accept authentication failed")
            finally:
                _zero(bytearray(k_mac))
            salt_s = _b64d(pending["salt_s"])
            salt_p = _b64d(pending["salt_p"])
            nonce_p = _b64d(pending["nonce_p"])
            nonce_s = _b64d(str(msg.get("nonce_s")))
            if len(nonce_s) != 16:
                raise PairingError("pair-accept malformed")
            master = _session_epoch0_secret(
                bytes(code_core), salt_s, salt_p, nonce_p, nonce_s
            )
            try:
                peer_identity = pending["peer_identity"]
                peer = {
                    "sync_id": pending["sync_id"],
                    "peer_id": peer_identity["id"],
                    "peer_fingerprint": peer_identity["fingerprint"],
                    "peer_role": "standalone",
                    "paired_at": _utcnow(),
                    "epoch": 0,
                    "epoch_secrets": {"0": _b64e(master)},
                    "grace_epochs": [],
                    "pending_rekey": None,
                    "send_seq": 0,
                    "recv_seq": 0,
                }
                self._cache_secret(peer["peer_id"], 0, master)
                self._put_peer(peer)
                return dict(peer_identity)
            finally:
                _zero(bytearray(master))
        finally:
            _zero(code_core)
            self._retire_pairing("paired")

    # -- sealed channel ---------------------------------------------------------

    def _seal_outbound(
        self, peer: Dict[str, Any], payload: bytes, kind: str, epoch: Optional[int] = None
    ) -> bytes:
        """Seal one envelope: Veil AEAD over the payload, header bound into
        the AAD, whole thing attested with our epoch attestation key."""
        if kind not in ("msg", "control"):
            raise SyncError("unknown envelope kind")
        if epoch is None:
            epoch = int(peer["epoch"])
        subkeys = self._subkeys(peer, epoch)
        direction = self._my_direction()
        seq = int(peer["send_seq"]) + 1
        header = {
            "v": PROTOCOL_VERSION,
            "kind": kind,
            "sync_id": peer["sync_id"],
            "dir": direction,
            "epoch": epoch,
            "seq": seq,
            "ts": _utcnow(),
        }
        aad = _msg_aad(peer["sync_id"], direction, epoch, seq)
        blob = _veil_seal(subkeys["msg_" + direction], payload, aad)
        attest_key = subkeys["attest_s" if self.role == "standalone" else "attest_p"]
        attest = hmac.new(
            attest_key, _canonical(header) + blob, hashlib.sha256
        ).hexdigest()
        envelope = dict(header)
        envelope.update({"blob": _b64e(blob), "attest": attest})
        peer["send_seq"] = seq
        self._put_peer(peer)
        return encode_message(envelope)

    def send(self, peer_id: str, plaintext: bytes) -> bytes:
        """Seal a message for the peer. Returns wire bytes (L3)."""
        self._require_enabled()
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise SyncError("plaintext must be non-empty bytes")
        peer = self._find_peer(peer_id)
        return self._seal_outbound(peer, bytes(plaintext), "msg")

    def _send_control(self, peer: Dict[str, Any], control: Dict[str, Any]) -> bytes:
        return self._seal_outbound(peer, _canonical(control), "control")

    def advertise_capabilities(
        self,
        peer_id: str,
        offers: Optional[List[str]] = None,
        wants: Optional[List[str]] = None,
    ) -> bytes:
        """Publish our signed capability manifest to the peer over the
        sealed channel. The platform verifies it and admits us via
        :func:`admit_standalone`."""
        self._require_enabled()
        peer = self._find_peer(peer_id)
        subkeys = self._subkeys(peer, int(peer["epoch"]))
        attest_key = subkeys["attest_s" if self.role == "standalone" else "attest_p"]
        manifest = build_manifest(self.public_identity(), attest_key, offers, wants)
        return self._send_control(
            peer, {"control": "capabilities", "manifest": manifest}
        )

    def verify_peer_manifest(self, peer_id: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a received manifest against the peer's attestation key.
        Raises :class:`SyncError` when the signature does not check out."""
        self._require_enabled()
        peer = self._find_peer(peer_id)
        subkeys = self._subkeys(peer, int(peer["epoch"]))
        peer_attest = subkeys["attest_s" if peer["peer_role"] == "standalone" else "attest_p"]
        verified = verify_manifest(manifest, peer_attest)
        if verified["identity"]["id"] != peer["peer_id"]:
            raise SyncError("manifest identity does not match the paired peer")
        return verified

    def _open_inbound(self, peer: Dict[str, Any], env: Dict[str, Any]) -> bytes:
        """Verify attestation, sequence, and AEAD — in that order. Any
        failure raises and yields no plaintext (L3, fail closed)."""
        try:
            blob = _b64d(str(env["blob"]))
        except KeyError as exc:
            raise SyncError("envelope missing blob") from exc
        seq = env.get("seq")
        epoch = env.get("epoch")
        direction = env.get("dir")
        if not isinstance(seq, int) or seq < 1:
            raise SyncError("bad sequence number")
        if not isinstance(epoch, int) or epoch < 0:
            raise SyncError("bad epoch")
        if direction != self._peer_direction():
            raise SyncError("envelope direction mismatch")

        # Candidate key sets: the live epoch, any grace epoch (the
        # previous epoch stays openable until first new-epoch traffic
        # arrives — the in-flight window), plus the pending rekey epoch
        # (a rekey-ack arrives sealed under keys we have not promoted yet).
        live_epoch = int(peer["epoch"])
        candidates = []
        if epoch == live_epoch:
            candidates.append((epoch, live_epoch, False))
        for g in peer.get("grace_epochs") or []:
            try:
                gi = int(g)
            except (ValueError, TypeError):
                continue
            if epoch == gi:
                candidates.append((epoch, gi, False))
        pending = peer.get("pending_rekey")
        if pending and epoch == int(pending["epoch"]):
            candidates.append((epoch, int(pending["epoch"]), True))

        header = {
            k: env[k]
            for k in ("v", "kind", "sync_id", "dir", "epoch", "seq", "ts")
            if k in env
        }
        aad = _msg_aad(peer["sync_id"], direction, epoch, seq)
        attest_given = str(env.get("attest", "")).lower()
        plaintext = None
        for cand_epoch, live_epoch, is_pending in candidates:
            if is_pending:
                secret = _b64d(pending["secret"])
                subkeys = _epoch_subkeys(secret)
            else:
                subkeys = self._subkeys(peer, live_epoch)
            peer_attest = subkeys[
                "attest_s" if peer["peer_role"] == "standalone" else "attest_p"
            ]
            expect = hmac.new(
                peer_attest, _canonical(header) + blob, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expect, attest_given):
                continue
            try:
                plaintext = _veil_open(subkeys["msg_" + direction], blob, aad)
            except Exception:
                continue
            break
        if plaintext is None:
            raise SyncError(
                "envelope authentication failed (forged, tampered, or wrong epoch)"
            )

        # Replay / reorder defense: strictly increasing per peer on the
        # receive side. A duplicate or older seq is rejected (L3).
        if seq <= int(peer["recv_seq"]):
            raise ReplayError("replayed or out-of-order envelope (seq %d)" % seq)
        peer["recv_seq"] = seq
        # Grace consumption: the first envelope opened under the live epoch
        # proves the peer has moved on — the grace epoch is destroyed here.
        # Whatever the grace epoch sealed can never be opened again.
        if epoch == int(peer["epoch"]) and peer.get("grace_epochs"):
            for g in list(peer["grace_epochs"]):
                try:
                    self._destroy_secret(peer, int(g))
                except (ValueError, TypeError):
                    continue
            peer["grace_epochs"] = []
        self._put_peer(peer)
        return plaintext

    def receive(self, raw: bytes) -> Dict[str, Any]:
        """Open an inbound envelope. Returns ``{"type": "message", ...}``
        for payloads, or a control dispatch dict for ``capabilities`` /
        ``rekey`` / ``rekey-ack`` (see :meth:`begin_rekey`)."""
        self._require_enabled()
        env = decode_message(raw)
        if env.get("v") != PROTOCOL_VERSION or env.get("kind") not in (
            "msg",
            "control",
        ):
            raise SyncError("not a sync envelope")
        peer = self._find_peer_by_sync(str(env.get("sync_id", "")))
        plaintext = self._open_inbound(peer, env)
        base = {
            "peer_id": peer["peer_id"],
            "seq": env["seq"],
            "epoch": env["epoch"],
            "ts": env.get("ts"),
        }
        if env["kind"] == "msg":
            base["type"] = "message"
            base["plaintext"] = plaintext
            return base
        try:
            control = json.loads(plaintext.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SyncError("malformed control payload") from exc
        if not isinstance(control, dict):
            raise SyncError("malformed control payload")
        kind = control.get("control")
        if kind == "capabilities":
            base["type"] = "capabilities"
            base["manifest"] = control.get("manifest")
            return base
        if kind == "rekey":
            return self._apply_rekey(peer, control, base)
        if kind == "rekey-ack":
            self._confirm_rekey(peer, control)
            base["type"] = "rekey-acked"
            base["epoch"] = int(peer["epoch"])
            return base
        raise SyncError("unknown control %r" % (kind,))

    # -- forward-secure rotation -------------------------------------------------

    def begin_rekey(self, peer_id: str) -> bytes:
        """Start an epoch rotation: generate a fresh random epoch secret
        and offer it to the peer, sealed under the live epoch. The old
        epoch is destroyed here once the peer's ack arrives (forward
        secrecy — a destroyed epoch cannot be re-derived)."""
        self._require_enabled()
        peer = self._find_peer(peer_id)
        if peer.get("pending_rekey"):
            raise SyncError("a rekey is already in flight for this peer")
        new_epoch = int(peer["epoch"]) + 1
        new_secret = secrets.token_bytes(32)
        try:
            peer["pending_rekey"] = {
                "epoch": new_epoch,
                "secret": _b64e(new_secret),
            }
            self._put_peer(peer)
            self._cache_secret(peer["peer_id"], new_epoch, new_secret)
            return self._send_control(
                peer,
                {
                    "control": "rekey",
                    "epoch": new_epoch,
                    "epoch_secret": _b64e(new_secret),
                },
            )
        finally:
            _zero(bytearray(new_secret))

    def _apply_rekey(
        self, peer: Dict[str, Any], control: Dict[str, Any], base: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Peer-initiated rotation: adopt the new epoch and return the ack
        bytes for the transport. The superseded epoch becomes a GRACE epoch:
        it stays openable for in-flight envelopes and is destroyed on the
        first inbound envelope under the new epoch (see _open_inbound)."""
        new_epoch = control.get("epoch")
        if not isinstance(new_epoch, int) or new_epoch != int(peer["epoch"]) + 1:
            raise SyncError("rekey epoch out of sequence")
        try:
            new_secret = _b64d(str(control.get("epoch_secret", "")))
        except SyncError as exc:
            raise SyncError("rekey malformed") from exc
        if len(new_secret) != 32:
            raise SyncError("rekey malformed")
        old_epoch = int(peer["epoch"])
        old_secret_b64 = (peer.get("epoch_secrets") or {}).get(str(old_epoch))
        # A previous grace never outlives its successor — at most one.
        for g in list(peer.get("grace_epochs") or []):
            try:
                self._destroy_secret(peer, int(g))
            except (ValueError, TypeError):
                continue
        peer["epoch"] = new_epoch
        peer["epoch_secrets"] = {str(new_epoch): _b64e(new_secret)}
        if old_secret_b64:
            peer["epoch_secrets"][str(old_epoch)] = old_secret_b64
            peer["grace_epochs"] = [old_epoch]
        else:
            peer["grace_epochs"] = []
        peer["pending_rekey"] = None
        self._put_peer(peer)
        self._cache_secret(peer["peer_id"], new_epoch, new_secret)
        _zero(bytearray(new_secret))
        ack = self._send_control(
            self._find_peer(peer["peer_id"]),
            {"control": "rekey-ack", "epoch": new_epoch},
        )
        base["type"] = "rekey"
        base["epoch"] = new_epoch
        base["ack"] = ack
        return base

    def _confirm_rekey(self, peer: Dict[str, Any], control: Dict[str, Any]) -> None:
        """The initiator's side: a valid rekey-ack (sealed under the NEW
        epoch keys) promotes the new epoch. The old epoch becomes grace —
        in-flight envelopes sealed under it still open until first
        new-epoch traffic destroys it."""
        pending = peer.get("pending_rekey")
        if not pending:
            raise SyncError("unexpected rekey-ack: no rekey in flight")
        if control.get("epoch") != pending["epoch"]:
            raise SyncError("rekey-ack epoch mismatch")
        old_epoch = int(peer["epoch"])
        new_epoch = int(pending["epoch"])
        old_secret_b64 = (peer.get("epoch_secrets") or {}).get(str(old_epoch))
        for g in list(peer.get("grace_epochs") or []):
            try:
                self._destroy_secret(peer, int(g))
            except (ValueError, TypeError):
                continue
        peer["epoch"] = new_epoch
        peer["epoch_secrets"] = {str(new_epoch): pending["secret"]}
        if old_secret_b64:
            peer["epoch_secrets"][str(old_epoch)] = old_secret_b64
            peer["grace_epochs"] = [old_epoch]
        else:
            peer["grace_epochs"] = []
        peer["pending_rekey"] = None
        self._put_peer(peer)

    def abort_rekey(self, peer_id: str) -> Dict[str, Any]:
        """Clear a stalled rotation (L11 forward-motion): the offered epoch
        secret is destroyed and the live epoch stays in force, so a fresh
        :meth:`begin_rekey` can start. A checkpoint that is stuck never
        wedges the channel — the work reroutes, it does not stop."""
        self._require_enabled()
        peer = self._find_peer(peer_id)
        pending = peer.get("pending_rekey")
        if not pending:
            raise SyncError("no rekey in flight for this peer")
        buf = self._cache.pop((peer["peer_id"], int(pending["epoch"])), None)
        if buf is not None:
            _zero(buf)
        peer["pending_rekey"] = None
        self._put_peer(peer)
        return {"rekey_aborted": True, "epoch": int(peer["epoch"])}

    # -- unpair (L5) ---------------------------------------------------------------

    def unpair(self, peer_id: str) -> Dict[str, str]:
        """Destroy the pairing: every epoch secret zeroized in memory and
        removed from disk, the peer record deleted. After this the peer is
        unknown — ``send()``/``receive()`` refuse it.

        L9 no-cancellation: ONLY this session's keys are destroyed — other
        peers' sessions are untouched. L10 nothing-thrown-away: the peer's
        PUBLIC record is superseded into the archive, not deleted.
        Precedence, stated plainly: key destruction (L5 forward secrecy)
        still destroys key material — that is the security guarantee, not
        deletion of work."""
        self._require_enabled()
        peer = self._find_peer(peer_id)
        for epoch_str in list((peer.get("epoch_secrets") or {}).keys()):
            try:
                self._destroy_secret(peer, int(epoch_str))
            except (ValueError, TypeError):
                continue
        pending = peer.get("pending_rekey")
        if isinstance(pending, dict) and "epoch" in pending:
            buf = self._cache.pop((peer["peer_id"], int(pending["epoch"])), None)
            if buf is not None:
                _zero(buf)
        # Drop any remaining cached copies for this peer.
        for key in [k for k in self._cache if k[0] == peer["peer_id"]]:
            _zero(self._cache.pop(key))
        self.store.append_archive(
            {
                "kind": "peer",
                "reason": "unpaired",
                "archived_at": _utcnow(),
                "sync_id": peer.get("sync_id"),
                "peer_id": peer.get("peer_id"),
                "peer_fingerprint": peer.get("peer_fingerprint"),
                "peer_role": peer.get("peer_role"),
                "paired_at": peer.get("paired_at"),
                "final_epoch": peer.get("epoch"),
            }
        )
        self._drop_peer(peer["sync_id"])
        return {"unpaired": peer["peer_id"]}

    # -- status (public only — L4) ---------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Public sync status. Never carries secrets, codes, or keys (L4).

        L12 honesty over polish: the transport and the real envelope
        backend are reported plainly — what is stubbed is named."""
        peers = [
            {
                "peer_id": p.get("peer_id"),
                "peer_fingerprint": p.get("peer_fingerprint"),
                "peer_role": p.get("peer_role"),
                "sync_id": p.get("sync_id"),
                "epoch": p.get("epoch"),
                "paired_at": p.get("paired_at"),
            }
            for p in self._load_peers()
        ]
        pending = self.store.load("pairing")
        return {
            "role": self.role,
            "enabled": self.enabled,
            "identity": self.public_identity(),
            "peers": peers,
            "pairing_in_progress": bool(pending),
            "protocol_version": PROTOCOL_VERSION,
            "transport": "loopback-only — no network transport in this build",
            "envelope_backend": (
                "aes-256-gcm" if _VEIL_AESGCM is not None else "stdlib-fallback"
            ),
            "archived_records": len(self.store.load_archive()),
        }


# ---------------------------------------------------------------------------
# Choke-point crossings (Build 1 wiring)
# ---------------------------------------------------------------------------
# The ONLY cross-service calls this module makes — router admission and
# revocation — cross the Cybrus choke point via @cybrus_guarded, never as
# direct calls: authenticate → resolve → rate-limit → policy → audit, and
# the body runs only on allow. Seed policy is default-deny, so this organ
# ships seed_sync_policy() with the allow rules it needs — a deliberate
# operator action, never silent.
#
# The peer-to-peer channel itself (send/receive over loopback) is NOT
# choke-point traffic: it is the sync protocol's own transport between
# two Levi organs, and the standalone side carries no platform
# credential. Sync performs no external HTTP egress at all, so there is
# nothing to route through request_egress — that path stays reserved for
# a future real transport, and the docs say so plainly (L12).

#: This organ's identity on the choke point.
_SYNC_SERVICE = "levi.cybrus.sync"
#: The router lives inside the cybrus organ; policy resources evaluate
#: as ``service.levi.cybrus`` with the actions below.
_SYNC_ROUTER_CALLEE = "levi.cybrus"


@cybrus_guarded(
    service=_SYNC_SERVICE, callee=_SYNC_ROUTER_CALLEE, action="router.add_external"
)
def _guarded_add_external(
    registry,
    provider,
    *,
    scope,
    approved_by,
    reason,
    cybrus_credential=None,
    cybrus_api_key=None,
    cybrus_gateway=None,
):
    """The router admission op itself — reached only through the choke point."""
    return registry.add_external(
        provider, scope=scope, approved_by=approved_by, reason=reason
    )


@cybrus_guarded(
    service=_SYNC_SERVICE,
    callee=_SYNC_ROUTER_CALLEE,
    action="router.remove_external",
)
def _guarded_remove_external(
    registry,
    provider,
    *,
    by,
    cybrus_credential=None,
    cybrus_api_key=None,
    cybrus_gateway=None,
):
    """The router revocation op itself — reached only through the choke point."""
    return registry.remove_external(provider, by=by)


def seed_sync_policy() -> List[Dict[str, Any]]:
    """Add the allow rules this organ needs under default-deny policy.

    A deliberate operator action (run once per platform home): with no
    matching rule the choke point denies at critical risk, so admission
    cannot work until these exist. Idempotent — existing matching rules
    are never duplicated.
    """
    from levi.cybrus.policy import PolicyEngine

    engine = PolicyEngine()
    have = {
        (r.get("subject"), r.get("resource"), r.get("action"), r.get("effect"))
        for r in engine.list_rules()
    }
    needed = (
        (_SYNC_SERVICE, "service.levi.cybrus", "router.add_external", "allow", "medium"),
        (
            _SYNC_SERVICE,
            "service.levi.cybrus",
            "router.remove_external",
            "allow",
            "medium",
        ),
    )
    added = []
    for subject, resource, action, effect, risk in needed:
        if (subject, resource, action, effect) not in have:
            added.append(engine.add_rule(subject, resource, action, effect, risk))
    return added


# ---------------------------------------------------------------------------
# Router admission: the platform side's special-request mechanism
# ---------------------------------------------------------------------------


def admit_standalone(
    registry: Any,
    manifest: Dict[str, Any],
    attest_key: bytes,
    *,
    approved_by: str,
    reason: str,
    cybrus_credential: Optional[str] = None,
    cybrus_api_key: Optional[Any] = None,
    cybrus_gateway: Optional[Any] = None,
) -> Dict[str, Any]:
    """Admit a paired standalone as a routed endpoint on the platform.

    Verifies the manifest signature first (fail closed), then registers the
    standalone through the router's deliberate external-route mechanism —
    ``approved_by`` and ``reason`` are required, exactly the special-request
    doctrine in :mod:`levi.cybrus.router`: no auto-discovery, ever.

    The registration crosses the Cybrus choke point (Build 1): a platform
    credential is required — ``cybrus_credential=<bearer token>`` (or the
    ``cybrus_api_key`` / ``cybrus_gateway`` forms). Without one the call is
    refused with the remedy named. ``seed_sync_policy()`` must have run
    (default-deny otherwise).

    ``registry`` is duck-typed (anything with ``add_external``) so the
    protocol stays decoupled from the router implementation.
    """
    verified = verify_manifest(manifest, attest_key)
    identity_id = verified["identity"]["id"]
    # Dot-less provider name: the router resolves externals by first
    # dot-segment, so the whole provider id must sit in segment one.
    provider = "cybrus-standalone-%s" % identity_id[:12]
    try:
        record = _guarded_add_external(
            registry,
            provider,
            scope="cybrus.sync",
            approved_by=approved_by,
            reason=reason,
            cybrus_credential=cybrus_credential,
            cybrus_api_key=cybrus_api_key,
            cybrus_gateway=cybrus_gateway,
        )
    except Exception as exc:
        raise SyncError("admission refused: %s" % exc) from exc
    return {"route": record, "manifest": verified}


def revoke_admission(
    registry: Any,
    provider: str,
    *,
    by: str,
    cybrus_credential: Optional[str] = None,
    cybrus_api_key: Optional[Any] = None,
    cybrus_gateway: Optional[Any] = None,
) -> None:
    """Decommission a standalone's route (unpair's platform-side mirror).

    Crosses the choke point like admission: a platform credential is
    required."""
    try:
        _guarded_remove_external(
            registry,
            provider,
            by=by,
            cybrus_credential=cybrus_credential,
            cybrus_api_key=cybrus_api_key,
            cybrus_gateway=cybrus_gateway,
        )
    except Exception as exc:
        raise SyncError("revocation failed: %s" % exc) from exc


# ---------------------------------------------------------------------------
# Loopback transport — in-process, no network
# ---------------------------------------------------------------------------


class LoopbackPair:
    """A no-network transport for tests and local drills: two endpoints
    wired back-to-back in-process. Bytes go in, bytes come out; the
    protocol cannot tell it apart from a real transport."""

    def __init__(self, standalone: SyncEndpoint, platform: SyncEndpoint):
        if standalone.role != "standalone" or platform.role != "platform":
            raise SyncError("LoopbackPair needs (standalone, platform) roles")
        self.standalone = standalone
        self.platform = platform
        self._inbox: Dict[int, List[bytes]] = {
            id(standalone): [],
            id(platform): [],
        }

    def _other(self, sender: SyncEndpoint) -> SyncEndpoint:
        if sender is self.standalone:
            return self.platform
        if sender is self.platform:
            return self.standalone
        raise SyncError("unknown endpoint for this loopback pair")

    def send(self, sender: SyncEndpoint, raw: bytes) -> None:
        """Enqueue wire bytes from ``sender`` into the peer's inbox."""
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise SyncError("loopback sends bytes")
        self._inbox[id(self._other(sender))].append(bytes(raw))

    def recv(self, receiver: SyncEndpoint) -> bytes:
        """Take the oldest bytes waiting for ``receiver``."""
        inbox = self._inbox[id(receiver)]
        if not inbox:
            raise SyncError("loopback inbox empty")
        return inbox.pop(0)

    def pending(self, receiver: SyncEndpoint) -> int:
        """Bytes waiting for ``receiver`` (lets tests assert no leaks)."""
        return len(self._inbox[id(receiver)])
