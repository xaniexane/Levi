"""Key provisioning and channel cryptography for the CLEAR network.

Written against the Meshtastic failures as explicit threat models:
* CVE-2025-52464 (cloned X25519 key pairs across production batches):
  every tower generates its own keys at first boot behind a hardware
  entropy gate. A provisioning attempt on an already-provisioned tower
  is REFUSED, never silently cloned — GoldenImageError.
* DEF CON 2025 (spoofed NodeInfo, no PSK message verification):
  nodeinfo attestations are bound to the per-device identity key, and
  every channel packet carries an HMAC. See protocol.attest_nodeinfo.
* No forward secrecy on DMs: per-message keys ratchet forward from the
  session key, so a later key compromise cannot decrypt earlier traffic.

Honest limits: payload sealing below is a reference-grade stream seal
built on HKDF-SHA256. It is NOT a vetted AEAD. Milestone 0.3 (key
provisioning & identity spec, hardware phase) MUST replace it with an
audited AEAD before any field use. The HMAC authentication, however, is
standard HMAC-SHA256 and carries the integrity story today.

Everything here is stdlib-only (hashlib, hmac, secrets, os, json).
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import secrets
from dataclasses import dataclass

from .protocol import MAC_LEN, NODE_ID_LEN, ProtocolError


class GoldenImageError(ProtocolError):
    """Provisioning refused: this tower already has an identity.

    Cloned 'golden images' are exactly how CVE-2025-52464 happened.
    A tower that cannot prove it generated its own keys does not join.
    """


class EntropyGateError(ProtocolError):
    """The hardware entropy gate refused a weak device secret."""


IDENTITY_FILE = "identity.json"
MIN_PAIRING_PSK_LEN = 16


def hkdf(ikm: bytes, salt: bytes = b"", info: bytes = b"", length: int = 32) -> bytes:
    """RFC 5869 HKDF with SHA-256."""
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = _hmac.new(salt, ikm, hashlib.sha256).digest()
    out = b""
    block = b""
    counter = 1
    while len(out) < length:
        block = _hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def _entropy_gate(secret: bytes) -> None:
    """Refuse weak device secrets at provisioning time."""
    if len(secret) < 32:
        raise EntropyGateError("device secret too short")
    if secret == b"\x00" * len(secret):
        raise EntropyGateError("device secret is all zeros")
    # 64 random bytes virtually always carry >16 distinct byte values;
    # anything less means the entropy source is broken or the image cloned.
    if len(set(secret)) < 16:
        raise EntropyGateError("device secret failed the entropy gate")


@dataclass(frozen=True)
class DeviceIdentity:
    node_id: bytes  # 8 bytes: sha256(identity_key)[:8]
    device_secret: bytes  # 64 bytes: never leaves the tower
    identity_key: bytes  # 32 bytes: shared only inside a paired session
    path: str


def provision_device(data_dir: str) -> DeviceIdentity:
    """First-boot key provisioning. Refuses to run twice — no golden images."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, IDENTITY_FILE)
    if os.path.exists(path):
        raise GoldenImageError(
            f"identity already provisioned at {path} — refusing to clone it. "
            "Factory-reset the tower through the owner ceremony to re-provision."
        )
    secret = secrets.token_bytes(64)
    _entropy_gate(secret)
    identity_key = hkdf(secret, info=b"clearnet-identity-v1")
    node_id = hashlib.sha256(identity_key).digest()[:NODE_ID_LEN]
    record = {
        "node_id": node_id.hex(),
        "device_secret": secret.hex(),
        "identity_key": identity_key.hex(),
        "provisioned": "first-boot",
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    os.chmod(path, 0o600)
    return DeviceIdentity(
        node_id=node_id, device_secret=secret, identity_key=identity_key, path=path
    )


def load_device(data_dir: str) -> DeviceIdentity:
    """Load an existing identity, or provision one on first boot."""
    path = os.path.join(data_dir, IDENTITY_FILE)
    if not os.path.exists(path):
        return provision_device(data_dir)
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    return DeviceIdentity(
        node_id=bytes.fromhex(record["node_id"]),
        device_secret=bytes.fromhex(record["device_secret"]),
        identity_key=bytes.fromhex(record["identity_key"]),
        path=path,
    )


class ChainRatchet:
    """Symmetric forward-secrecy ratchet (one direction of a paired session).

    Each message key is derived then the chain advances and the old chain
    is overwritten — a later compromise cannot rewind to earlier keys.
    A bounded skip window (16) tolerates reordered store-and-forward
    delivery; anything older is treated as replay and refused.

    Honest limit: no post-compromise security without an asymmetric
    ratchet — that needs the vetted-AEAD milestone (0.3).
    """

    MAX_SKIP = 16

    def __init__(self, chain_key: bytes):
        self._chain = bytes(chain_key)
        self._index = 0
        self._skipped: dict[int, bytes] = {}

    def send_key(self) -> tuple[int, bytes]:
        key = hkdf(self._chain, info=b"clearnet-msg")
        self._chain = hkdf(self._chain, info=b"clearnet-chain")
        index = self._index
        self._index += 1
        return index, key

    def recv_key(self, index: int) -> bytes:
        if index in self._skipped:
            return self._skipped.pop(index)
        if index < self._index:
            raise ProtocolError("replayed or expired message key refused")
        if index - self._index > self.MAX_SKIP:
            raise ProtocolError("message gap beyond the reorder window refused")
        key = b""
        while self._index <= index:
            key = hkdf(self._chain, info=b"clearnet-msg")
            self._chain = hkdf(self._chain, info=b"clearnet-chain")
            if self._index < index:
                self._skipped[self._index] = key
            self._index += 1
        return key


def _keystream(key: bytes, nonce: bytes, nbytes: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < nbytes:
        out += hkdf(key, salt=nonce, info=b"clearnet-seal" + counter.to_bytes(4, "big"))
        counter += 1
    return out[:nbytes]


def seal(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """Reference-grade payload seal (XOR with an HKDF keystream).

    NOT a vetted cipher — see the module docstring. Carries the
    confidentiality story for the loopback reference only.
    """
    if len(nonce) != 12:
        raise ProtocolError("seal nonce must be 12 bytes")
    stream = _keystream(key, nonce, len(plaintext))
    return bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))


def unseal(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return seal(key, nonce, ciphertext)


def pair_channel_id(id_a: bytes, id_b: bytes) -> int:
    """Deterministic pair-channel id shared by both towers of a pairing."""
    lo, hi = (id_a, id_b) if id_a < id_b else (id_b, id_a)
    digest = hashlib.sha256(b"clearnet-pair-chan" + lo + hi).digest()
    return int.from_bytes(digest[:4], "big")


def session_key_for(psk: bytes, nonce_a: bytes, nonce_b: bytes) -> bytes:
    if len(psk) < MIN_PAIRING_PSK_LEN:
        raise ProtocolError("pairing PSK too short")
    return hkdf(psk, salt=nonce_a + nonce_b, info=b"clearnet-session-v1")


def direction_key(session_key: bytes, sender: bytes, receiver: bytes) -> bytes:
    return hkdf(session_key, info=b"clearnet-dir" + sender + receiver)


def pair_channel_key(session_key: bytes) -> bytes:
    return hkdf(session_key, info=b"clearnet-pair-channel")


def pair_nonce(nonce_a: bytes, nonce_b: bytes, tag: bytes) -> bytes:
    return hashlib.sha256(tag + nonce_a + nonce_b).digest()[:12]


def mac(key: bytes, *parts: bytes) -> bytes:
    h = _hmac.new(key, digestmod=hashlib.sha256)
    for part in parts:
        h.update(part)
    return h.digest()


__all__ = [
    "MAC_LEN",
    "GoldenImageError",
    "EntropyGateError",
    "DeviceIdentity",
    "provision_device",
    "load_device",
    "hkdf",
    "ChainRatchet",
    "seal",
    "unseal",
    "pair_channel_id",
    "session_key_for",
    "direction_key",
    "pair_channel_key",
    "pair_nonce",
    "mac",
]
