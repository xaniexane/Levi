"""
Vault Seal — encrypt/decrypt local blobs (LEVI-original).

Fail-closed design: encryption is provided exclusively by the ``cryptography``
package's Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption).
Instantiating :class:`VaultSeal` without ``cryptography`` installed raises
``RuntimeError`` telling the user to ``pip install cryptography`` — there is
no XOR/plaintext-equivalent fallback.

The vault directory is restricted to the owner (0o700) at creation, and every
``.seal`` file is written with owner-only permissions (0o600).

Not a substitute for a full HSM. Good enough for local private chat/notes at rest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import hashlib
import base64
import os


DEFAULT_DIR = Path.home() / ".levi" / "vault"


class VaultSeal:
    def __init__(self, passphrase: str, directory: Optional[Path] = None):
        if not passphrase:
            raise ValueError("passphrase required")
        try:
            from cryptography.fernet import Fernet  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The 'cryptography' package is required for the vault seal. "
                "Install it with: pip install cryptography"
            ) from exc
        self.key = hashlib.sha256(passphrase.encode("utf-8")).digest()
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        # Fail closed on permissions: vault directory owner-only, even if it
        # already existed with looser permissions.
        os.chmod(self.dir, 0o700)
        fkey = base64.urlsafe_b64encode(self.key)
        self._fernet = Fernet(fkey)

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)

    def put(self, name: str, text: str) -> Path:
        path = self.dir / f"{name}.seal"
        path.write_bytes(self.encrypt_bytes(text.encode("utf-8")))
        os.chmod(path, 0o600)
        return path

    def get(self, name: str) -> str:
        path = self.dir / f"{name}.seal"
        if not path.exists():
            raise FileNotFoundError(name)
        return self.decrypt_bytes(path.read_bytes()).decode("utf-8")

    def list_names(self) -> list:
        return [p.stem for p in self.dir.glob("*.seal")]
