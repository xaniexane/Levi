"""Sealed envelopes — lightweight encrypted-at-rest text blobs for the keeper.

LEVI-native recreation of the keeper's "vault seal" idea, raised to the
house crypto posture: PBKDF2-HMAC-SHA256 key derivation over a random
per-envelope salt, HMAC-SHA256 counter-mode stream cipher with
verify-then-decrypt authentication, Fernet (``cryptography`` package)
preferred when installed — real authenticated encryption.

This sits next to, not inside, ``levi.cybrus.vault.CredentialVault``:
the vault is a structured credential store (service -> username ->
secret); envelopes are free-form text the keeper seals away (private
notes, exported chat excerpts, drafts) and unseals later.

Legacy migration: envelopes written by the keeper's earlier seal tool
(``X1`` prefix, unsalted SHA-256(passphrase) XOR stream) remain READABLE
with the same passphrase so old files survive; ``migrate()`` re-seals
them into the current format. The old format is never WRITTEN.

Fail closed: wrong passphrase or a tampered envelope raises
:class:`SealError`, never garbage plaintext.

Crypto posture, stated plainly:
- Fernet backend: AES-128-CBC + HMAC-SHA256 authenticated encryption via
  the ``cryptography`` package.
- Stdlib fallback: PBKDF2-HMAC-SHA256 (260,000 iterations) -> HMAC-
  SHA256(counter) keystream. Documented honestly as fallback-grade,
  NOT AES. A Fernet envelope opened without ``cryptography`` fails
  closed with a clear error.
- Envelope layout is self-describing, so a blob written by either
  backend opens under the other.

Stdlib-only in this file's imports (``cryptography`` is optional).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from pathlib import Path
from typing import Optional

# Self-describing envelope schemes.
_SCHEME_FERNET = b"LSF1"  # Fernet envelope
_SCHEME_STDLIB = b"LS1"  # stdlib fallback envelope
_SCHEME_LEGACY = b"X1"  # keeper's earlier seal tool (read-only)

_SALT_LEN = 16
_NONCE_LEN = 16
_TAG_LEN = 32
_PBKDF2_ITERATIONS = 260_000
_DOMAIN = b"levi-cybrus-seal-v1"
_FERNET_SALT = b"levi-cybrus-seal-fernet"

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def _default_dir() -> Path:
    home = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return home / "cybrus" / "envelopes"


class SealError(Exception):
    """The envelope could not be opened (wrong passphrase, tampered, or
    unreadable format)."""


class SealedEnvelope:
    """Passphrase-sealed text envelopes at rest."""

    def __init__(self, passphrase: str, directory: Optional[Path] = None):
        if not passphrase:
            raise ValueError("passphrase required")
        self._pw = passphrase.encode("utf-8")
        self.dir = Path(directory) if directory else _default_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self._fernet = None
        try:
            from cryptography.fernet import Fernet  # type: ignore

            raw = hashlib.pbkdf2_hmac(
                "sha256", self._pw, _FERNET_SALT, _PBKDF2_ITERATIONS
            )
            self._fernet = Fernet(base64.urlsafe_b64encode(raw))
        except Exception:
            self._fernet = None

    @property
    def backend(self) -> str:
        return "fernet" if self._fernet is not None else "stdlib-fallback"

    # -- primitives -----------------------------------------------------
    def _derive(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._pw, salt, _PBKDF2_ITERATIONS)

    @staticmethod
    def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            out.extend(
                hmac.new(
                    key,
                    _DOMAIN + nonce + counter.to_bytes(4, "big"),
                    hashlib.sha256,
                ).digest()
            )
            counter += 1
        return bytes(out[:length])

    def _seal_stdlib(self, data: bytes) -> bytes:
        salt = os.urandom(_SALT_LEN)
        nonce = os.urandom(_NONCE_LEN)
        key = self._derive(salt)
        ct = bytes(a ^ b for a, b in zip(data, self._keystream(key, nonce, len(data))))
        tag = hmac.new(key, _DOMAIN + salt + nonce + ct, hashlib.sha256).digest()
        return _SCHEME_STDLIB + salt + nonce + tag + ct

    def _open_stdlib(self, blob: bytes) -> bytes:
        head = len(_SCHEME_STDLIB) + _SALT_LEN + _NONCE_LEN + _TAG_LEN
        if len(blob) < head:
            raise SealError("truncated envelope")
        salt = blob[3 : 3 + _SALT_LEN]
        nonce = blob[3 + _SALT_LEN : 3 + _SALT_LEN + _NONCE_LEN]
        tag = blob[3 + _SALT_LEN + _NONCE_LEN : head]
        ct = blob[head:]
        key = self._derive(salt)
        want = hmac.new(key, _DOMAIN + salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, want):
            raise SealError(
                "authentication failed (wrong passphrase or tampered envelope)"
            )
        ks = self._keystream(key, nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, ks))

    def _open_legacy(self, blob: bytes) -> bytes:
        # Keeper's earlier seal: raw XOR under SHA-256(passphrase). Read-only.
        key = hashlib.sha256(self._pw).digest()
        data = blob[len(_SCHEME_LEGACY) :]
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    # -- envelope API ----------------------------------------------------
    def seal_bytes(self, data: bytes) -> bytes:
        if self._fernet is not None:
            return _SCHEME_FERNET + self._fernet.encrypt(data)
        return self._seal_stdlib(data)

    def open_bytes(self, blob: bytes) -> bytes:
        if blob.startswith(_SCHEME_LEGACY):
            return self._open_legacy(blob)
        if blob.startswith(_SCHEME_FERNET):
            if self._fernet is None:
                raise SealError("Fernet envelope requires the cryptography package")
            try:
                return self._fernet.decrypt(blob[len(_SCHEME_FERNET) :])
            except Exception as e:
                raise SealError(f"fernet open failed: {e}") from e
        if blob.startswith(_SCHEME_STDLIB):
            return self._open_stdlib(blob)
        raise SealError("unrecognized envelope format")

    def _path(self, name: str) -> Path:
        if not _NAME_RE.fullmatch(name or ""):
            raise ValueError(f"unsafe envelope name: {name!r}")
        return self.dir / f"{name}.envelope"

    def seal_text(self, name: str, text: str) -> Path:
        path = self._path(name)
        path.write_bytes(self.seal_bytes(text.encode("utf-8")))
        os.chmod(path, 0o600)
        return path

    def open_text(self, name: str) -> str:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"no sealed envelope: {name}")
        return self.open_bytes(path.read_bytes()).decode("utf-8")

    def list_names(self) -> list:
        return [p.stem for p in sorted(self.dir.glob("*.envelope"))]

    def migrate(self, name: str) -> bool:
        """Re-seal a legacy ``X1`` envelope into the current format.
        Returns True when the envelope was legacy and got rewritten."""
        path = self._path(name)
        raw = path.read_bytes()
        if not raw.startswith(_SCHEME_LEGACY):
            return False
        text = self._open_legacy(raw).decode("utf-8")
        self.seal_text(name, text)
        return True
