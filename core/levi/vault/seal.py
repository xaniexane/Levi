"""
Vault Seal — encrypt/decrypt local blobs (LEVI-original).

Uses stdlib hashlib + a simple XOR stream derived from passphrase when
cryptography package is unavailable; prefers Fernet if installed.

Not a substitute for full HSM. Good enough for local private chat/notes at rest.
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
        self.key = hashlib.sha256(passphrase.encode("utf-8")).digest()
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._fernet = None
        try:
            from cryptography.fernet import Fernet  # type: ignore

            fkey = base64.urlsafe_b64encode(self.key)
            self._fernet = Fernet(fkey)
        except Exception:
            self._fernet = None

    def _xor(self, data: bytes) -> bytes:
        key = self.key
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def encrypt_bytes(self, data: bytes) -> bytes:
        if self._fernet:
            return self._fernet.encrypt(data)
        # prefix version byte for XOR path
        return b"X1" + self._xor(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        if self._fernet and not data.startswith(b"X1"):
            return self._fernet.decrypt(data)
        if data.startswith(b"X1"):
            return self._xor(data[2:])
        if self._fernet:
            return self._fernet.decrypt(data)
        return self._xor(data)

    def put(self, name: str, text: str) -> Path:
        path = self.dir / f"{name}.seal"
        path.write_bytes(self.encrypt_bytes(text.encode("utf-8")))
        return path

    def get(self, name: str) -> str:
        path = self.dir / f"{name}.seal"
        if not path.exists():
            raise FileNotFoundError(name)
        return self.decrypt_bytes(path.read_bytes()).decode("utf-8")

    def list_names(self) -> list:
        return [p.stem for p in self.dir.glob("*.seal")]
