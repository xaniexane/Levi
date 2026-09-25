"""LEVI integrity — defensive tamper detection (not malware, not DRM).

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

What this is: FNV-1a fingerprints and a triple-fingerprint check used to
detect *casual tampering* of local pack manifests and skill files, with
a refuse-to-load gate. What it is not: license enforcement against the
user, remote attestation, or any code that phones home. Fingerprints are
integrity checksums, not cryptographic secrecy.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193
_MASK32 = 0xFFFFFFFF


def fnv1a_32(text: str) -> str:
    """FNV-1a 32-bit hash of ``text`` (UTF-8), returned as 8 hex chars.

    Integrity fingerprint only — not a cryptographic hash, not secrecy.
    """
    if not isinstance(text, str):
        raise ValueError(f"fnv1a_32: expected str, got {type(text).__name__}")
    h = _FNV_OFFSET
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK32
    return f"{h:08x}"


def _canonical(obj: Any) -> str:
    """Deterministic JSON encoding for fingerprinting."""
    try:
        return json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError):
        return str(obj)


def triple_fingerprint(obj: Any) -> str:
    """Triple fingerprint: content + reversed content + length mix.

    Three FNV-1a digests concatenated (24 hex chars). Detects casual
    tampering of pack manifests: flipping content changes the digest,
    reordering changes the reversed digest, truncation changes the mix.
    """
    canon = _canonical(obj)
    a = fnv1a_32(canon)
    b = fnv1a_32(canon[::-1])
    c = fnv1a_32(f"{len(canon)}:{a}:{b}")
    return a + b + c


def verify_fingerprint(obj: Any, expected: Optional[str]) -> Dict[str, Any]:
    """Check ``obj`` against an expected fingerprint."""
    if not expected:
        return {"ok": False, "reason": "missing fingerprint"}
    got = triple_fingerprint(obj)
    return {"ok": got == expected, "got": got, "expected": expected}


def gate_pack(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Refuse-to-load gate for pack manifests.

    If the manifest carries a ``fingerprint``, it must verify against the
    manifest body (id, version, serials); otherwise loading is refused.
    Manifests without a fingerprint pass with a note — the gate is
    opt-in tamper detection, not a lockout.
    """
    if not isinstance(pack, Mapping) or not pack.get("id"):
        return {"ok": False, "reason": "invalid pack manifest"}
    fingerprint = pack.get("fingerprint")
    if fingerprint:
        body = {
            "id": pack.get("id"),
            "version": pack.get("version"),
            "serials": pack.get("serials"),
        }
        verdict = verify_fingerprint(body, str(fingerprint))
        if not verdict["ok"]:
            return {
                "ok": False,
                "reason": "tamper fingerprint mismatch",
                "detail": verdict,
            }
    else:
        return {"ok": True, "note": "no fingerprint — unverified"}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    def _skill_fingerprint(args):
        args = args or {}
        text = args.get("text")
        if text is None:
            return "fingerprint needs text"
        if isinstance(text, str):
            return triple_fingerprint(text)
        return triple_fingerprint(text)

    def _skill_gate_pack(args):
        pack = (args or {}).get("pack")
        if not isinstance(pack, dict):
            return "gate_pack needs a pack manifest dict"
        verdict = gate_pack(pack)
        return f"ok={verdict['ok']} reason={verdict.get('reason', verdict.get('note', ''))}"

    INTEGRITY_SKILLS = [
        Skill(
            id="security_fingerprint",
            name="Integrity Fingerprint",
            description="FNV-1a triple fingerprint of text/data (tamper detection)",
            category="security",
            risk_level=SkillRisk.INFO,
            handler=_skill_fingerprint,
            tags=["security", "integrity", "fingerprint"],
        ),
        Skill(
            id="security_gate_pack",
            name="Pack Load Gate",
            description="Refuse-to-load gate: verify a pack manifest fingerprint before loading",
            category="security",
            risk_level=SkillRisk.INFO,
            handler=_skill_gate_pack,
            tags=["security", "integrity", "pack"],
        ),
    ]
except ImportError:  # pragma: no cover
    INTEGRITY_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
