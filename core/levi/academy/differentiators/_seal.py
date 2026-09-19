"""Veil-lineage sealing, academy scope.

Same construction family as the keeper's Veil (renamed from Void Box):
keeper-held 32-byte key (0600), HKDF-derived subkeys, SHA-256 CTR
keystream XOR, Encrypt-then-MAC. Sealed here so the academy never
depends on the creator platform — same math, separate key, separate
home (``<LEVI_HOME>/academy/differentiators/``).

Honest limits: sound Encrypt-then-MAC, not AES-GCM. Protects records
at rest on this machine. Does not stop a key-file holder.
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


def pkg_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (Path(home) if home is not None else Path(base).expanduser())
    d = d / "academy" / "differentiators"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _key_path(home: Optional[Path] = None) -> Path:
    return pkg_dir(home) / _KEY_FILE


def keeper_key(home: Optional[Path] = None) -> bytes:
    p = _key_path(home)
    if p.exists():
        data = p.read_bytes()
        if len(data) != 32:
            raise SealError("keeper key file is corrupt (wrong length)")
        return data
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


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def seal_dict(payload: Dict[str, Any], context: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Seal a JSON-able dict into a tamper-evident envelope."""
    key = keeper_key(home)
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    plaintext = _canonical(payload)
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


def open_dict(envelope: Dict[str, Any], context: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Open an envelope. Raises SealError on any tampering or mismatch."""
    key = keeper_key(home)
    try:
        if envelope.get("v") != 1 or envelope.get("alg") != ALG:
            raise SealError("unknown envelope version/algorithm")
        if envelope.get("ctx") != context:
            raise SealError("envelope context mismatch")
        nonce = _b64d(envelope["nonce"])
        ct = _b64d(envelope["ct"])
        mac = _b64d(envelope["mac"])
    except (KeyError, ValueError, TypeError) as exc:
        raise SealError(f"malformed envelope: {exc}") from exc
    mac_key = _hkdf(key, b"veil1-mac", context.encode("utf-8"), 32)
    expect = hmac.new(mac_key, nonce + ct + context.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(expect, mac):
        raise SealError("envelope MAC mismatch — tampered or wrong key")
    enc_key = _hkdf(key, b"veil1-enc", context.encode("utf-8"), 32)
    plaintext = bytes(a ^ b for a, b in zip(ct, _keystream(enc_key, nonce, len(ct))))
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SealError(f"envelope payload corrupt: {exc}") from exc
    if not isinstance(payload, dict):
        raise SealError("envelope payload is not a dict")
    return payload
