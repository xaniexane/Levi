"""Veil-lineage sealing for the creator platform (SI side).

Lineage: the keeper's Veil (renamed from Void Box 2026-09-17) — sealed,
tamper-evident, keeper-held keys. This module implements the same family
of construction with stdlib only:

- Keeper key: 32 random bytes, owner-only file (0600), generated once.
- Encryption: XOR keystream from SHA-256 CTR (key || nonce || counter),
  key derived via HMAC-SHA256 HKDF-style from the keeper key.
- Authentication: Encrypt-then-MAC (HMAC-SHA256 over nonce + ciphertext
  + context). Any tampering with the envelope fails verification.

Honest limits: this is a sound Encrypt-then-MAC construction, not
AES-GCM. It protects records at rest on this machine against tampering
and casual reading. It does not protect against an attacker who can read
the keeper's memory or who already holds the key file.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

ALG = "VEIL1-HMAC-XOR"
_NONCE_BYTES = 16
_KEY_FILE = "keeper.key"


class SealError(ValueError):
    """A sealed envelope failed verification — tampered or wrong key."""


def _home_base(home: Optional[Path] = None) -> Path:
    return (Path(home) if home is not None else Path.home()) / ".levi" / "creator"


def _key_path(home: Optional[Path] = None) -> Path:
    return _home_base(home) / _KEY_FILE


def keeper_key(home: Optional[Path] = None) -> bytes:
    """Load or create the keeper key. The file is created mode 0600."""
    p = _key_path(home)
    if p.exists():
        data = p.read_bytes()
        if len(data) != 32:
            raise SealError("keeper key file is corrupt (wrong length)")
        return data
    p.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    # Create with restrictive perms from the start.
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    os.chmod(p, 0o600)
    return key


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out = b""
    t = b""
    counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def _keystream(key: bytes, nonce: bytes, nbytes: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < nbytes:
        out += hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        counter += 1
    return out[:nbytes]


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def seal_bytes(plaintext: bytes, key: bytes, context: str) -> Dict[str, Any]:
    """Seal plaintext into a tamper-evident envelope."""
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    nonce = os.urandom(_NONCE_BYTES)
    ct = bytes(a ^ b for a, b in zip(plaintext, _keystream(enc_key, nonce, len(plaintext))))
    mac = hmac.new(mac_key, nonce + ct + context.encode("utf-8"), hashlib.sha256).digest()
    return {
        "v": 1,
        "alg": ALG,
        "ctx": context,
        "nonce": _b64e(nonce),
        "ct": _b64e(ct),
        "mac": _b64e(mac),
    }


def open_bytes(envelope: Dict[str, Any], key: bytes, context: str) -> bytes:
    """Open an envelope. Raises SealError on any tampering or mismatch."""
    try:
        if envelope.get("v") != 1 or envelope.get("alg") != ALG:
            raise SealError("unknown envelope version/algorithm")
        if envelope.get("ctx") != context:
            raise SealError("envelope context mismatch")
        nonce = _b64d(envelope["nonce"])
        ct = _b64d(envelope["ct"])
        mac = _b64d(envelope["mac"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SealError("malformed envelope: %s" % exc) from exc
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    expect = hmac.new(mac_key, nonce + ct + context.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(expect, mac):
        raise SealError("envelope failed MAC verification — tampered or wrong key")
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    pt = bytes(a ^ b for a, b in zip(ct, _keystream(enc_key, nonce, len(ct))))
    return pt


def seal_record(record: Dict[str, Any], home: Optional[Path] = None, context: str = "creator/si") -> Dict[str, Any]:
    """Seal a JSON-able record. Returns the envelope dict."""
    key = keeper_key(home)
    plaintext = json.dumps(record, sort_keys=True).encode("utf-8")
    return seal_bytes(plaintext, key, context)


def open_record(envelope: Dict[str, Any], home: Optional[Path] = None, context: str = "creator/si") -> Dict[str, Any]:
    """Open a sealed record envelope. Raises SealError on tampering."""
    key = keeper_key(home)
    plaintext = open_bytes(envelope, key, context)
    return json.loads(plaintext.decode("utf-8"))
