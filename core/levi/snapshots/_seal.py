"""Veil-lineage sealing, snapshots-scoped.

Same construction family as the creator platform's seal: keeper-held
32-byte key (0600, generated once), XOR keystream from SHA-256 CTR,
Encrypt-then-MAC (HMAC-SHA256 over nonce + ciphertext + context).
Kept self-contained so the snapshot engine has no cross-module
dependencies — the engine is meant to be reusable anywhere.

Honest limits: sound Encrypt-then-MAC, not AES-GCM. Protects records
at rest on this machine against tampering and casual reading. Does
not stop an attacker who holds the key file or reads keeper memory.
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


def _key_path(home: Optional[Path]) -> Path:
    return home / _KEY_FILE


def keeper_key(home: Path) -> bytes:
    """Load or create the keeper key. The file is created mode 0600."""
    p = _key_path(home)
    if p.exists():
        data = p.read_bytes()
        if len(data) != 32:
            raise SealError("keeper key file is corrupt (wrong length)")
        return data
    p.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
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


def seal_bytes(plaintext: bytes, key: bytes, context: str) -> Dict[str, Any]:
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    nonce = os.urandom(_NONCE_BYTES)
    ks = _keystream(enc_key, nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks))
    mac = hmac.new(mac_key, nonce + ct + context.encode("utf-8"), hashlib.sha256).digest()
    return {
        "v": 1,
        "alg": ALG,
        "ctx": context,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
        "mac": base64.b64encode(mac).decode("ascii"),
    }


def open_bytes(envelope: Dict[str, Any], key: bytes, context: str) -> bytes:
    try:
        if envelope.get("v") != 1 or envelope.get("alg") != ALG:
            raise SealError("unknown envelope version/algorithm")
        if envelope.get("ctx") != context:
            raise SealError("envelope context mismatch")
        nonce = base64.b64decode(envelope["nonce"].encode("ascii"))
        ct = base64.b64decode(envelope["ct"].encode("ascii"))
        mac = base64.b64decode(envelope["mac"].encode("ascii"))
    except (KeyError, TypeError, ValueError) as exc:
        raise SealError("malformed envelope: %s" % exc) from exc
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    expect = hmac.new(mac_key, nonce + ct + context.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(expect, mac):
        raise SealError("envelope failed MAC verification — tampered or wrong key")
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    ks = _keystream(enc_key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))
