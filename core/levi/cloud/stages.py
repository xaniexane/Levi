"""
Product stage map (A / B / C) — fused into Vyve LEVI as first-class organism layers.

Not to be confused with the project phase runner (levi.project.phases,
P0–P15 service-delivery phases). Cloud "stages" are product-maturity
stages; project "phases" are an executable workflow with HITL.

Local-first does not mean cloud-never. Cloud is optional wings; core stays useful offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


@dataclass(frozen=True)
class StageDef:
    id: str
    name: str
    status: str  # active | specified | planned
    summary: str
    capabilities: List[str] = field(default_factory=list)
    must_keep: List[str] = field(default_factory=list)
    not_yet: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


STAGE_A = StageDef(
    id="A",
    name="Local SI",
    status="active",
    summary="Full local symbiotic intelligence — offline brain, HITL, L.W.P., UI, no account required.",
    capabilities=[
        "companion / charter / persona lattice",
        "L.W.P. story organs (deny / reim / crown / rupture / phase / power)",
        "Opportunity Rail + Mirror Cascade + HITL (silence ≠ approve)",
        "corpus / brain / vault seal (local)",
        "Software Factory under L.W.P. stages",
        "daemon cycle · pulse · estop",
        "export life-pack · offline crisis path",
        "optional local LLM (Ollama) + Pollinations",
    ],
    must_keep=[
        "HITL on consequences",
        "local crisis path works with server down",
        "exportable ~/.levi data",
        "no manufactured demand",
        "closed-source DNA / provenance",
    ],
    not_yet=[],
)

STAGE_B = StageDef(
    id="B",
    name="Encrypted wings",
    status="specified",
    summary="E2E encrypted sync, recovery keys, optional model relay, ciphertext-only server.",
    capabilities=[
        "Argon2id passphrase → content master key (CMK) at rest",
        "X3DH + Double Ratchet for device pairing / sync sessions",
        "encrypted backup of ~/.levi across devices",
        "optional hosted model API relay (when local LLM absent)",
        "recovery key path (password reset cannot unlock mind-data alone)",
        "ciphertext + metadata only on server",
    ],
    must_keep=[
        "CMK never leaves device by default",
        "server cannot read corpus / stories / charter",
        "HITL still local-authoritative",
        "offline core remains fully usable",
    ],
    not_yet=[
        "production libsignal integration",
        "live multi-device sync transport",
        "hosted relay billing hooks",
    ],
)

STAGE_C = StageDef(
    id="C",
    name="Product wings",
    status="planned",
    summary="Teams, billing, hosted UI, remote wipe, ZK quota research — still not cloud-owns-keys.",
    capabilities=[
        "team seats + shared project graphs (encrypted)",
        "billing / seats (separate from content keys)",
        "hosted UI calling the same organs",
        "remote wipe of device sessions (not content without CMK)",
        "ZK-oriented quota / usage proofs research",
    ],
    must_keep=[
        "same organs as Phase A",
        "no server-held content keys by default",
        "export / exit always available",
        "crisis path independent of cloud",
    ],
    not_yet=[
        "multi-tenant control plane",
        "payment processor wiring",
        "remote admin UI",
    ],
)


def current_stage() -> StageDef:
    """Runtime truth: we are on Phase A until B transport is stood up."""
    return STAGE_A


class StageMap:
    """Fused A→B→C view for CLI, ops, and integration audit."""

    def __init__(self) -> None:
        self.phases = {"A": STAGE_A, "B": STAGE_B, "C": STAGE_C}

    def all(self) -> List[StageDef]:
        return [self.phases[k] for k in ("A", "B", "C")]

    def get(self, pid: str) -> Optional[StageDef]:
        return self.phases.get(pid.upper())

    def status_block(self) -> str:
        lines = [
            "LEVI × L.W.P. — Phase map (local-first + optional cloud wings)",
            f"Current: Phase {current_stage().id} — {current_stage().name} [{current_stage().status}]",
            "",
        ]
        for p in self.all():
            marker = "▶" if p.id == current_stage().id else " "
            lines.append(f"{marker} Phase {p.id}  {p.name:16}  [{p.status}]")
            lines.append(f"    {p.summary}")
            if p.capabilities:
                lines.append("    can: " + "; ".join(p.capabilities[:3]) + ("…" if len(p.capabilities) > 3 else ""))
            if p.not_yet:
                lines.append("    not yet: " + "; ".join(p.not_yet[:2]))
            lines.append("")
        lines.append("Invariant: HITL · local crisis · exportable · server never needs plaintext.")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": current_stage().id,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "at": datetime.now(timezone.utc).isoformat(),
        }
