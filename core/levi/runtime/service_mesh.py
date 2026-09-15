"""
Service Mesh — LEVI-original local capability catalog.

Maps operator intents to organs/tools without a remote control plane.
Monetizable later as packs; runtime is free and local.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class LocalService:
    id: str
    title: str
    cli: str
    organ: str
    risk: str  # low | medium | high


SERVICES: List[LocalService] = [
    LocalService("ask", "Companion reply", 'levi ask "…"', "offline_companion", "low"),
    LocalService(
        "mirror", "Mirror Cascade", 'levi mirror --seed "…"', "lwp.mirror", "low"
    ),
    LocalService(
        "rail", "Opportunity Rail", 'levi rail --start "…"', "lwp.rail", "medium"
    ),
    LocalService(
        "lwp", "L.W.P. Model expand", "levi lwp-model --expand -n 1", "lwp.model", "low"
    ),
    LocalService(
        "builder",
        "Emergency Builder",
        "levi builder --plan --tier E5",
        "builder",
        "medium",
    ),
    LocalService(
        "crucible",
        "Crucible syntax probe",
        'levi crucible --syntax "…"',
        "runtime.crucible",
        "low",
    ),
    LocalService("watch", "Standing Watch", "levi watch", "runtime.watch", "low"),
    LocalService(
        "continuity", "Continuity Shelf", "levi continue", "runtime.continuity", "low"
    ),
    LocalService(
        "brain", "Offline brain atlas", "levi brain --seed-atlas", "brain", "low"
    ),
    LocalService(
        "hitl", "HITL decisions", "levi project --approve ID", "policy.hitl", "high"
    ),
    LocalService("ui", "Command UI", "levi serve-ui", "ops.ui", "low"),
    LocalService(
        "relay", "Model relay test", "levi relay --test", "model.relay", "low"
    ),
]


class ServiceMesh:
    def list(self) -> List[LocalService]:
        return list(SERVICES)

    def find(self, q: str) -> List[LocalService]:
        if not isinstance(q, str):
            raise ValueError(
                f"find: 'q' must be a string, got {type(q).__name__}"
            )
        q = q.lower()
        return [
            s for s in SERVICES if q in s.id or q in s.title.lower() or q in s.organ
        ]

    def format(self, q: Optional[str] = None) -> str:
        items = self.find(q) if q else self.list()
        lines = [
            "=== LEVI Service Mesh (local) ===",
            "Original catalog — not a remote agent marketplace",
            "",
        ]
        for s in items:
            lines.append(f"  [{s.id}] {s.title}")
            lines.append(f"       {s.cli}")
            lines.append(f"       organ={s.organ}  risk={s.risk}")
        lines.append("")
        lines.append(f"{len(items)} services · HITL still gates high risk")
        return "\n".join(lines)
