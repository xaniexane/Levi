"""Portable signed reputation: attestations you hold and anyone can verify offline.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 2]

The mechanism: contribution history and endorsements become *attestations* —
small canonical documents signed by their issuer with an elliptic-curve
signature. The signature, issuer public key, and attestation travel
together, so verification needs nothing but this module: no account, no
host, no connectivity. Hold your reputation in a file; show it anywhere.

Cryptography, kept honest:

- ECDSA over secp256k1, written from scratch in pure Python on stdlib
  (hashlib/hmac/os only). The curve constants are public mathematics,
  not borrowed code. Deterministic nonces per RFC6979-style HMAC-SHA256,
  so signing never depends on a weak RNG — though key *generation* does
  use ``os.urandom``.
- This is a compact, readable implementation, not a hardened library.
  Verification is constant-effort math, but the code has not had a
  cryptographic audit; treat it as a working mechanism with honest
  limits, sized for portable reputation — not for custody of funds.
- Canonical encoding is sorted-key JSON; any byte change breaks the
  signature, which is exactly the tamper-evidence the feature promises.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/signed-reputation"

# -- secp256k1 parameters (public domain mathematics) ------------------------
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_A = 0
_B = 7
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
_G = (_GX, _GY)
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_H = 1


def _inv(a: int, p: int) -> int:
    return pow(a % p, p - 2, p)


def _point_add(p1, p2):
    """Add two curve points; None is the point at infinity."""
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1 + _A) * _inv(2 * y1, _P) % _P
    else:
        lam = (y2 - y1) * _inv(x2 - x1, _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _scalar_mult(k: int, point=_G):
    """Double-and-add scalar multiplication."""
    result = None
    addend = point
    k = k % _N
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _rfc6979(priv: bytes, msg_hash: bytes) -> int:
    """Deterministic nonce: HMAC-SHA256 construction in the RFC6979 spirit."""
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + priv + msg_hash, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + priv + msg_hash, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        candidate = int.from_bytes(v, "big")
        if 1 <= candidate < _N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def _hash_attestation(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


# -- keys --------------------------------------------------------------------
@dataclass(frozen=True)
class KeyPair:
    """A reputation identity: secret signing key + public verification key."""

    private: bytes  # 32 bytes, keep secret
    public: Tuple[int, int]  # curve point (x, y)

    @staticmethod
    def generate() -> "KeyPair":
        priv = int.from_bytes(os.urandom(32), "big") % (_N - 1) + 1
        return KeyPair.from_private(priv.to_bytes(32, "big"))

    @staticmethod
    def from_private(private: bytes) -> "KeyPair":
        if len(private) != 32:
            raise ValueError("private key must be 32 bytes")
        d = int.from_bytes(private, "big")
        if not 1 <= d < _N:
            raise ValueError("private key out of range")
        return KeyPair(private=private, public=_scalar_mult(d))

    def public_hex(self) -> str:
        x, y = self.public
        return f"{x:064x}{y:064x}"

    @staticmethod
    def public_from_hex(text: str) -> Tuple[int, int]:
        if len(text) != 128:
            raise ValueError("public key hex must be 128 chars (uncompressed x||y)")
        x = int(text[:64], 16)
        y = int(text[64:], 16)
        if (y * y - (x * x * x + _A * x + _B)) % _P != 0:
            raise ValueError("public key not on curve")
        return (x, y)

    def sign(self, message: bytes) -> Tuple[int, int]:
        digest = _hash_attestation(message)
        z = int.from_bytes(digest, "big")
        d = int.from_bytes(self.private, "big")
        while True:
            k = _rfc6979(self.private, digest)
            r_point = _scalar_mult(k)
            r = r_point[0] % _N
            if r == 0:
                continue
            s = (_inv(k, _N) * (z + r * d)) % _N
            if s == 0:
                continue
            return (r, s)

    @staticmethod
    def verify(public, message: bytes, signature: Tuple[int, int]) -> bool:
        r, s = signature
        if not 1 <= r < _N or not 1 <= s < _N:
            return False
        z = int.from_bytes(_hash_attestation(message), "big")
        w = _inv(s, _N)
        u1 = z * w % _N
        u2 = r * w % _N
        point = _point_add(_scalar_mult(u1), _scalar_mult(u2, public))
        return point is not None and point[0] % _N == r


# -- attestations ------------------------------------------------------------
@dataclass
class Attestation:
    """One signed reputation statement: contribution or endorsement."""

    issuer: str  # public_hex of the issuer
    subject: str  # public_hex of the person being attested
    kind: str  # "contribution" | "endorsement"
    payload: Dict = field(default_factory=dict)
    issued_at: float = field(default_factory=time.time)
    signature: Tuple[int, int] | None = None

    KINDS = ("contribution", "endorsement")

    def __post_init__(self):
        if self.kind not in self.KINDS:
            raise ValueError(f"kind must be one of {self.KINDS}")

    def canonical(self) -> bytes:
        doc = {
            "issuer": self.issuer,
            "subject": self.subject,
            "kind": self.kind,
            "payload": self.payload,
            "issued_at": self.issued_at,
        }
        return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_with(self, keypair: KeyPair) -> "Attestation":
        if keypair.public_hex() != self.issuer:
            raise ValueError("signing key does not match the attestation's issuer")
        self.signature = keypair.sign(self.canonical())
        return self

    def verify(self) -> bool:
        """Offline verification: signature + issuer match, nothing else needed."""
        if self.signature is None:
            return False
        public = KeyPair.public_from_hex(self.issuer)
        return KeyPair.verify(public, self.canonical(), self.signature)

    def to_dict(self) -> Dict:
        r, s = self.signature or (0, 0)
        return {
            "issuer": self.issuer,
            "subject": self.subject,
            "kind": self.kind,
            "payload": self.payload,
            "issued_at": self.issued_at,
            "signature": {"r": hex(r), "s": hex(s)},
        }

    @staticmethod
    def from_dict(doc: Dict) -> "Attestation":
        sig = doc.get("signature") or {}
        r = int(sig.get("r", "0x0"), 16)
        s = int(sig.get("s", "0x0"), 16)
        return Attestation(
            issuer=doc["issuer"],
            subject=doc["subject"],
            kind=doc["kind"],
            payload=doc.get("payload", {}),
            issued_at=doc.get("issued_at", 0.0),
            signature=(r, s) if (r, s) != (0, 0) else None,
        )


class ReputationWallet:
    """The user's held reputation: attestations in, offline verification out."""

    def __init__(self):
        self._attestations: List[Attestation] = []

    def add(self, attestation: Attestation) -> None:
        self._attestations.append(attestation)

    def endorsements_for(self, subject_hex: str) -> List[Attestation]:
        return [
            a
            for a in self._attestations
            if a.kind == "endorsement" and a.subject == subject_hex
        ]

    def contributions_for(self, subject_hex: str) -> List[Attestation]:
        return [
            a
            for a in self._attestations
            if a.kind == "contribution" and a.subject == subject_hex
        ]

    def verify_all(self) -> Dict[str, List[int]]:
        """Verify every held attestation offline; report indices by outcome."""
        valid: List[int] = []
        invalid: List[int] = []
        for i, att in enumerate(self._attestations):
            (valid if att.verify() else invalid).append(i)
        return {"valid": valid, "invalid": invalid}

    def export_portable(self) -> List[Dict]:
        """Serialize for display anywhere: JSON-safe dicts."""
        return [a.to_dict() for a in self._attestations]

    @staticmethod
    def import_portable(docs: List[Dict]) -> "ReputationWallet":
        wallet = ReputationWallet()
        for doc in docs:
            wallet.add(Attestation.from_dict(doc))
        return wallet
