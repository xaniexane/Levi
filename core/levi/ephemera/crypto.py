"""Ephemeral messaging crypto — honest, local, best-effort.

HONESTY NOTE (read before relying on this): stdlib Python has no
authenticated cipher (no AES-GCM, no ChaCha20-Poly1305). What this module
provides is a *composition of reviewed primitives*:

- Key derivation: PBKDF2-HMAC-SHA256 (hashlib.pbkdf2_hmac), 210_000
  iterations — genuinely strong password/passphrase stretching.
- Encryption: SHA-256 in CTR mode as a stream cipher (real: preimage
  resistance of SHA-256), plus HMAC-SHA256 over (nonce || ciphertext) as
  the MAC (real: unforgeability of HMAC).

What is NOT true: this is not a reviewed AEAD construction, not a
substitute for libsodium or a audited library, and not a claim of
"military-grade E2EE". There is no peer key exchange here at all —
encryption is AT REST, on your own machine, against disk-level
snooping (stolen laptop, nosy sync tool, backups you forgot about).
It defeats casual plaintext greps, not a motivated cryptanalyst with
chosen-plaintext access.

Threat model this DOES defeat: plaintext on disk; an exfiltrated
JSON file without the key.
Threat model this does NOT defeat: key compromise, memory forensics,
screenshots, the other endpoint, the NSA.

Use accordingly.
"""

from __future__ import annotations

import hashlib
import hmac
import os

# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

KDF_ITERATIONS = 210_000
KEY_LEN = 32  # 256-bit keys throughout


def derive_key(
    passphrase: bytes, salt: bytes, iterations: int = KDF_ITERATIONS
) -> bytes:
    """PBKDF2-HMAC-SHA256 key derivation (a reviewed primitive)."""
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, iterations, dklen=KEY_LEN)


def new_salt(n: int = 16) -> bytes:
    return os.urandom(n)


# ---------------------------------------------------------------------------
# Stream cipher: SHA-256 CTR (best-effort composition — see module docstring)
# ---------------------------------------------------------------------------


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:length])


def seal(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt+MAC. Returns nonce(12) || ciphertext || mac(32)."""
    if len(key) != KEY_LEN:
        raise ValueError("key must be 32 bytes")
    nonce = os.urandom(12)
    stream = _keystream(key, nonce, len(plaintext))
    ct = bytes(p ^ s for p, s in zip(plaintext, stream))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return nonce + ct + mac


def open_seal(key: bytes, blob: bytes) -> bytes:
    """Verify MAC, then decrypt. Raises ValueError on any tampering."""
    if len(key) != KEY_LEN:
        raise ValueError("key must be 32 bytes")
    if len(blob) < 12 + 32:
        raise ValueError("sealed blob too short")
    nonce, ct, mac = blob[:12], blob[12:-32], blob[-32:]
    expect = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(expect, mac):
        raise ValueError("MAC verification failed — blob tampered or wrong key")
    stream = _keystream(key, nonce, len(ct))
    return bytes(c ^ s for c, s in zip(ct, stream))


def chain_hash(prev: bytes, record: bytes) -> bytes:
    """Hash-chain link: H(prev || record). Used for deletion receipts."""
    return hashlib.sha256(prev + record).digest()
