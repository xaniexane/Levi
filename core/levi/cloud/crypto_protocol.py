"""
Crypto protocol for Phase B — Argon2id (CMK) + Signal-style Double Ratchet (sessions).

They solve different problems:
  Argon2id  = memory-hard KDF: passphrase → content master key at rest
  Ratchet   = session keys evolve so one leak does not open whole history

Production: reviewed libsignal (or equivalent) + argon2-cffi / libsodium.
This module is the *protocol spec + safe local demo* — not a home-grown production ratchet.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
import hashlib
import hmac
import os
import secrets


@dataclass(frozen=True)
class Argon2idPolicy:
    """Memory-hard KDF policy for content master key derivation."""

    name: str
    memory_mib: int
    time_cost: int
    parallelism: int
    purpose: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


BASELINE_CMK = Argon2idPolicy(
    name="baseline",
    memory_mib=64,
    time_cost=3,
    parallelism=4,
    purpose="interactive content master key (CMK) from passphrase",
)

ARCHIVAL_RECOVERY = Argon2idPolicy(
    name="archival",
    memory_mib=256,
    time_cost=4,
    parallelism=4,
    purpose="recovery key hardening",
)


class Argon2idGuide:
    """Derive a CMK. Prefer argon2-cffi; fall back to labeled HMAC demo."""

    def __init__(self, policy: Argon2idPolicy = BASELINE_CMK):
        self.policy = policy
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        try:
            import argon2  # noqa: F401

            return "argon2-cffi"
        except Exception:
            try:
                import nacl  # noqa: F401

                return "libsodium-pwhash"
            except Exception:
                return "demo-hmac-fallback"

    @property
    def backend(self) -> str:
        return self._backend

    def is_production_ready(self) -> bool:
        return self._backend in ("argon2-cffi", "libsodium-pwhash")

    def derive_cmk(
        self, passphrase: str, salt: Optional[bytes] = None
    ) -> Tuple[bytes, bytes, str]:
        """
        Returns (cmk_32bytes, salt, backend_label).
        Demo path is clearly labeled — not pretended to be Argon2.
        """
        if not passphrase:
            raise ValueError("passphrase required")
        salt = salt or os.urandom(16)

        if self._backend == "argon2-cffi":
            from argon2.low_level import hash_secret_raw, Type

            cmk = hash_secret_raw(
                secret=passphrase.encode("utf-8"),
                salt=salt,
                time_cost=self.policy.time_cost,
                memory_cost=self.policy.memory_mib * 1024,
                parallelism=self.policy.parallelism,
                hash_len=32,
                type=Type.ID,
            )
            return cmk, salt, "argon2id"

        if self._backend == "libsodium-pwhash":
            from nacl import pwhash

            # opslimit/memlimit approximate policy
            cmk = pwhash.argon2id.kdf(
                32,
                passphrase.encode("utf-8"),
                salt[:16] if len(salt) >= 16 else salt.ljust(16, b"\0"),
                opslimit=pwhash.argon2id.OPSLIMIT_MODERATE,
                memlimit=pwhash.argon2id.MEMLIMIT_MODERATE,
            )
            return cmk, salt, "argon2id-libsodium"

        # Explicit demo fallback — NOT Argon2
        material = hmac.new(
            salt,
            passphrase.encode("utf-8") + self.policy.name.encode(),
            hashlib.sha256,
        ).digest()
        # stretch a few rounds so it is obviously a demo, not a password hash
        for i in range(8):
            material = hmac.new(
                material, str(i).encode() + salt, hashlib.sha256
            ).digest()
        return material, salt, "DEMO_HMAC_FALLBACK_NOT_ARGON2"

    def status_block(self) -> str:
        lines = [
            "Argon2id — content master key (CMK) at rest",
            f"  backend: {self.backend}"
            + (
                "  ✓ production path"
                if self.is_production_ready()
                else "  ⚠ demo HMAC only — install argon2-cffi"
            ),
            f"  baseline: {BASELINE_CMK.memory_mib} MiB · t={BASELINE_CMK.time_cost} · p={BASELINE_CMK.parallelism}",
            f"  archival: {ARCHIVAL_RECOVERY.memory_mib} MiB · t={ARCHIVAL_RECOVERY.time_cost} · p={ARCHIVAL_RECOVERY.parallelism}",
            "  job: passphrase → CMK for sealed ~/.levi blobs",
            "  not: session protocol (see Double Ratchet)",
        ]
        return "\n".join(lines)


class RatchetGuide:
    """
    Signal-style session protocol *guide* + educational HMAC chain demo.

    Production: use reviewed libsignal (or equivalent).
    Local demo: simplified HMAC chain for tests/education only — labeled clearly.
    """

    def __init__(self) -> None:
        self._demo_chains: Dict[str, bytes] = {}

    def protocol_block(self) -> str:
        return "\n".join(
            [
                "Signal protocol ratcheting (Phase B guide)",
                "  X3DH — X25519 identity / ephemeral / prekeys → initial shared secret",
                "  Double Ratchet — DH ratchet + symmetric chain; one message key per message",
                "  properties: forward secrecy + post-compromise recovery when DH steps continue",
                "  production: reviewed libsignal (or equivalent) — NOT home-grown in app code",
                "  local demo: simplified HMAC chain (tests/education only)",
            ]
        )

    def demo_init_session(
        self, session_id: str, root_key: Optional[bytes] = None
    ) -> str:
        """Educational only. Returns status string."""
        rk = root_key or secrets.token_bytes(32)
        self._demo_chains[session_id] = rk
        return f"demo session {session_id[:12]}… root established (HMAC chain — NOT libsignal)"

    def demo_next_message_key(self, session_id: str) -> Tuple[bytes, str]:
        if session_id not in self._demo_chains:
            raise KeyError("unknown demo session — call demo_init_session first")
        chain = self._demo_chains[session_id]
        mk = hmac.new(chain, b"msg", hashlib.sha256).digest()
        # advance chain
        self._demo_chains[session_id] = hmac.new(
            chain, b"chain", hashlib.sha256
        ).digest()
        return mk, "DEMO_HMAC_CHAIN_NOT_SIGNAL"

    def status_block(self) -> str:
        return (
            self.protocol_block() + f"\n  open demo sessions: {len(self._demo_chains)}"
        )


class CryptoProtocol:
    """Unified Phase B crypto surface for CLI / ops."""

    STANDARDS = [
        "X25519 / Ed25519",
        "ChaCha20-Poly1305 or AES-256-GCM",
        "HKDF-SHA-256 · Argon2id for passphrases",
        "TLS 1.3 only on the wire",
        "age / libsodium for blob envelopes",
    ]
    AVOID = [
        "TLS 1.0 / 1.1",
        "MD5 / SHA-1",
        "home-grown production ratchet",
        "server-held content keys by default",
    ]

    def __init__(self) -> None:
        self.argon = Argon2idGuide()
        self.ratchet = RatchetGuide()

    def complement_block(self) -> str:
        return "\n".join(
            [
                "How they complement each other",
                "  Piece          Job",
                "  Argon2id       Memory-hard KDF: passphrase → CMK at rest",
                "  Double Ratchet Session keys evolve so one leak doesn’t open whole history",
                "",
                "  Argon2id is not a session protocol; the ratchet is not a password KDF.",
                "  Refinement: CMK for sealed ~/.levi blobs; ratchet keys for device pairing / sync control-plane.",
            ]
        )

    def full_report(self) -> str:
        lines = [
            "══ LEVI Phase B crypto protocol ══",
            "",
            self.complement_block(),
            "",
            self.argon.status_block(),
            "",
            self.ratchet.status_block(),
            "",
            "Standards (top line)",
        ]
        for s in self.STANDARDS:
            lines.append(f"  · {s}")
        lines.append("Avoid")
        for a in self.AVOID:
            lines.append(f"  · {a}")
        lines.append("")
        lines.append(f"at {datetime.now(timezone.utc).isoformat()}")
        return "\n".join(lines)

    def demo_roundtrip(self, passphrase: str = "levi-phase-b-demo") -> Dict[str, Any]:
        """Safe local demo: derive CMK label + one ratchet step. No network."""
        cmk, salt, label = self.argon.derive_cmk(passphrase)
        sid = secrets.token_hex(8)
        self.ratchet.demo_init_session(sid, cmk)
        mk, mk_label = self.ratchet.demo_next_message_key(sid)
        return {
            "cmk_backend": label,
            "cmk_len": len(cmk),
            "salt_hex": salt.hex()[:16] + "…",
            "session": sid,
            "message_key_label": mk_label,
            "message_key_len": len(mk),
            "production_argon": self.argon.is_production_ready(),
            "note": "demo only — install argon2-cffi + use libsignal for production Phase B",
        }
