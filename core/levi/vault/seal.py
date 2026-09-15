"""
Vault Seal — encrypt/decrypt local blobs (LEVI-original).

Fail-closed design: encryption is provided exclusively by the ``cryptography``
package's Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption).
Instantiating :class:`VaultSeal` without ``cryptography`` installed raises
``RuntimeError`` telling the user to ``pip install cryptography`` — there is
no XOR/plaintext-equivalent fallback.

Lock (key derivation): the passphrase is stretched with PBKDF2-HMAC-SHA256
(600,000 iterations) over a per-vault random 16-byte salt stored at
``<dir>/.salt`` (owner-only). A wrong passphrase raises :class:`VaultError`,
never a raw library exception.

Backwards compatibility: seals written by the original v1 scheme (single
unsalted SHA-256 of the passphrase) are still readable — decryption tries the
v2 key first, then the legacy v1 key. New seals are always written with v2.

The vault directory is restricted to the owner (0o700) at creation, and every
``.seal`` file (and the salt file) is written with owner-only permissions
(0o600). Entry names are restricted to ``[A-Za-z0-9_-]`` so a hostile name
can never escape the vault directory.

Not a substitute for a full HSM. Good enough for local private chat/notes at rest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import base64
import hashlib
import os
import re


DEFAULT_DIR = Path.home() / ".levi" / "vault"

_SALT_FILE = ".salt"
_SALT_LEN = 16
_PBKDF2_ITERATIONS = 600_000
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class VaultError(Exception):
    """The vault could not be unlocked or the request was invalid."""


def _sanitize_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise VaultError(
            "invalid vault entry name %r: use 1-64 chars of "
            "[A-Za-z0-9_-]" % (name,)
        )
    return name


class VaultSeal:
    def __init__(self, passphrase: str, directory: Optional[Path] = None):
        if not passphrase:
            raise ValueError("passphrase required")
        try:
            from cryptography.fernet import Fernet, InvalidToken  # type: ignore
            from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # type: ignore
                PBKDF2HMAC,
            )
            from cryptography.hazmat.primitives import hashes  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The 'cryptography' package is required for the vault seal. "
                "Install it with: pip install cryptography"
            ) from exc
        self._InvalidToken = InvalidToken
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        # Fail closed on permissions: vault directory owner-only, even if it
        # already existed with looser permissions.
        os.chmod(self.dir, 0o700)

        self._salt = self._load_or_create_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        self.key = kdf.derive(passphrase.encode("utf-8"))
        # Legacy v1 key (unsalted SHA-256) — read-only fallback so seals
        # written before the PBKDF2 upgrade remain openable.
        self._legacy_key = hashlib.sha256(passphrase.encode("utf-8")).digest()

        self._fernet = Fernet(base64.urlsafe_b64encode(self.key))
        self._legacy_fernet = Fernet(base64.urlsafe_b64encode(self._legacy_key))

    # -- key material ------------------------------------------------------

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
        tmp = self.dir / (_SALT_FILE + ".tmp")
        tmp.write_bytes(salt)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        return salt

    # -- primitives --------------------------------------------------------

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        try:
            return self._fernet.decrypt(data)
        except self._InvalidToken:
            pass
        try:
            return self._legacy_fernet.decrypt(data)
        except self._InvalidToken:
            pass
        raise VaultError(
            "cannot unlock vault entry: wrong passphrase or corrupted data"
        )

    # -- entries -----------------------------------------------------------

    def put(self, name: str, text: str) -> Path:
        name = _sanitize_name(name)
        path = self.dir / f"{name}.seal"
        # Atomic, owner-only from creation: write to a temp file opened with
        # 0o600 (no window with default permissions), then rename over the
        # target — same pattern as the salt file.
        tmp = self.dir / f"{name}.seal.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(self.encrypt_bytes(text.encode("utf-8")))
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp, path)
        return path

    def get(self, name: str) -> str:
        name = _sanitize_name(name)
        path = self.dir / f"{name}.seal"
        if not path.exists():
            raise FileNotFoundError(name)
        return self.decrypt_bytes(path.read_bytes()).decode("utf-8")

    def list_names(self) -> list:
        return [p.stem for p in self.dir.glob("*.seal")]
