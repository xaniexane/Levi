"""
Zero-knowledge-oriented design notes + checklist for Phase B/C.

Server stores ciphertext + metadata. Content master key stays on device.
Password reset cannot unlock mind-data without user recovery key.
Support cannot “open a ticket and read the corpus.”
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from datetime import datetime, timezone


@dataclass
class ZKPrinciple:
    id: str
    title: str
    rule: str
    phase: str  # A | B | C

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PRINCIPLES: List[ZKPrinciple] = [
    ZKPrinciple(
        "ZK1",
        "CMK on device",
        "Content master key never uploaded; server has ciphertext only.",
        "B",
    ),
    ZKPrinciple(
        "ZK2",
        "Recovery split",
        "Password reset alone cannot unlock mind-data; recovery key required.",
        "B",
    ),
    ZKPrinciple(
        "ZK3",
        "Support blind",
        "Support cannot open a ticket and read corpus / stories / charter.",
        "B",
    ),
    ZKPrinciple(
        "ZK4",
        "Metadata minimal",
        "Server metadata limited to sync cursors, device ids, encrypted blobs sizes.",
        "B",
    ),
    ZKPrinciple(
        "ZK5",
        "HITL local",
        "HITL decisions remain authoritative on-device even when sync is enabled.",
        "A",
    ),
    ZKPrinciple(
        "ZK6",
        "Crisis offline",
        "Crisis / distress path works with cloud unreachable.",
        "A",
    ),
    ZKPrinciple(
        "ZK7",
        "Export exit",
        "User can always export life-pack and leave; no lock-in via ciphertext hostage.",
        "A",
    ),
    ZKPrinciple(
        "ZK8",
        "Quota research",
        "Phase C may explore ZK usage proofs; never trade for content keys.",
        "C",
    ),
]


class ZeroKnowledgeDesign:
    def principles(self) -> List[ZKPrinciple]:
        return list(PRINCIPLES)

    def report(self) -> str:
        lines = [
            "══ Zero-knowledge-oriented design ══",
            "Server stores ciphertext + metadata. CMK stays on device.",
            "",
        ]
        for p in PRINCIPLES:
            lines.append(f"  [{p.phase}] {p.id}  {p.title}")
            lines.append(f"       {p.rule}")
        lines.append("")
        lines.append(f"at {datetime.now(timezone.utc).isoformat()}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principles": [p.to_dict() for p in PRINCIPLES],
            "at": datetime.now(timezone.utc).isoformat(),
        }
