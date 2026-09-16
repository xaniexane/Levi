"""Credential vault — encrypted-at-rest secret store (LEVI-original).

Crypto posture, stated plainly:

PREFERRED BACKEND (``vault.backend == "fernet"``):
  Key: PBKDF2-HMAC-SHA256 (600,000 iterations) over a per-vault random
  16-byte salt stored at ``<vault>/.salt`` (owner-only).
  Encryption: Fernet from the ``cryptography`` package — AES-128-CBC with
  HMAC-SHA256 authenticated encryption. (The repo already depends on
  ``cryptography`` for its vault seal; this vault reuses that dependency.)

FALLBACK BACKEND (``vault.backend == "stdlib-fallback"``) — used ONLY when
``cryptography`` cannot be imported:
  Key: same PBKDF2-HMAC-SHA256 derivation (stdlib ``hashlib``).
  Encryption: XOR stream cipher whose keystream is HMAC-SHA256(key,
  ``"cybrus-stream" || nonce || counter_be32``) blocks — this is NOT AES and
  is documented honestly as fallback-grade. Authentication: HMAC-SHA256 over
  (domain-separator || salt || nonce || ciphertext), checked with
  ``hmac.compare_digest`` BEFORE any decryption (verify-then-decrypt).
  Blob layout is self-describing, so a vault written by either backend
  opens under the other — except a Fernet blob when ``cryptography`` is
  missing, which fails closed with a clear error rather than pretending.

Fail-closed behavior: a wrong passphrase cannot decrypt the blob — Fernet
raises InvalidToken, the fallback raises on MAC mismatch — and both are
surfaced as :class:`VaultError`, never a raw library exception. Tampered
blobs (flipped bits) fail authentication the same way.

Storage: one encrypted blob at ``<vault>/entries.enc`` holding
``{service: {username: secret}}`` as JSON. All writes atomic (tmp +
``os.replace``), owner-only (0o600), vault dir 0o700. ``list_services``
returns names only — secrets never leave the vault except via ``get``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Optional

from levi.cybrus._paths import atomic_write_bytes, cybrus_dir, store_lock

_VAULT_SUBDIR = "vault"
_SALT_FILE = ".salt"
_ENTRIES_FILE = "entries.enc"
_SALT_LEN = 16
_NONCE_LEN = 16
_PBKDF2_ITERATIONS = 600_000

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

# Self-describing blob schemes.
_SCHEME_FERNET = "cybrus-vault-fernet-v1"
_SCHEME_STDLIB = "cybrus-vault-stdlib-v1"

_MAC_DOMAIN = b"cybrus-vault-mac-v1\x00"
_STREAM_DOMAIN = b"cybrus-stream-v1\x00"


class VaultError(ValueError):
    """Vault errors: invalid requests, unlock failures, tamper detection."""


def _sanitize(value: str, what: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise VaultError(
            "invalid %s %r: use 1-64 chars of [A-Za-z0-9._-]" % (what, value)
        )
    return value


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256, 600k iterations, 32-byte key (stdlib)."""
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )


def _try_fernet():
    """Import Fernet, or return None when ``cryptography`` is unavailable."""
    try:
        from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    except ImportError:
        return None, None
    return Fernet, InvalidToken


class _StdlibCipher:
    """Fallback-grade cipher: HMAC-SHA256 counter-mode stream + HMAC auth.

    HONEST LIMITS: this is NOT AES. It is a labeled fallback for environments
    where the ``cryptography`` package cannot be installed. Authentication is
    real (HMAC-SHA256, verify-then-decrypt, constant-time compare), and the
    key derivation is the same 600k-iteration PBKDF2 as the Fernet path — but
    a stream built from HMAC counter mode does not carry the cryptanalytic
    scrutiny of AES. Treat ``backend == "stdlib-fallback"`` as "better than
    plaintext, not a substitute for real AEAD".
    """

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise VaultError("stdlib cipher requires a 32-byte key")
        self._key = key

    def _keystream(self, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hmac.new(
                self._key,
                _STREAM_DOMAIN + nonce + counter.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    @staticmethod
    def _xor(a: bytes, b: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(a, b, strict=True))

    def encrypt(self, salt: bytes, plaintext: bytes) -> bytes:
        """Return a self-describing authenticated blob (JSON bytes)."""
        nonce = os.urandom(_NONCE_LEN)
        ciphertext = self._xor(plaintext, self._keystream(nonce, len(plaintext)))
        mac = hmac.new(
            self._key, _MAC_DOMAIN + salt + nonce + ciphertext, hashlib.sha256
        ).digest()
        blob = {
            "scheme": _SCHEME_STDLIB,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "mac": base64.b64encode(mac).decode("ascii"),
        }
        return json.dumps(blob, sort_keys=True).encode("utf-8")

    def decrypt(self, salt: bytes, blob: bytes) -> bytes:
        """Verify-then-decrypt. Raises VaultError on auth failure or tamper."""
        try:
            data = json.loads(blob.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise VaultError("vault blob is not valid JSON: corrupted") from exc
        if not isinstance(data, dict) or data.get("scheme") != _SCHEME_STDLIB:
            raise VaultError("vault blob scheme mismatch: corrupted or foreign")
        try:
            nonce = base64.b64decode(data["nonce"])
            ciphertext = base64.b64decode(data["ciphertext"])
            expected_mac = base64.b64decode(data["mac"])
        except (KeyError, ValueError) as exc:
            raise VaultError("vault blob fields malformed: corrupted") from exc
        mac = hmac.new(
            self._key, _MAC_DOMAIN + salt + nonce + ciphertext, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise VaultError("cannot unlock vault: wrong passphrase or tampered data")
        return self._xor(ciphertext, self._keystream(nonce, len(ciphertext)))


class CredentialVault:
    """Encrypted-at-rest store for ``(service, username) -> secret``."""

    def __init__(self, passphrase: str, directory: Optional[Path] = None):
        if not isinstance(passphrase, str) or not passphrase:
            raise ValueError(
                "passphrase required: pass a non-empty string "
                "(getpass prompt preferred)"
            )
        self.dir = (
            Path(directory) if directory is not None else cybrus_dir() / _VAULT_SUBDIR
        )
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)  # fail closed on permissions

        self._salt = self._load_or_create_salt()
        self._key = _derive_key(passphrase, self._salt)

        fernet_cls, invalid_token = _try_fernet()
        self.backend = "fernet" if fernet_cls is not None else "stdlib-fallback"
        self._fernet = (
            fernet_cls(base64.urlsafe_b64encode(self._key)) if fernet_cls else None
        )
        self._InvalidToken = invalid_token
        self._stdlib = _StdlibCipher(self._key)

    # -- key material ----------------------------------------------------

    def _load_or_create_salt(self) -> bytes:
        path = self.dir / _SALT_FILE
        if path.exists():
            salt = path.read_bytes()
            if len(salt) != _SALT_LEN:
                raise VaultError(
                    "vault salt file is corrupt (%d bytes, expected %d); "
                    "refusing to derive a key" % (len(salt), _SALT_LEN)
                )
            return salt
        salt = os.urandom(_SALT_LEN)
        atomic_write_bytes(path, salt, 0o600)
        return salt

    def _salt_path(self) -> Path:
        return self.dir / _SALT_FILE

    def _entries_path(self) -> Path:
        return self.dir / _ENTRIES_FILE

    # -- blob encode/decode -----------------------------------------------

    def _encrypt_blob(self, plaintext: bytes) -> bytes:
        if self._fernet is not None:
            token = self._fernet.encrypt(plaintext)
            blob = {
                "scheme": _SCHEME_FERNET,
                "salt": base64.b64encode(self._salt).decode("ascii"),
                "token": token.decode("ascii"),
            }
            return json.dumps(blob, sort_keys=True).encode("utf-8")
        return self._stdlib.encrypt(self._salt, plaintext)

    def _decrypt_blob(self, blob: bytes) -> bytes:
        try:
            parsed = json.loads(blob.decode("utf-8"))
            scheme = parsed.get("scheme") if isinstance(parsed, dict) else None
        except (ValueError, UnicodeDecodeError, AttributeError) as exc:
            raise VaultError("vault blob corrupted: not parseable") from exc
        if scheme == _SCHEME_FERNET:
            if self._fernet is None:
                raise VaultError(
                    "vault blob needs the 'cryptography' package to open; "
                    "install it with: pip install cryptography"
                )
            data = parsed
            try:
                return self._fernet.decrypt(data["token"].encode("ascii"))
            except self._InvalidToken as exc:
                raise VaultError(
                    "cannot unlock vault: wrong passphrase or tampered data"
                ) from exc
        if scheme == _SCHEME_STDLIB:
            return self._stdlib.decrypt(self._salt, blob)
        raise VaultError("vault blob scheme unrecognized: corrupted or foreign")

    # -- entry store -------------------------------------------------------

    def _load_entries(self) -> dict:
        path = self._entries_path()
        if not path.exists():
            return {}
        plaintext = self._decrypt_blob(path.read_bytes())
        try:
            data = json.loads(plaintext.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise VaultError("vault entries corrupted after decrypt") from exc
        if not isinstance(data, dict):
            raise VaultError("vault entries corrupted after decrypt")
        return data

    def _save_entries(self, entries: dict) -> None:
        plaintext = json.dumps(entries, sort_keys=True).encode("utf-8")
        atomic_write_bytes(self._entries_path(), self._encrypt_blob(plaintext), 0o600)

    # -- public API ---------------------------------------------------------

    def store(self, service: str, username: str, secret: str) -> None:
        """Encrypt ``secret`` under ``(service, username)`` (atomic write).

        The load → modify → save runs under the store lock so concurrent
        writers cannot drop each other's entries.
        """
        service = _sanitize(service, "service")
        username = _sanitize(username, "username")
        if not isinstance(secret, str) or not secret:
            raise VaultError("secret must be a non-empty string")
        with store_lock(self._entries_path()):
            entries = self._load_entries()
            entries.setdefault(service, {})[username] = secret
            self._save_entries(entries)

    def get(self, service: str, username: str) -> str:
        """Decrypt and return the secret. Raises ``KeyError`` when the entry
        does not exist, :class:`VaultError` on wrong passphrase/tamper."""
        service = _sanitize(service, "service")
        username = _sanitize(username, "username")
        entries = self._load_entries()
        try:
            return entries[service][username]
        except KeyError:
            raise KeyError(f"no vault entry for {service!r}/{username!r}") from None

    def delete(self, service: str, username: str) -> None:
        """Remove an entry. Raises ``KeyError`` when it does not exist."""
        service = _sanitize(service, "service")
        username = _sanitize(username, "username")
        with store_lock(self._entries_path()):
            entries = self._load_entries()
            try:
                del entries[service][username]
            except KeyError:
                raise KeyError(f"no vault entry for {service!r}/{username!r}") from None
            if not entries[service]:
                del entries[service]
            self._save_entries(entries)

    def list_services(self) -> list:
        """Sorted service names. Names only — secrets never listed."""
        return sorted(self._load_entries().keys())

    def change_master_password(self, new_passphrase: str) -> None:
        """Re-encrypt every entry under a fresh salt and ``new_passphrase``.

        The old key is dropped from memory afterwards; entries encrypted
        under the old passphrase become unreadable by this instance (a new
        instance must be opened with the new passphrase).
        """
        if not isinstance(new_passphrase, str) or not new_passphrase:
            raise ValueError("new passphrase must be a non-empty string")
        with store_lock(self._entries_path()):
            entries = self._load_entries()  # fails closed on wrong current passphrase
            self._salt = os.urandom(_SALT_LEN)
            atomic_write_bytes(self._salt_path(), self._salt, 0o600)
            self._key = _derive_key(new_passphrase, self._salt)
            if self._fernet is not None:
                fernet_cls = type(self._fernet)
                self._fernet = fernet_cls(base64.urlsafe_b64encode(self._key))
            self._stdlib = _StdlibCipher(self._key)
            self._save_entries(entries)
        # Scrub the in-memory entries copy; key/fernet already replaced.
        entries.clear()
