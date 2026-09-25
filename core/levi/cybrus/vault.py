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


# ===========================================================================
# Layer 2 — OAuth token vault, identity scoping, auto-lock (additive).
#
# Everything above (CredentialVault) is untouched. This layer adds:
#   * generate_password — CSPRNG password generation
#   * IdentityVault — per-identity credential namespaces (containment by
#     construction: cybrus.id.<identity>.<service>)
#   * OAuthVault — OAuth access/refresh tokens with scopes, expiry,
#     provider, owning identity; refresh metadata tracked
#   * AutoLockVault — drops the in-memory key after inactivity
#   * Vault access audit — metadata only, never secret values
#
# Founder containment (binding law): the vault exposes NO share, copy, or
# export path for any entry. Founder-tier-owned credentials therefore
# cannot leave Cybrus — there is no API that could move them.
# ===========================================================================

_IDENTITY_NS = "cybrus.id"
_OAUTH_NS = "cybrus.oauth"
_IDENTITY_META_STORE = "vault_identity_meta"

_PASSWORD_ALPHABET = (
    "abcdefghijkmnopqrstuvwxyz"  # no l
    "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O
    "23456789"  # no 0, 1
    "!@#$%^&*-_=+"
)


class VaultLockedError(VaultError):
    """The vault auto-locked after inactivity — unlock again to continue."""


class OAuthError(VaultError):
    """OAuth vault errors: unknown token, containment violation."""


def generate_password(length: int = 24) -> str:
    """Generate a strong random password from the unambiguous alphabet.

    Uses :mod:`secrets` (CSPRNG). Raises :class:`VaultError` when
    ``length`` < 12. The value is returned once — store it in the vault
    immediately; it is never logged anywhere.
    """
    import secrets

    if not isinstance(length, int) or isinstance(length, bool) or length < 12:
        raise VaultError("password length must be an integer >= 12")
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _audit_vault(event: str, identity: str, details: Optional[dict] = None) -> None:
    """Append a vault audit record. ``details`` must NEVER contain secret
    material — callers pass names, providers, scopes, never token values."""
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(identity), dict(details or {}))


def _identity_tier(identity: str) -> Optional[str]:
    """Tier of an identity, or None when the identity does not exist."""
    try:
        from levi.cybrus.identity import IdentityStore

        rec = IdentityStore().get(identity)
        return rec.get("tier") if rec else None
    except Exception:
        return None


def _load_meta() -> dict:
    from levi.cybrus._paths import load_json_store, store_path

    return load_json_store(store_path(_IDENTITY_META_STORE)) or {}


def _save_meta(meta: dict) -> None:
    from levi.cybrus._paths import save_json_store, store_lock, store_path

    path = store_path(_IDENTITY_META_STORE)
    with store_lock(path):
        current = _load_meta()
        current.update(meta)
        save_json_store(path, current)


class IdentityVault:
    """Per-identity credential namespace over :class:`CredentialVault`.

    Entries live under the service ``cybrus.id.<identity>.<service>``, so
    identity A can never address identity B's entries — scoping is by
    construction, not convention. Owner + tier are recorded in vault
    metadata; founder-tier-owned entries are additionally flagged
    ``founder_owned`` — and since the vault has no share/copy/export path,
    founder-only powers never leave Cybrus.
    """

    def __init__(self, passphrase: str, identity: str, directory: Optional[Path] = None):
        self.identity = _sanitize(identity, "identity")
        self._vault = CredentialVault(passphrase, directory=directory)
        tier = _identity_tier(self.identity)
        _save_meta(
            {
                f"{_IDENTITY_NS}.{self.identity}": {
                    "owner": self.identity,
                    "tier": tier,
                    "founder_owned": tier == "founder",
                }
            }
        )

    @property
    def backend(self) -> str:
        """Which crypto backend unlocked this vault (honest label)."""
        return self._vault.backend

    def _service(self, service: str) -> str:
        return f"{_IDENTITY_NS}.{self.identity}.{_sanitize(service, 'service')}"

    def store(self, service: str, username: str, secret: str) -> None:
        self._vault.store(self._service(service), username, secret)
        _audit_vault(
            "vault.stored", self.identity, {"service": service, "username": username}
        )

    def get(self, service: str, username: str) -> str:
        secret = self._vault.get(self._service(service), username)
        _audit_vault(
            "vault.accessed", self.identity, {"service": service, "username": username}
        )
        return secret

    def delete(self, service: str, username: str) -> None:
        self._vault.delete(self._service(service), username)
        _audit_vault(
            "vault.deleted", self.identity, {"service": service, "username": username}
        )

    def list_services(self) -> list:
        """This identity's services only (namespace prefix stripped)."""
        prefix = f"{_IDENTITY_NS}.{self.identity}."
        return sorted(
            s[len(prefix):]
            for s in self._vault.list_services()
            if s.startswith(prefix)
        )

    def change_master_password(self, new_passphrase: str) -> None:
        self._vault.change_master_password(new_passphrase)


class OAuthVault:
    """OAuth token storage — access/refresh tokens with scopes, expiry,
    provider, and owning identity, encrypted at rest in the credential vault.

    Containment: a token is readable only by its owning identity —
    ``requester`` must equal the stored identity, or :class:`OAuthError`
    is raised. Refresh metadata (``refresh_count``,
    ``last_refreshed_at``) is tracked on every recorded refresh.

    Honest boundary: this vault records token metadata and performs NO
    network calls. The actual provider refresh HTTP exchange is the
    caller's job; :meth:`record_refresh` stores the fresh tokens the
    caller obtained elsewhere.
    """

    def __init__(self, passphrase: str, directory: Optional[Path] = None):
        self._vault = CredentialVault(passphrase, directory=directory)

    @property
    def backend(self) -> str:
        """Which crypto backend unlocked this vault (honest label)."""
        return self._vault.backend

    @staticmethod
    def _service(provider: str) -> str:
        try:
            return f"{_OAUTH_NS}.{_sanitize(provider, 'provider')}"
        except VaultError as exc:
            raise OAuthError(str(exc)) from exc

    @staticmethod
    def _record(
        provider: str,
        identity: str,
        access_token: str,
        refresh_token: Optional[str],
        scopes: list,
        expires_in: Optional[int],
        refresh_count: int = 0,
        last_refreshed_at: Optional[str] = None,
    ) -> dict:
        now = _utcnow_iso()
        return {
            "provider": provider,
            "identity": identity,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scopes": list(scopes),
            "issued_at": now,
            "expires_at": None
            if expires_in is None
            else __import__("time").time() + expires_in,
            "refresh_count": refresh_count,
            "last_refreshed_at": last_refreshed_at,
        }

    @staticmethod
    def _validate_scopes(scopes) -> list:
        if not isinstance(scopes, (list, tuple)):
            raise OAuthError("scopes must be a list of strings")
        clean = []
        for s in scopes:
            if not isinstance(s, str) or not s.strip():
                raise OAuthError("scopes must be non-empty strings")
            clean.append(s.strip())
        return clean

    def store_token(
        self,
        provider: str,
        identity: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        scopes=(),
        expires_in: Optional[int] = None,
    ) -> dict:
        """Store an OAuth token set. Returns the metadata (never printed
        with token values by callers)."""
        identity = _sanitize(identity, "identity")
        if not isinstance(access_token, str) or not access_token:
            raise OAuthError("access_token must be a non-empty string")
        if refresh_token is not None and (
            not isinstance(refresh_token, str) or not refresh_token
        ):
            raise OAuthError("refresh_token must be a non-empty string or None")
        if expires_in is not None and (
            not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise OAuthError("expires_in must be a positive integer or None")
        clean_scopes = self._validate_scopes(scopes)
        try:
            clean_provider = _sanitize(provider, "provider")
        except VaultError as exc:
            raise OAuthError(str(exc)) from exc
        record = self._record(
            clean_provider,
            identity,
            access_token,
            refresh_token,
            clean_scopes,
            expires_in,
        )
        service = self._service(provider)
        self._vault.store(service, identity, __import__("json").dumps(record))
        _audit_vault(
            "oauth.stored",
            identity,
            {
                "provider": record["provider"],
                "scopes": clean_scopes,
                "expires_in": expires_in,
                "has_refresh_token": refresh_token is not None,
            },
        )
        return {k: v for k, v in record.items() if k not in ("access_token", "refresh_token")}

    def _load(self, provider: str, identity: str) -> dict:
        import json

        identity = _sanitize(identity, "identity")
        try:
            raw = self._vault.get(self._service(provider), identity)
        except KeyError:
            raise OAuthError(
                f"no OAuth token stored for provider {provider!r} / identity {identity!r}"
            ) from None
        try:
            record = json.loads(raw)
        except ValueError as exc:
            raise OAuthError("stored OAuth record is corrupt") from exc
        if not isinstance(record, dict):
            raise OAuthError("stored OAuth record is corrupt")
        return record

    def get_token(self, provider: str, identity: str, requester: str) -> dict:
        """Return the full token record. ``requester`` must equal
        ``identity`` — containment by identity, no cross-reads."""
        requester = _sanitize(requester, "requester")
        identity = _sanitize(identity, "identity")
        if requester != identity:
            raise OAuthError(
                f"containment: {requester!r} may not read {identity!r}'s tokens"
            )
        record = self._load(provider, identity)
        _audit_vault(
            "oauth.accessed",
            identity,
            {"provider": record["provider"], "scopes": record["scopes"]},
        )
        return record

    def record_refresh(
        self,
        provider: str,
        identity: str,
        requester: str,
        new_access_token: str,
        new_refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> dict:
        """Record a refresh the caller performed against the provider:
        replaces the tokens, bumps ``refresh_count``, stamps
        ``last_refreshed_at``. No network is touched here."""
        requester = _sanitize(requester, "requester")
        identity = _sanitize(identity, "identity")
        if requester != identity:
            raise OAuthError(
                f"containment: {requester!r} may not refresh {identity!r}'s tokens"
            )
        old = self._load(provider, identity)
        if not isinstance(new_access_token, str) or not new_access_token:
            raise OAuthError("new_access_token must be a non-empty string")
        record = self._record(
            old["provider"],
            identity,
            new_access_token,
            new_refresh_token if new_refresh_token is not None else old.get("refresh_token"),
            old.get("scopes", []),
            expires_in,
            refresh_count=int(old.get("refresh_count", 0)) + 1,
            last_refreshed_at=_utcnow_iso(),
        )
        import json

        self._vault.store(self._service(provider), identity, json.dumps(record))
        _audit_vault(
            "oauth.refreshed",
            identity,
            {"provider": record["provider"], "refresh_count": record["refresh_count"]},
        )
        return {k: v for k, v in record.items() if k not in ("access_token", "refresh_token")}

    @staticmethod
    def is_expired(record: dict, skew_seconds: int = 60) -> bool:
        """True when the record's ``expires_at`` has passed (with skew).
        Records without an expiry never expire."""
        import time

        expires_at = record.get("expires_at")
        if expires_at is None:
            return False
        return time.time() >= float(expires_at) - skew_seconds

    def list_tokens(self, identity: Optional[str] = None) -> list:
        """Token metadata only — providers, identities, scopes, expiry,
        refresh counts. Token values are never listed."""
        out = []
        for service in self._vault.list_services():
            if not service.startswith(_OAUTH_NS + "."):
                continue
            provider = service[len(_OAUTH_NS) + 1:]
            try:
                entries = self._vault._load_entries().get(service, {})
            except VaultError:
                continue
            for ident in sorted(entries):
                if identity is not None and ident != identity:
                    continue
                try:
                    record = self._load(provider, ident)
                except OAuthError:
                    continue
                out.append(
                    {
                        "provider": provider,
                        "identity": ident,
                        "scopes": record.get("scopes", []),
                        "expires_at": record.get("expires_at"),
                        "expired": self.is_expired(record),
                        "refresh_count": record.get("refresh_count", 0),
                    }
                )
        return sorted(out, key=lambda r: (r["provider"], r["identity"]))

    def revoke(self, provider: str, identity: str, requester: str) -> None:
        """Delete a stored token set. Containment rules apply."""
        requester = _sanitize(requester, "requester")
        identity = _sanitize(identity, "identity")
        if requester != identity:
            raise OAuthError(
                f"containment: {requester!r} may not revoke {identity!r}'s tokens"
            )
        # Fail closed when nothing is stored (KeyError -> OAuthError).
        self._load(provider, identity)
        self._vault.delete(self._service(provider), identity)
        _audit_vault("oauth.revoked", identity, {"provider": _sanitize(provider, "provider")})


class AutoLockVault:
    """Auto-locking wrapper around :class:`CredentialVault`.

    The in-memory vault (and its derived key) is dropped after
    ``idle_seconds`` of inactivity; any operation past the deadline raises
    :class:`VaultLockedError` until :meth:`unlock` is called again with
    the passphrase. The passphrase itself is never retained — a locked
    vault can only be reopened by presenting it again.

    Honest limit: dropping the reference removes *our* handle on the key;
    CPython may keep the bytes in freed memory until the allocator reuses
    them. This is standard best-effort memory hygiene for a Python
    process, not a certified wipe.
    """

    def __init__(self, idle_seconds: float = 900):
        if (
            not isinstance(idle_seconds, (int, float))
            or isinstance(idle_seconds, bool)
            or idle_seconds <= 0
        ):
            raise VaultError("idle_seconds must be a positive number")
        self.__dict__["_idle"] = float(idle_seconds)
        self.__dict__["_vault"] = None
        self.__dict__["_deadline"] = 0.0

    def unlock(self, passphrase: str, directory: Optional[Path] = None) -> "AutoLockVault":
        import time

        self.__dict__["_vault"] = CredentialVault(passphrase, directory=directory)
        self.__dict__["_deadline"] = time.monotonic() + self.__dict__["_idle"]
        return self

    def lock(self) -> None:
        """Lock now: drop the in-memory vault and its derived key."""
        self.__dict__["_vault"] = None
        self.__dict__["_deadline"] = 0.0

    @property
    def is_locked(self) -> bool:
        import time

        vault = self.__dict__["_vault"]
        if vault is None:
            return True
        if time.monotonic() >= self.__dict__["_deadline"]:
            self.lock()
            return True
        return False

    def _checked(self):
        import time

        vault = self.__dict__["_vault"]
        if vault is None:
            raise VaultLockedError("vault is locked: call unlock(passphrase) first")
        if time.monotonic() >= self.__dict__["_deadline"]:
            self.lock()
            raise VaultLockedError(
                "vault auto-locked after inactivity: call unlock(passphrase) again"
            )
        self.__dict__["_deadline"] = time.monotonic() + self.__dict__["_idle"]
        return vault

    @property
    def backend(self) -> str:
        return self._checked().backend

    def __getattr__(self, name: str):
        # Only fires when normal attribute lookup fails — delegates every
        # CredentialVault operation through the idle check.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return getattr(self._checked(), name)
