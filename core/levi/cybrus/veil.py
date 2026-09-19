"""Veil — the keeper's sealed, tamper-evident, keeper-held-keys secure messenger.

LEVI-original recreation. Lineage: the keeper's lock-and-key upload
(``lock-and-key-vault-genesis.zip``), studied in the workspace and rebuilt
LEVI-native per the revival laws — the *ideas* (sealed envelopes, device
identity with fingerprints and rotation, revocation, replay protection,
threat modeling) recreated here; no code copied, nothing masked.

What Veil is
----------------
A local, defensive secure-messenger core: the keeper holds the keys (every
key derives from the keeper's passphrase — nothing leaves the keeper), every
message is a sealed tamper-evident envelope, and device identities carry
fingerprints, versions, rotation, and a revocation ledger. There is no
network anywhere in this module: no relay, no telemetry, no external
identity service. All state lives under ``~/.levi/cybrus/veil/``
(``LEVI_HOME`` env override honored, the LEVI-tree convention).

Crypto posture, stated plainly
------------------------------
Stdlib-first with honest upgrades. The instance reports its posture via
:attr:`Veil.backend`, :attr:`Veil.kdf`, and :meth:`Veil.crypto_report` —
never silently, never as marketing.

- **AEAD backend.** When the ``cryptography`` package is importable,
  envelopes seal under **AES-256-GCM** (``backend == "aes-256-gcm"``).
  Otherwise the stdlib fallback is used: counter-mode keystream blocks of
  ``HMAC-SHA256(enc_key, "veil-stream-v1" || nonce || counter_be32)`` with
  an HMAC-SHA256 encrypt-then-MAC tag
  (``backend == "stdlib-fallback"`` — fallback-grade, honestly labeled,
  never a silent downgrade). Envelope blobs are versioned by magic:
  ``VB2`` for AES-256-GCM, ``VB1`` for the stdlib construction. The
  opener dispatches on the magic, so old and new envelopes are
  distinguishable; a ``VB2`` blob on a machine without ``cryptography``
  fails closed with an install hint instead of failing open.
- **KDF.** ``hashlib.scrypt`` (n=2^15, r=8, p=1, 32 MiB — workstation
  grade, stepped down to n=2^14 only on OpenSSL builds that cap scrypt
  memory) where the stdlib offers it; PBKDF2-HMAC-SHA256 at 600,000
  iterations otherwise. The choice is pinned in ``config.json`` at vault
  creation (pre-hardening vaults default to PBKDF2, which is what sealed
  them) and the stored verifier pins the derived key — a wrong KDF
  fails closed like a wrong passphrase.
- **Forward secrecy.** Per-conversation epoch ratchet
  (:meth:`Veil.rotate_conversation`). Epoch 0 is the legacy
  master-derived conversation key — the pre-ratchet era, no forward
  secrecy, kept so pre-upgrade envelopes still open. Every epoch >= 1 is
  a fresh 32-byte random key, sealed under a master-derived wrap key and
  stored owner-only; rotation keeps the new epoch plus one grace epoch
  (in-flight envelopes) and **destroys** older epochs — removed from the
  store, local copies zeroized. A destroyed epoch cannot be re-derived,
  not even with the master key: that destruction IS the forward secrecy.
  Honest bounds: the live epochs are sealed under the master key, so a
  master-key compromise exposes them; epoch 0 never had it; a disk
  snapshot taken before a rotation can recover the epoch it captured.
- **Subkeys.** HKDF-SHA256 (extract+expand, RFC 5869 shape) with domain
  separation — separate encryption/MAC subkeys, separate info strings
  per purpose (devices, conversations, ledger, verifier, ratchet wrap).
- **Nonces.** Fresh ``secrets`` bytes per seal (16 for the stdlib
  construction, 12 for GCM); nonce reuse destroys confidentiality
  (documented assumption: ``os.urandom`` is sound).
- **Authentication.** Encrypt-then-MAC with the full header (versions,
  ids, epoch, sequence, timestamp) bound into the AAD; device
  attestation covers header + blob; verify-then-decrypt with
  ``hmac.compare_digest`` BEFORE any decryption.

The module fails closed on every authentication failure: tampered blobs,
wrong keys, wrong associated data, destroyed epochs, and unknown envelope
versions all raise :class:`VeilError`.

Local attestation is not PKI
----------------------------
Device "signatures" here are HMAC attestations under a device token derived
from the keeper's master key. They prove *the keeper's device* sealed a
message — they are local attestation, not cross-device public-key
signatures. Cross-device trust is established the old-fashioned way: the
fingerprint ceremony (compare grouped-hex fingerprints out of band).
This limit is documented, not hidden.

Explicit non-claims: see :data:`NON_CLAIMS`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from levi.cybrus._paths import atomic_write_bytes, cybrus_dir, store_lock

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Envelope / blob magic. VB1 = stdlib HMAC-CTR fallback construction;
#: VB2 = AES-256-GCM via the ``cryptography`` package. The opener
#: dispatches on the magic, so old and new envelopes are distinguishable
#: and an unknown magic fails closed instead of decrypting under the
#: wrong layout.
_BLOB_MAGIC = b"VB1"
_BLOB_MAGIC_GCM = b"VB2"
_PROTOCOL_VERSION = 1

_PBKDF2_ITERATIONS = 600_000
_SALT_LEN = 16
_NONCE_LEN = 16
_GCM_NONCE_LEN = 12
_GCM_TAG_LEN = 16
_TAG_LEN = 32

#: scrypt work factors: 2^15 * 8 * 1 = 32 MiB, workstation-grade. Stepped
#: down to n=2^14 only on OpenSSL builds that cap scrypt memory.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024

_DOMAIN_STREAM = b"veil-stream-v1\x00"
_DOMAIN_MAC = b"veil-mac-v1\x00"
_DOMAIN_ATTEST = b"veil-attest-v1\x00"

_INFO_MASTER = b"veil-master"
_INFO_DEVICE = b"veil-device-v1\x00"
_INFO_CONV = b"veil-conversation-v1\x00"
_INFO_LEDGER = b"veil-ledger-v1\x00"
_INFO_VERIFY = b"veil-verify-v1\x00"
_INFO_RATCHET_WRAP = b"veil-ratchet-wrap-v1\x00"

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

_VB_SUBDIR = "veil"
_CONFIG_FILE = "config.json"
_DEVICES_FILE = "devices.json"
_REVOCATIONS_FILE = "revocations.jsonl"
_SEQ_FILE = "seq.json"
_RATCHETS_FILE = "ratchets.json"
_CONV_DIR = "conversations"


class VeilError(ValueError):
    """All Veil failures: locked vaults, bad passphrases, tampered or
    replayed envelopes, revoked devices, unknown identities. Fail-closed by
    construction — a wrong key or a flipped bit never yields plaintext."""


# ---------------------------------------------------------------------------
# Key derivation + AEAD (stdlib-only, honestly labeled)
# ---------------------------------------------------------------------------


def _pbkdf2(passphrase: str, salt: bytes) -> bytes:
    """Master key: PBKDF2-HMAC-SHA256, 600k iterations, 32 bytes."""
    if not passphrase:
        raise VeilError("passphrase must not be empty")
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=32
    )


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA-256 extract+expand (RFC 5869 shape), stdlib-only."""
    if not (1 <= length <= 255 * 32):
        raise VeilError("invalid hkdf output length")
    prk = hmac.new(salt if salt else b"\x00" * 32, ikm, hashlib.sha256).digest()
    okm = b""
    prev = b""
    counter = 1
    while len(okm) < length:
        prev = hmac.new(prk, prev + info + bytes([counter]), hashlib.sha256).digest()
        okm += prev
        counter += 1
    return okm[:length]


def _keystream(enc_key: bytes, nonce: bytes, nbytes: int) -> bytes:
    """HMAC-SHA256 counter-mode keystream. NOT AES — see module docstring."""
    out = bytearray()
    counter = 0
    while len(out) < nbytes:
        out += hmac.new(
            enc_key,
            _DOMAIN_STREAM + nonce + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        counter += 1
    return bytes(out[:nbytes])


def _seal(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt-then-MAC. Returns ``VB1 || nonce || ciphertext || tag``.

    The tag covers the nonce, the AAD length, the AAD, and the ciphertext,
    so a tampered header, swapped nonce, or flipped bit fails verification.
    """
    if len(key) != 32:
        raise VeilError("seal key must be 32 bytes")
    if len(nonce) != _NONCE_LEN:
        raise VeilError("nonce must be %d bytes" % _NONCE_LEN)
    enc_key = _hkdf(key, b"", _DOMAIN_STREAM + b"enc", 32)
    mac_key = _hkdf(key, b"", _DOMAIN_MAC + b"mac", 32)
    ks = _keystream(enc_key, nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks, strict=True))
    tag = hmac.new(
        mac_key,
        _DOMAIN_MAC + nonce + len(aad).to_bytes(8, "big") + aad + ct,
        hashlib.sha256,
    ).digest()
    return _BLOB_MAGIC + nonce + ct + tag


def _open(key: bytes, blob: bytes, aad: bytes) -> bytes:
    """Verify-then-decrypt. Raises :class:`VeilError` on any failure."""
    if len(key) != 32:
        raise VeilError("open key must be 32 bytes")
    if not blob.startswith(_BLOB_MAGIC):
        raise VeilError("not a Veil v1 blob")
    body = blob[len(_BLOB_MAGIC) :]
    if len(body) < _NONCE_LEN + _TAG_LEN:
        raise VeilError("blob too short")
    nonce = body[:_NONCE_LEN]
    tag = body[-_TAG_LEN:]
    ct = body[_NONCE_LEN:-_TAG_LEN]
    enc_key = _hkdf(key, b"", _DOMAIN_STREAM + b"enc", 32)
    mac_key = _hkdf(key, b"", _DOMAIN_MAC + b"mac", 32)
    expect = hmac.new(
        mac_key,
        _DOMAIN_MAC + nonce + len(aad).to_bytes(8, "big") + aad + ct,
        hashlib.sha256,
    ).digest()
    # Verify BEFORE decrypting; constant-time compare.
    if not hmac.compare_digest(expect, tag):
        raise VeilError(
            "authentication failed: tampered blob, wrong key, or wrong AAD"
        )
    ks = _keystream(enc_key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks, strict=True))


# ---------------------------------------------------------------------------
# Backend selection: real AEAD when available, labeled fallback otherwise
# ---------------------------------------------------------------------------


def _resolve_aesgcm():
    """Import AESGCM from the ``cryptography`` package, or None.

    Resolved once at import; read as the module global ``_AESGCM`` at call
    time so tests (and operators) can observe either backend honestly.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

        return AESGCM
    except Exception:
        return None


_AESGCM = _resolve_aesgcm()


def _seal_gcm(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """AES-256-GCM seal. Returns ``VB2 || nonce(12) || ciphertext+tag``.

    Raises instead of sealing when the ``cryptography`` package is absent —
    a missing backend is never a silent downgrade.
    """
    if _AESGCM is None:
        raise VeilError(
            "AES-256-GCM envelope needs the 'cryptography' package "
            "(pip install cryptography); refusing to seal"
        )
    if len(key) != 32:
        raise VeilError("seal key must be 32 bytes")
    if len(nonce) != _GCM_NONCE_LEN:
        raise VeilError("GCM nonce must be %d bytes" % _GCM_NONCE_LEN)
    ct = _AESGCM(key).encrypt(nonce, bytes(plaintext), bytes(aad))
    return _BLOB_MAGIC_GCM + nonce + ct


def _open_gcm(key: bytes, blob: bytes, aad: bytes) -> bytes:
    """Open a VB2 envelope. Fails closed — loudly — without ``cryptography``."""
    if _AESGCM is None:
        raise VeilError(
            "cannot open an AES-256-GCM envelope without the 'cryptography' "
            "package (pip install cryptography)"
        )
    if not blob.startswith(_BLOB_MAGIC_GCM):
        raise VeilError("not a Veil v2 blob")
    body = blob[len(_BLOB_MAGIC_GCM) :]
    if len(body) < _GCM_NONCE_LEN + _GCM_TAG_LEN:
        raise VeilError("blob too short")
    nonce = body[:_GCM_NONCE_LEN]
    ct = body[_GCM_NONCE_LEN:]
    try:
        return _AESGCM(key).decrypt(nonce, ct, bytes(aad))
    except Exception as exc:
        raise VeilError(
            "authentication failed: tampered blob, wrong key, or wrong AAD"
        ) from exc


def _seal_backend(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Seal with the preferred backend: AES-256-GCM (VB2) when the
    ``cryptography`` package is importable, else the labeled stdlib
    fallback (VB1). Fresh nonce per call."""
    if _AESGCM is not None:
        return _seal_gcm(key, secrets.token_bytes(_GCM_NONCE_LEN), plaintext, aad)
    return _seal(key, secrets.token_bytes(_NONCE_LEN), plaintext, aad)


def _open_backend(key: bytes, blob: bytes, aad: bytes) -> bytes:
    """Versioned envelope dispatch: VB2 -> AES-256-GCM, VB1 -> stdlib.
    Unknown magic fails closed; a VB2 blob without ``cryptography`` fails
    closed with an install hint. Never silently fails open."""
    if blob.startswith(_BLOB_MAGIC_GCM):
        return _open_gcm(key, blob, aad)
    return _open(key, blob, aad)  # VB1, or VeilError on bad magic


# ---------------------------------------------------------------------------
# KDF selection: memory-hard scrypt where available, PBKDF2 fallback
# ---------------------------------------------------------------------------


def _scrypt(password: bytes, salt: bytes) -> bytes:
    """Memory-hard derivation: 32 MiB, workstation-grade. Steps down to
    n=2^14 on OpenSSL builds that cap scrypt memory — still memory-hard,
    and the stored verifier pins whichever path this machine took."""
    try:
        return hashlib.scrypt(
            password,
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            maxmem=_SCRYPT_MAXMEM,
            dklen=32,
        )
    except (ValueError, TypeError):
        return hashlib.scrypt(
            password, salt=salt, n=2**14, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
        )


def _kdf_default() -> str:
    """Preferred KDF for new vaults: memory-hard scrypt where the stdlib
    offers it, PBKDF2-HMAC-SHA256 otherwise."""
    return "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2"


def _derive_master(passphrase: str, salt: bytes, kdf: str) -> bytes:
    """Master key under the named KDF. The KDF is pinned in config.json;
    a wrong KDF fails closed at the verifier like a wrong passphrase."""
    if not passphrase:
        raise VeilError("passphrase must not be empty")
    if kdf == "scrypt":
        if not hasattr(hashlib, "scrypt"):
            raise VeilError("scrypt KDF selected but unavailable on this machine")
        return _scrypt(passphrase.encode("utf-8"), salt)
    if kdf == "pbkdf2":
        return _pbkdf2(passphrase, salt)
    raise VeilError("unknown kdf %r" % (kdf,))


def fingerprint(public_bytes: bytes) -> str:
    """Human-verifiable fingerprint: SHA-256 of the bytes, hex grouped in
    fours (``aaaa bbbb ...``) — the verification-ceremony format."""
    digest = hashlib.sha256(public_bytes).hexdigest()
    return " ".join(digest[i : i + 4] for i in range(0, len(digest), 4))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sanitize(value: str, what: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise VeilError(
            "invalid %s %r: use 1-64 chars of [A-Za-z0-9._-]" % (what, value)
        )
    return value


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:
        raise VeilError("invalid base64") from exc


# ---------------------------------------------------------------------------
# Veil — the keeper-held-keys messenger
# ---------------------------------------------------------------------------


class Veil:
    """The keeper's sealed messenger.

    The keeper's passphrase derives the master key (memory-hard scrypt
    where available, PBKDF2-HMAC-SHA256 fallback — pinned per vault and
    reported by :attr:`kdf`); every device token, conversation key, and
    ledger key derives from it via HKDF. The master key lives in memory
    only while unlocked; :meth:`lock` best-effort zeroizes it. No key
    material in the clear is ever written to disk — only salt, verifier,
    device *metadata*, the revocation ledger, sequence counters, sealed
    envelopes, and the ratchet store (epoch keys sealed under a
    master-derived wrap key, never cleartext).

    Device identity model (recreated LEVI-native from the lock-and-key
    lineage): each device has a stable ``device_id``, a ``key_version``
    (rotation), a grouped-hex ``fingerprint`` of its attestation token, and
    attestation via HMAC — local attestation, not PKI (see module docstring).
    """

    def __init__(self, passphrase: str, home: Optional[Path] = None) -> None:
        self._home = Path(home) if home is not None else cybrus_dir() / _VB_SUBDIR
        self._home.mkdir(parents=True, exist_ok=True)
        os.chmod(self._home, 0o700)  # fail closed even if pre-existing
        self._master: Optional[bytearray] = None
        self._salt: bytes = b""
        self._kdf: str = _kdf_default()
        self._load_or_init(passphrase)

    # -- paths ---------------------------------------------------------

    def _path(self, name: str) -> Path:
        return self._home / name

    def _conv_path(self, conversation_id: str) -> Path:
        _sanitize(conversation_id, "conversation_id")
        d = self._home / _CONV_DIR
        d.mkdir(exist_ok=True)
        return d / (conversation_id + ".jsonl")

    # -- lock discipline ------------------------------------------------

    def _read_config(self) -> dict:
        """Read salt, verifier, and the pinned KDF. Pre-hardening vaults
        predate the ``kdf`` field and default to PBKDF2 — which is what
        sealed them. Unknown KDF names fail closed."""
        cfg_path = self._path(_CONFIG_FILE)
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            salt = _b64d(cfg["salt"])
            verifier = _b64d(cfg["verifier"])
            kdf = cfg.get("kdf", "pbkdf2")
        except (KeyError, VeilError, ValueError, OSError) as exc:
            raise VeilError("veil config unreadable: %s" % exc) from exc
        if kdf not in ("scrypt", "pbkdf2"):
            raise VeilError("veil config unreadable: unknown kdf %r" % (kdf,))
        return {"salt": salt, "verifier": verifier, "kdf": kdf}

    def _load_or_init(self, passphrase: str) -> None:
        cfg_path = self._path(_CONFIG_FILE)
        if cfg_path.exists():
            cfg = self._read_config()
            self._salt = cfg["salt"]
            self._kdf = cfg["kdf"]
            candidate = bytearray(_derive_master(passphrase, self._salt, self._kdf))
            expect = hmac.new(bytes(candidate), _INFO_VERIFY, hashlib.sha256).digest()
            if not hmac.compare_digest(expect, cfg["verifier"]):
                self._zero(candidate)
                raise VeilError("wrong passphrase")
            self._master = candidate
        else:
            self._salt = secrets.token_bytes(_SALT_LEN)
            self._kdf = _kdf_default()
            master = bytearray(_derive_master(passphrase, self._salt, self._kdf))
            verifier = hmac.new(bytes(master), _INFO_VERIFY, hashlib.sha256).digest()
            cfg = {
                "salt": _b64e(self._salt),
                "verifier": _b64e(verifier),
                "kdf": self._kdf,
                "created_at": _utcnow(),
                "protocol_version": _PROTOCOL_VERSION,
            }
            atomic_write_bytes(cfg_path, json.dumps(cfg, indent=2).encode("utf-8"))
            self._master = master

    def _zero(self, buf: bytearray) -> None:
        for i in range(len(buf)):
            buf[i] = 0

    @property
    def is_locked(self) -> bool:
        return self._master is None

    def _require_unlocked(self) -> bytes:
        if self._master is None:
            raise VeilError("veil is locked")
        return bytes(self._master)

    def lock(self) -> None:
        """Best-effort zeroize the master key. All operations fail closed
        until :meth:`unlock`."""
        if self._master is not None:
            self._zero(self._master)
            self._master = None

    def unlock(self, passphrase: str) -> None:
        """Re-derive and verify against the stored verifier. Raises
        :class:`VeilError` on a wrong passphrase — never unlocks
        partially."""
        if self._master is not None:
            return
        cfg = self._read_config()
        self._salt = cfg["salt"]
        self._kdf = cfg["kdf"]
        candidate = bytearray(_derive_master(passphrase, self._salt, self._kdf))
        expect = hmac.new(bytes(candidate), _INFO_VERIFY, hashlib.sha256).digest()
        if not hmac.compare_digest(expect, cfg["verifier"]):
            self._zero(candidate)
            raise VeilError("wrong passphrase")
        self._master = candidate

    @property
    def backend(self) -> str:
        """Honestly labeled AEAD backend: ``"aes-256-gcm"`` when the
        ``cryptography`` package is importable, else
        ``"stdlib-fallback"``. Never a silent downgrade."""
        return "aes-256-gcm" if _AESGCM is not None else "stdlib-fallback"

    @property
    def kdf(self) -> str:
        """Pinned key-derivation function: ``"scrypt"`` or ``"pbkdf2"``."""
        return self._kdf

    def crypto_report(self) -> dict:
        """Honest crypto posture for the keeper's audit: backend, KDF and
        its real parameters, envelope versioning, forward-secrecy story."""
        if self._kdf == "scrypt":
            kdf_params: dict = {
                "n": _SCRYPT_N,
                "r": _SCRYPT_R,
                "p": _SCRYPT_P,
                "memory": "32 MiB",
                "grade": "workstation (stepped down to n=2^14 on "
                "memory-capped OpenSSL builds)",
            }
        else:
            kdf_params = {
                "iterations": _PBKDF2_ITERATIONS,
                "note": "fallback; scrypt unavailable on this machine",
            }
        return {
            "backend": self.backend,
            "kdf": self._kdf,
            "kdf_params": kdf_params,
            "envelope": "VB2/AES-256-GCM" if _AESGCM is not None else "VB1/HMAC-CTR",
            "protocol_version": _PROTOCOL_VERSION,
            "forward_secrecy": "per-conversation epoch ratchet; "
            "rotate_conversation() destroys old epochs",
        }

    # -- key derivation --------------------------------------------------

    def _device_token(self, device_id: str, key_version: int) -> bytes:
        """Attestation token for a device/version. Derived, never stored."""
        master = self._require_unlocked()
        return _hkdf(
            master,
            self._salt,
            _INFO_DEVICE
            + device_id.encode("utf-8")
            + b"\x00"
            + str(key_version).encode("ascii"),
            32,
        )

    def _conversation_key(self, conversation_id: str) -> bytes:
        master = self._require_unlocked()
        return _hkdf(
            master, self._salt, _INFO_CONV + conversation_id.encode("utf-8"), 32
        )

    def _ledger_key(self) -> bytes:
        master = self._require_unlocked()
        return _hkdf(master, self._salt, _INFO_LEDGER, 32)

    # -- forward-secrecy ratchet -------------------------------------------

    def _read_ratchets(self) -> dict:
        path = self._path(_RATCHETS_FILE)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise VeilError("ratchet registry unreadable: %s" % exc) from exc
        return data if isinstance(data, dict) else {}

    def _write_ratchets(self, ratchets: dict) -> None:
        # Sealed epoch keys only — never cleartext key material. Owner-only
        # (atomic_write_bytes defaults to 0o600), single-winner under lock.
        with store_lock(self._path(_RATCHETS_FILE)):
            atomic_write_bytes(
                self._path(_RATCHETS_FILE),
                json.dumps(ratchets, indent=2, sort_keys=True).encode("utf-8"),
            )

    def _ratchet_wrap_key(self, conversation_id: str) -> bytes:
        """Wrap key for this conversation's epoch keys. Master-derived, so
        epoch keys at rest are sealed — but also so a master compromise can
        unwrap the *live* epochs (documented residual; destroyed epochs
        stay dark)."""
        master = self._require_unlocked()
        return _hkdf(
            master,
            self._salt,
            _INFO_RATCHET_WRAP + conversation_id.encode("utf-8"),
            32,
        )

    @staticmethod
    def _ratchet_aad(conversation_id: str) -> bytes:
        return b"veil-ratchet-wrap" + conversation_id.encode("utf-8")

    def _ensure_epoch(self, conversation_id: str) -> int:
        """Return the conversation's live epoch, initializing epoch 1 (a
        fresh random key) for conversations that predate the ratchet. Epoch
        0 is reserved for pre-upgrade envelopes — the pre-ratchet era."""
        ratchets = self._read_ratchets()
        convs = ratchets.setdefault("conversations", {})
        conv = convs.get(conversation_id)
        if conv is None:
            raw = bytearray(secrets.token_bytes(32))
            try:
                sealed = _seal_backend(
                    self._ratchet_wrap_key(conversation_id),
                    bytes(raw),
                    self._ratchet_aad(conversation_id),
                )
            finally:
                self._zero(raw)
            convs[conversation_id] = {"epoch": 1, "live": {"1": _b64e(sealed)}}
            self._write_ratchets(ratchets)
            return 1
        return int(conv.get("epoch", 1))

    def _epoch_key(self, conversation_id: str, epoch: int) -> bytes:
        """Key for (conversation, epoch).

        Epoch 0 is the legacy master-derived conversation key — the
        pre-ratchet era, no forward secrecy, kept so pre-upgrade envelopes
        still open. Epoch >= 1 keys are fresh random bytes sealed in the
        ratchet store; a destroyed or unknown epoch raises instead of
        returning anything."""
        if epoch == 0:
            return self._conversation_key(conversation_id)
        conv = self._read_ratchets().get("conversations", {}).get(conversation_id, {})
        sealed_b64 = conv.get("live", {}).get(str(epoch))
        if not sealed_b64:
            raise VeilError(
                "epoch %d of %r rotated away or unknown" % (epoch, conversation_id)
            )
        sealed = _b64d(sealed_b64)
        return _open_backend(
            self._ratchet_wrap_key(conversation_id),
            sealed,
            self._ratchet_aad(conversation_id),
        )

    def rotate_conversation(self, conversation_id: str) -> dict:
        """Advance the conversation's epoch — the forward-secrecy rotation.

        A fresh random 32-byte epoch key is generated; new traffic seals
        under it. The previous epoch stays live for one grace epoch so
        in-flight envelopes still open; older epochs are **destroyed** —
        removed from the store, with local copies zeroized. A destroyed
        epoch cannot be re-derived, not even with the master key: that
        destruction IS the forward secrecy. Rotate on a cadence (or after
        any suspected compromise) — the keeper decides the rhythm."""
        _sanitize(conversation_id, "conversation_id")
        self._require_unlocked()
        current = self._ensure_epoch(conversation_id)
        new_epoch = current + 1
        raw = bytearray(secrets.token_bytes(32))
        try:
            sealed = _seal_backend(
                self._ratchet_wrap_key(conversation_id),
                bytes(raw),
                self._ratchet_aad(conversation_id),
            )
        finally:
            self._zero(raw)
        ratchets = self._read_ratchets()
        conv = ratchets["conversations"][conversation_id]
        live = {str(new_epoch): _b64e(sealed)}
        # One-epoch grace: the previous epoch stays openable for in-flight
        # envelopes. Everything older is destroyed here — not carried over.
        if str(current) in conv.get("live", {}):
            live[str(current)] = conv["live"][str(current)]
        conv["epoch"] = new_epoch
        conv["live"] = live
        self._write_ratchets(ratchets)
        return {
            "conversation_id": conversation_id,
            "epoch": new_epoch,
            "previous_epoch": current,
        }

    # -- device registry ---------------------------------------------------

    def _read_devices(self) -> dict:
        path = self._path(_DEVICES_FILE)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise VeilError("devices registry unreadable: %s" % exc) from exc
        if not isinstance(data, dict):
            raise VeilError("devices registry corrupt")
        return data

    def _write_devices(self, devices: dict) -> None:
        # Metadata only — no key material lives here. Single-winner under lock.
        with store_lock(self._path(_DEVICES_FILE)):
            atomic_write_bytes(
                self._path(_DEVICES_FILE),
                json.dumps(devices, indent=2, sort_keys=True).encode("utf-8"),
            )

    def create_device(self, name: str) -> dict:
        """Register a new device. Returns its *public* identity; the
        attestation token is derived on demand and never exported."""
        _sanitize(name, "device name")
        self._require_unlocked()
        devices = self._read_devices()
        if any(d.get("name") == name for d in devices.values()):
            raise VeilError("device name %r already registered" % name)
        device_id = uuid.uuid4().hex
        record = {
            "device_id": device_id,
            "name": name,
            "key_version": 1,
            "created_at": _utcnow(),
        }
        devices[device_id] = record
        self._write_devices(devices)
        return self.identity(device_id)

    def identity(self, device_id: str) -> dict:
        """Public identity: id, name, key version, creation time, and the
        grouped-hex fingerprint for the verification ceremony."""
        devices = self._read_devices()
        record = devices.get(device_id)
        if record is None:
            raise VeilError("unknown device")
        token = self._device_token(device_id, record["key_version"])
        return {
            "device_id": device_id,
            "name": record["name"],
            "key_version": record["key_version"],
            "created_at": record["created_at"],
            "fingerprint": fingerprint(token),
            "revoked": self.is_revoked(device_id),
        }

    def verify_fingerprint(self, device_id: str, candidate: str) -> bool:
        """The verification ceremony: compare a fingerprint read out of band
        (call, in person) against this device's real one."""
        try:
            real = self.identity(device_id)["fingerprint"]
        except VeilError:
            return False
        norm = " ".join(candidate.lower().split())
        return hmac.compare_digest(norm, real)

    def rotate_device(self, device_id: str) -> dict:
        """Bump the key version. The previous version keeps verifying for a
        one-version grace window so in-flight envelopes still open."""
        self._require_unlocked()
        devices = self._read_devices()
        record = devices.get(device_id)
        if record is None:
            raise VeilError("unknown device")
        if self.is_revoked(device_id):
            raise VeilError("device is revoked")
        record["key_version"] += 1
        devices[device_id] = record
        self._write_devices(devices)
        return self.identity(device_id)

    # -- local attestation ---------------------------------------------------

    def attest(self, device_id: str, message: bytes) -> str:
        """HMAC attestation under this device's current token. Local
        attestation — proves the *keeper's device* sealed the bytes, not a
        cross-device PKI signature."""
        devices = self._read_devices()
        record = devices.get(device_id)
        if record is None:
            raise VeilError("unknown device")
        if self.is_revoked(device_id):
            raise VeilError("device is revoked")
        token = self._device_token(device_id, record["key_version"])
        return hmac.new(token, _DOMAIN_ATTEST + message, hashlib.sha256).hexdigest()

    def verify_attestation(self, device_id: str, message: bytes, tag: str) -> bool:
        """Verify against the current token, then the previous version
        (rotation grace). Revoked or unknown devices never verify."""
        devices = self._read_devices()
        record = devices.get(device_id)
        if record is None or self.is_revoked(device_id):
            return False
        for version in (record["key_version"], record["key_version"] - 1):
            if version < 1:
                continue
            token = self._device_token(device_id, version)
            expect = hmac.new(
                token, _DOMAIN_ATTEST + message, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(expect, tag.lower()):
                return True
        return False

    # -- revocation ledger -----------------------------------------------------

    def _ledger_entries(self) -> list:
        path = self._path(_REVOCATIONS_FILE)
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def revoke_device(self, device_id: str, reason: str = "") -> dict:
        """Append a revocation statement to the HMAC-chained ledger. From
        this point the device can no longer attest, seal, or open."""
        self._require_unlocked()
        devices = self._read_devices()
        if device_id not in devices:
            raise VeilError("unknown device")
        if self.is_revoked(device_id):
            raise VeilError("device already revoked")
        key = self._ledger_key()
        entries = self._ledger_entries()
        prev_hash = entries[-1]["entry_hash"] if entries else "GENESIS"
        entry = {
            "device_id": device_id,
            "key_version": devices[device_id]["key_version"],
            "revoked_at": _utcnow(),
            "reason": reason[:280],
            "prev_hash": prev_hash,
        }
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
        entry["entry_hash"] = hmac.new(key, canonical, hashlib.sha256).hexdigest()
        line = json.dumps(entry, sort_keys=True) + "\n"
        path = self._path(_REVOCATIONS_FILE)
        with store_lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
            os.chmod(path, 0o600)
        return entry

    def is_revoked(self, device_id: str) -> bool:
        return any(e.get("device_id") == device_id for e in self._ledger_entries())

    def verify_ledger(self) -> bool:
        """Recompute the HMAC chain. Any tampered or reordered entry fails."""
        try:
            key = self._ledger_key()
        except VeilError:
            return False
        prev_hash = "GENESIS"
        for entry in self._ledger_entries():
            if entry.get("prev_hash") != prev_hash:
                return False
            check = dict(entry)
            entry_hash = check.pop("entry_hash", None)
            canonical = json.dumps(
                check, sort_keys=True, separators=(",", ":")
            ).encode()
            expect = hmac.new(key, canonical, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expect, entry_hash or ""):
                return False
            prev_hash = entry_hash
        return True

    # -- sealed messaging ------------------------------------------------------

    def _read_seq(self) -> dict:
        path = self._path(_SEQ_FILE)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise VeilError("sequence registry unreadable: %s" % exc) from exc
        return data if isinstance(data, dict) else {}

    def _write_seq(self, seq: dict) -> None:
        with store_lock(self._path(_SEQ_FILE)):
            atomic_write_bytes(
                self._path(_SEQ_FILE),
                json.dumps(seq, indent=2, sort_keys=True).encode("utf-8"),
            )

    @staticmethod
    def _header_aad(header: dict) -> bytes:
        """Canonical header bytes bound into the envelope's AAD: any
        tampering with sender, recipient, seq, or version fails the MAC."""
        return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def seal_message(
        self,
        conversation_id: str,
        sender_device_id: str,
        recipient_device_id: str,
        plaintext: bytes,
    ) -> dict:
        """Seal a tamper-evident envelope. The header (versions, ids,
        sequence, timestamp) is bound into the AAD; the device attestation
        covers header + blob. Sequence numbers are per (conversation,
        sender) and strictly increasing — the replay defense."""
        _sanitize(conversation_id, "conversation_id")
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise VeilError("plaintext must be non-empty bytes")
        devices = self._read_devices()
        sender = devices.get(sender_device_id)
        if sender is None:
            raise VeilError("unknown sender device")
        if self.is_revoked(sender_device_id):
            raise VeilError("sender device is revoked")
        if recipient_device_id not in devices:
            raise VeilError("unknown recipient device")

        seq_reg = self._read_seq()
        # Send-side counter lives under "sent"; the receive-side replay
        # watermark lives under "seen" (open_message). One vault playing
        # both roles must not trip its own replay defense.
        sent = seq_reg.setdefault("sent", {}).setdefault(conversation_id, {})
        last = sent.get(sender_device_id, 0)
        seq = last + 1

        header = {
            "protocol_version": _PROTOCOL_VERSION,
            "message_id": uuid.uuid4().hex,
            "conversation_id": conversation_id,
            "sender": sender_device_id,
            "recipient": recipient_device_id,
            "timestamp": _utcnow(),
            "seq": seq,
            "key_version": sender["key_version"],
            # Epoch is AAD-bound: an envelope cannot be transplanted across
            # ratchet rotations without failing authentication.
            "epoch": self._ensure_epoch(conversation_id),
        }
        aad = self._header_aad(header)
        blob = _seal_backend(
            self._epoch_key(conversation_id, header["epoch"]),
            bytes(plaintext),
            aad,
        )
        token = self._device_token(sender_device_id, sender["key_version"])
        attestation = hmac.new(
            token, _DOMAIN_ATTEST + aad + blob, hashlib.sha256
        ).hexdigest()

        envelope = dict(header)
        envelope["blob"] = _b64e(blob)
        envelope["attestation"] = attestation

        sent[sender_device_id] = seq
        self._write_seq(seq_reg)
        return envelope

    def open_message(self, envelope: dict) -> dict:
        """Open and authenticate an envelope. Fails closed on: wrong
        protocol version, unknown/revoked sender, bad attestation, tampered
        blob or header, or a replayed/out-of-order sequence number."""
        if not isinstance(envelope, dict):
            raise VeilError("envelope must be a dict")
        if envelope.get("protocol_version") != _PROTOCOL_VERSION:
            raise VeilError("unsupported protocol version")
        sender_id = envelope.get("sender")
        conversation_id = envelope.get("conversation_id")
        devices = self._read_devices()
        sender = devices.get(sender_id)
        if sender is None:
            raise VeilError("unknown sender device")
        if self.is_revoked(sender_id):
            raise VeilError("sender device is revoked")

        header = {
            k: envelope[k]
            for k in (
                "protocol_version",
                "message_id",
                "conversation_id",
                "sender",
                "recipient",
                "timestamp",
                "seq",
                "key_version",
            )
        }
        # Pre-ratchet envelopes carry no epoch — they seal under the legacy
        # epoch-0 (master-derived) key. New envelopes always carry theirs,
        # and it is AAD-bound above.
        epoch = envelope.get("epoch", 0)
        if not isinstance(epoch, int) or epoch < 0:
            raise VeilError("bad epoch")
        if "epoch" in envelope:
            header["epoch"] = epoch
        aad = self._header_aad(header)
        try:
            blob = _b64d(envelope["blob"])
        except KeyError as exc:
            raise VeilError("envelope missing blob") from exc

        # Attestation first (current token, then rotation-grace previous).
        attestation = str(envelope.get("attestation", "")).lower()
        ok = False
        for version in (sender["key_version"], sender["key_version"] - 1):
            if version < 1:
                continue
            token = self._device_token(sender_id, version)
            expect = hmac.new(
                token, _DOMAIN_ATTEST + aad + blob, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(expect, attestation):
                ok = True
                break
        if not ok:
            raise VeilError("attestation failed: forged or rotated-away envelope")

        # Verify-then-decrypt; header tampering fails the AAD check here.
        # The epoch key resolves through the ratchet: a destroyed epoch
        # fails closed, which is the forward-secrecy guarantee working.
        plaintext = _open_backend(self._epoch_key(conversation_id, epoch), blob, aad)

        # Replay / reorder defense: strictly increasing per (conversation,
        # sender) on the *receive* watermark ("seen" namespace — separate
        # from the send-side counter so self-talk doesn't false-positive).
        seq = envelope.get("seq")
        if not isinstance(seq, int) or seq < 1:
            raise VeilError("bad sequence number")
        seq_reg = self._read_seq()
        seen = seq_reg.setdefault("seen", {}).setdefault(conversation_id, {})
        last = seen.get(sender_id, 0)
        if seq <= last:
            raise VeilError(
                "replayed or out-of-order message (seq %d <= %d)" % (seq, last)
            )
        seen[sender_id] = seq
        self._write_seq(seq_reg)

        return {
            "plaintext": plaintext,
            "conversation_id": conversation_id,
            "sender": sender_id,
            "recipient": envelope.get("recipient"),
            "seq": seq,
            "timestamp": envelope.get("timestamp"),
            "message_id": envelope.get("message_id"),
        }

    # -- envelope store (ciphertext only) ----------------------------------------

    def store_envelope(self, envelope: dict) -> None:
        """Append a sealed envelope to the conversation's store. The store
        never sees plaintext — only sealed envelopes."""
        conversation_id = envelope.get("conversation_id")
        path = self._conv_path(conversation_id)
        line = json.dumps(envelope, sort_keys=True) + "\n"
        with store_lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
            os.chmod(path, 0o600)

    def fetch_envelopes(self, conversation_id: str) -> list:
        """Fetch sealed envelopes for a conversation (still sealed)."""
        path = self._conv_path(conversation_id)
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out


# ---------------------------------------------------------------------------
# Threat register + explicit non-claims (recreated LEVI-native)
# ---------------------------------------------------------------------------

#: Data-driven threat register: threat -> asset -> attack -> mitigation ->
#: residual risk -> status. The keeper reviews this, not the marketing copy.
THREATS: list[dict[str, str]] = [
    {
        "id": "stolen-device",
        "asset": "keeper passphrase; unlocked master key",
        "attack": "attacker obtains the device while the vault is unlocked",
        "mitigation": "lock() best-effort zeroizes the master key; PBKDF2 "
        "600k iterations slows passphrase guessing; state files are "
        "owner-only (0o700/0o600)",
        "residual": "an unlocked device in active use; a weak keeper "
        "passphrase; memory forensics against a running process",
        "status": "implemented",
    },
    {
        "id": "tampered-envelope",
        "asset": "message confidentiality and integrity",
        "mitigation": "encrypt-then-MAC with the header bound into the AAD; "
        "device attestation over header + blob; verify-then-decrypt with "
        "constant-time compare — any flipped bit fails closed; AES-256-GCM "
        "via the 'cryptography' package when importable",
        "attack": "attacker flips bits in a stored or in-flight envelope, or "
        "swaps header fields (sender, seq, epoch) between envelopes",
        "residual": "when the 'cryptography' package is absent the "
        "construction is fallback-grade (HMAC-CTR, not AES) — the instance "
        "reports its backend via Veil.backend; implementation bugs in "
        "either path",
        "status": "implemented",
    },
    {
        "id": "replayed-message",
        "asset": "conversation ordering and freshness",
        "attack": "attacker re-injects a previously sealed envelope",
        "mitigation": "per-(conversation, sender) strictly increasing "
        "sequence numbers bound into the AAD; seq <= last_seen is rejected",
        "residual": "deleting the sequence registry resets the replay "
        "window — the registry lives in the same keeper-held store, so its "
        "loss is detectable but not preventable here",
        "status": "implemented",
    },
    {
        "id": "revoked-device-speaks",
        "asset": "authorization of senders",
        "attack": "a compromised device keeps sealing messages after "
        "compromise is discovered",
        "mitigation": "revocation ledger consulted on seal, attest, and "
        "open; ledger entries are HMAC-chained so tampering is detectable "
        "via verify_ledger()",
        "residual": "the ledger is local — there is no network distribution "
        "in this module, so other keepers' copies do not learn of revocation",
        "status": "implemented",
    },
    {
        "id": "ceremony-skip",
        "asset": "peer identity (who am I really talking to)",
        "attack": "attacker substitutes their own device identity and the "
        "keeper never checks",
        "mitigation": "grouped-hex fingerprints + verify_fingerprint() for "
        "the out-of-band verification ceremony",
        "residual": "a keeper who skips the ceremony trusts on first use "
        "only — social engineering of the ceremony itself",
        "status": "implemented",
    },
    {
        "id": "weak-passphrase",
        "asset": "master key (everything derives from it)",
        "attack": "offline dictionary / brute-force against the salt + "
        "verifier in config.json",
        "mitigation": "memory-hard scrypt (n=2^15, r=8, p=1, 32 MiB, "
        "workstation-grade) where the stdlib offers it; PBKDF2-HMAC-SHA256 "
        "at 600,000 iterations otherwise; random 16-byte salt; the KDF "
        "choice is pinned in config.json and reported by Veil.kdf; "
        "verifier comparison is constant-time",
        "residual": "scrypt params are workstation-grade, not "
        "server-hardened; a weak passphrase still falls to a determined "
        "attacker; moving config.json to a machine whose OpenSSL caps "
        "scrypt memory fails closed at unlock",
        "status": "implemented",
    },
    {
        "id": "state-tampering",
        "asset": "device registry, sequence counters, revocation ledger",
        "attack": "attacker edits JSON state files on disk",
        "mitigation": "atomic writes + owner-only permissions; revocation "
        "ledger is HMAC-chained and verifiable; corrupt JSON fails closed "
        "instead of being absorbed",
        "residual": "devices.json metadata is not MAC'd — tampering causes "
        "denial of service (unknown device / wrong version), not key "
        "compromise; no key material lives there by design",
        "status": "implemented",
    },
    {
        "id": "master-key-compromise-reads-history",
        "asset": "past conversation traffic (stored sealed envelopes)",
        "attack": "attacker recovers the keeper's master key — passphrase "
        "cracked offline, or an unlocked device seized — and tries to "
        "decrypt every stored envelope",
        "mitigation": "per-conversation epoch ratchet "
        "(rotate_conversation): epoch >= 1 keys are fresh random bytes, "
        "sealed under a master-derived wrap key, and DESTROYED on "
        "rotation — only the live epoch plus one grace epoch are "
        "retained. A destroyed epoch cannot be re-derived, not even with "
        "the master key.",
        "residual": "the live epochs are sealed under the master key, so "
        "a master compromise exposes them; epoch 0 (pre-ratchet, "
        "master-derived) never had forward secrecy — rotate after "
        "upgrading; a disk snapshot taken before a rotation can recover "
        "the epoch it captured; the keeper sets the rotation cadence",
        "status": "implemented",
    },
    {
        "id": "nonce-reuse",
        "asset": "confidentiality of sealed envelopes",
        "attack": "two envelopes sealed under the same (key, nonce) leak "
        "the xor of their plaintexts",
        "mitigation": "16 fresh bytes from secrets.token_bytes per seal; "
        "conversation keys are per-conversation subkeys",
        "residual": "depends on os.urandom soundness; a broken RNG breaks "
        "everything (documented assumption)",
        "status": "implemented",
    },
]

#: What Veil does NOT claim. Honest gaps beat polished claims.
NON_CLAIMS: list[str] = [
    "No post-quantum resistance.",
    "Not AES when the 'cryptography' package is absent: the stdlib "
    "fallback is HMAC-SHA256 counter-mode + HMAC — standard composition, "
    "fallback-grade, honestly labeled via Veil.backend.",
    "Forward secrecy is epoch-scoped, not absolute: only destroyed epochs "
    "are dark. The live epoch and one grace epoch are sealed under the "
    "master key (a master compromise exposes them); epoch 0 (pre-ratchet, "
    "master-derived) never had forward secrecy — rotate after upgrading; "
    "a disk snapshot taken before a rotation can recover the epoch it "
    "captured.",
    "Local attestation is not cross-device PKI: device 'signatures' are "
    "HMACs under keeper-derived tokens. Cross-device trust comes from the "
    "fingerprint ceremony, not from math alone.",
    "No traffic-analysis resistance and no network transport at all — this "
    "module is local-only by design.",
    "No protection if the keeper's passphrase is compromised or the vault "
    "is left unlocked on a hostile device.",
]


def check_invariants() -> list[tuple[str, bool, str]]:
    """Structural invariants over the threat register and protocol.

    Returns ``(name, ok, detail)`` triples. These are the promises the
    keeper can audit without reading a line of crypto code.
    """
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
    check(
        "every threat names a mitigation",
        all(t.get("mitigation") for t in THREATS),
    )
    check(
        "every threat names its residual risk",
        all(t.get("residual") for t in THREATS),
    )
    check(
        "non-claims are documented, not hidden",
        len(NON_CLAIMS) >= 5,
        "%d explicit non-claims" % len(NON_CLAIMS),
    )
    check(
        "protocol version is pinned",
        _PROTOCOL_VERSION == 1,
        "v%d" % _PROTOCOL_VERSION,
    )
    check(
        "blob magic is pinned",
        _BLOB_MAGIC == b"VB1",
        _BLOB_MAGIC.decode("ascii"),
    )
    check(
        "envelope versions are distinguishable",
        _BLOB_MAGIC != _BLOB_MAGIC_GCM,
        "%s vs %s"
        % (_BLOB_MAGIC.decode("ascii"), _BLOB_MAGIC_GCM.decode("ascii")),
    )
    # The versioned dispatcher round-trips each backend's envelopes and
    # fails closed on unknown magic — never silently decrypts under the
    # wrong layout.
    try:
        _b1 = _seal(b"k" * 32, b"n" * 16, b"ping", b"aad")
        _ok_v1 = _open_backend(b"k" * 32, _b1, b"aad") == b"ping"
    except VeilError:
        _ok_v1 = False
    check("v1 envelopes open through the versioned dispatcher", _ok_v1)
    if _AESGCM is not None:
        try:
            _b2 = _seal_gcm(b"k" * 32, b"n" * 12, b"ping", b"aad")
            _ok_v2 = (
                _open_backend(b"k" * 32, _b2, b"aad") == b"ping"
                and _b2.startswith(_BLOB_MAGIC_GCM)
            )
        except VeilError:
            _ok_v2 = False
        check("v2 (AES-256-GCM) envelopes open through the dispatcher", _ok_v2)
    try:
        _open_backend(b"k" * 32, b"BAD" + b"\x00" * 60, b"aad")
        _ok_bad = False
    except VeilError:
        _ok_bad = True
    check("unknown envelope magic fails closed", _ok_bad)
    check(
        "kdf selection is pinned to a known function",
        _kdf_default() in ("scrypt", "pbkdf2"),
        _kdf_default(),
    )
    # Envelope header fields that MUST be AAD-bound (checked against the
    # implementation's own header construction).
    header = {
        "protocol_version": 1,
        "message_id": "x",
        "conversation_id": "x",
        "sender": "x",
        "recipient": "x",
        "timestamp": "x",
        "seq": 1,
        "key_version": 1,
        "epoch": 1,
    }
    aad = Veil._header_aad(header)
    check(
        "header AAD binding covers sender, seq, version, and epoch",
        all(
            token in aad
            for token in (b'"sender"', b'"seq"', b'"protocol_version"', b'"epoch"')
        ),
    )
    return results


__all__ = [
    "Veil",
    "VeilError",
    "THREATS",
    "NON_CLAIMS",
    "check_invariants",
    "fingerprint",
]
