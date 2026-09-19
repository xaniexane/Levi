# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Vaultkeeper — keeper of the LEVI Vault.

Jack of all trades; verification 10. Owns reproducible-build
verification, developer-signed installs, delta updates, paid apps on
day one with the 12% cut enforced in code.

Its unreplicable attribute is the **twin-engine verdict**: Vaultkeeper
never trusts a single crypto engine. Every verification hashes the
content with two independent SHA-256 engines — the platform binding
and its own from-scratch reimplementation sharing zero code paths —
and seals a verdict only when both digests agree AND match the
expected hash. A poisoned hash library fails the seal instead of
passing it: the second engine knows nothing of the first.
"""

from __future__ import annotations

import hashlib
import struct
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union

from levi.dynasty.dna import AgentError, DynastyAgent

__all__ = ["VaultError", "Vaultkeeper", "sha256_pure"]


class VaultError(AgentError):
    """A verification verdict was refused: engines disagreed, the
    content mismatched, or the artifact was malformed."""


# -- the second engine: SHA-256 reimplemented from scratch -------------
# Shares zero code paths with hashlib: no OpenSSL, no C binding. If the
# platform's hash library ever lies, this engine still tells the truth.


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


_K = (
    0x428A2F98,
    0x71374491,
    0xB5C0FBCF,
    0xE9B5DBA5,
    0x3956C25B,
    0x59F111F1,
    0x923F82A4,
    0xAB1C5ED5,
    0xD807AA98,
    0x12835B01,
    0x243185BE,
    0x550C7DC3,
    0x72BE5D74,
    0x80DEB1FE,
    0x9BDC06A7,
    0xC19BF174,
    0xE49B69C1,
    0xEFBE4786,
    0x0FC19DC6,
    0x240CA1CC,
    0x2DE92C6F,
    0x4A7484AA,
    0x5CB0A9DC,
    0x76F988DA,
    0x983E5152,
    0xA831C66D,
    0xB00327C8,
    0xBF597FC7,
    0xC6E00BF3,
    0xD5A79147,
    0x06CA6351,
    0x14292967,
    0x27B70A85,
    0x2E1B2138,
    0x4D2C6DFC,
    0x53380D13,
    0x650A7354,
    0x766A0ABB,
    0x81C2C92E,
    0x92722C85,
    0xA2BFE8A1,
    0xA81A664B,
    0xC24B8B70,
    0xC76C51A3,
    0xD192E819,
    0xD6990624,
    0xF40E3585,
    0x106AA070,
    0x19A4C116,
    0x1E376C08,
    0x2748774C,
    0x34B0BCB5,
    0x391C0CB3,
    0x4ED8AA4A,
    0x5B9CCA4F,
    0x682E6FF3,
    0x748F82EE,
    0x78A5636F,
    0x84C87814,
    0x8CC70208,
    0x90BEFFFA,
    0xA4506CEB,
    0xBEF9A3F7,
    0xC67178F2,
)


def sha256_pure(data: bytes) -> str:
    """SHA-256, reimplemented from the primitive — the second engine."""
    if not isinstance(data, (bytes, bytearray)):
        raise VaultError(f"sha256_pure needs bytes, got {type(data).__name__}")
    data = bytes(data)
    bit_len = (len(data) * 8) & 0xFFFFFFFFFFFFFFFF
    data += b"\x80"
    data += b"\x00" * ((56 - len(data) % 64) % 64)
    data += struct.pack(">Q", bit_len)

    h = (
        0x6A09E667,
        0xBB67AE85,
        0x3C6EF372,
        0xA54FF53A,
        0x510E527F,
        0x9B05688C,
        0x1F83D9AB,
        0x5BE0CD19,
    )

    for off in range(0, len(data), 64):
        w = list(struct.unpack(">16I", data[off : off + 64]))
        for i in range(16, 64):
            s0 = _rotr(w[i - 15], 7) ^ _rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
            s1 = _rotr(w[i - 2], 17) ^ _rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
            w.append((w[i - 16] + s0 + w[i - 7] + s1) & 0xFFFFFFFF)
        a, b, c, d, e, f, g, hh = h
        for i in range(64):
            s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
            ch = (e & f) ^ (~e & g)
            t1 = (hh + s1 + ch + _K[i] + w[i]) & 0xFFFFFFFF
            s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
            mj = (a & b) ^ (a & c) ^ (b & c)
            t2 = (s0 + mj) & 0xFFFFFFFF
            hh, g, f, e, d, c, b, a = (
                g,
                f,
                e,
                (d + t1) & 0xFFFFFFFF,
                c,
                b,
                a,
                (t1 + t2) & 0xFFFFFFFF,
            )
        h = tuple(
            (x + y) & 0xFFFFFFFF
            for x, y in zip(h, (a, b, c, d, e, f, g, hh), strict=True)
        )

    return "".join(f"{x:08x}" for x in h)


class Vaultkeeper(DynastyAgent):
    """Builds the LEVI Vault: reproducible verification, signed installs."""

    agent_id = "vaultkeeper"
    display_name = "Vaultkeeper"
    owns = "LEVI Vault"
    first_milestone = "repo index + verified installs"
    proficiency = {"verification": 10, "integrity": 9, "money": 6, "general": 6}
    specialties = [
        "reproducible-build verification: binaries provably match source",
        "twin-engine verdicts — no single crypto engine trusted",
        "developer-signed installs, delta updates",
        "paid apps on day one, 12% platform cut enforced in code",
    ]
    attributes = [
        {
            "name": "twin-engine verdict",
            "assertion": (
                "Vaultkeeper never trusts a single crypto engine: every "
                "verification hashes the content with two independent "
                "SHA-256 engines — the platform binding and its own "
                "from-scratch reimplementation sharing zero code paths — "
                "and seals a verdict only when both digests agree and match "
                "the expected hash; a poisoned hash library fails the seal "
                "instead of passing it."
            ),
        }
    ]

    #: The miniature reproducible build: fixed content, fixed expected
    #: hash — the artifact either reproduces byte-for-byte or it fails.
    GENESIS_CONTENT = b"vaultkeeper: reproducible-build miniature v1\n"
    GENESIS_EXPECTED = (
        "c1a6fc02d8f9aa09183bcdea96edea6f1fb4825fa1cf37514cea0b2646d8b588"
    )

    def __init__(self, home: Optional[Path] = None) -> None:
        # The seal lane must exist before super().__init__ binds the
        # default wares: sign_milestone touches the keeper key, whose
        # first-boot creation races under threads (partial reads fork
        # the key view and break the chain; proven in the purge).
        self._seal_lock = threading.Lock()
        super().__init__(home)
        # Warm the keeper key once, single-threaded, through the locked
        # ware — first-boot key creation must never happen mid-storm.
        self.wares.invoke("sign_milestone", f"{self.agent_id}:key-warmup")

    def _sign_milestone(self, milestone: str) -> Dict[str, str]:
        """Corroboration signature, through the seal lane."""
        with self._seal_lock:
            return super()._sign_milestone(milestone)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Any = None,
    ) -> Dict[str, Any]:
        """Plan→execute→verify→receipt, through the per-agent seal lane."""
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- twin-engine verification ---------------------------------------
    def verify_artifact(
        self, content: Union[bytes, bytearray], expected_hex: str
    ) -> Dict[str, Any]:
        """Verify content against an expected hash under both engines.

        Raises :class:`VaultError` when the two engines disagree (the
        platform binding is lying) or when the digest misses the
        expected hash. Mints nothing on failure.
        """
        if not isinstance(content, (bytes, bytearray)):
            raise VaultError(
                f"verify_artifact needs bytes, got {type(content).__name__}"
            )
        if (
            not isinstance(expected_hex, str)
            or len(expected_hex) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in expected_hex)
        ):
            raise VaultError("expected hash must be a 64-char hex string")
        engine_a = hashlib.sha256(bytes(content)).hexdigest()
        engine_b = sha256_pure(bytes(content))
        if engine_a != engine_b:
            raise VaultError(
                "twin-engine disagreement: the platform hash binding does "
                "not agree with the independent engine — verdict refused"
            )
        if engine_a != expected_hex.lower():
            raise VaultError(
                "content digest does not match the expected hash — "
                "artifact failed reproducible verification"
            )
        return {
            "sha256": engine_a,
            "engines": ["hashlib", "pure-python"],
            "engines_agree": True,
            "expected_match": True,
        }

    # -- dispatch ---------------------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Vault-domain shapes; everything else rides the shared DNA."""
        if not isinstance(task, dict):
            raise AgentError("handle requires a task dict")
        shape = task.get("shape")
        if shape == "verify":
            content = task.get("content")
            if isinstance(content, str):
                content = content.encode("utf-8")
            return self.verify_artifact(content, str(task.get("expected", "")))
        return super().handle(task)

    # -- first green task ---------------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """The reproducible-build miniature: hash known content under
        both engines, compare to the expected hash, seal the verdict."""
        verdict = self.verify_artifact(self.GENESIS_CONTENT, self.GENESIS_EXPECTED)

        def _verify(payload: Dict[str, Any]) -> None:
            if not verdict["engines_agree"] or not verdict["expected_match"]:
                raise AgentError("genesis verdict did not come back green")

        return self.do_task(
            "wave.first_task",
            {
                "artifact": "genesis-miniature",
                "sha256": verdict["sha256"],
                "engines": verdict["engines"],
                "engines_agree": True,
                "expected_match": True,
            },
            task="vaultkeeper:first",
            verify=_verify,
        )
