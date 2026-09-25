"""Cybrus capability registry — explicit, discoverable capabilities.

Addition to the Cybrus gate: capabilities register with a risk band and a
discovery surface, so nothing acts on an unregistered power. Concept adapted
from the recovered security-fabric lineage; original implementation, wired to
Cybrus policy/approval rather than duplicating them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List


class RiskBand(IntEnum):
    INFO = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Capability:
    id: str
    name: str
    description: str
    domain: str
    version: str = "1.0.0"
    risk: RiskBand = RiskBand.LOW
    requires_approval: bool = False
    destructive: bool = False
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["risk"] = int(self.risk)
        d["risk_name"] = self.risk.name
        return d


class CapabilityRegistry:
    """Register once, discover by text, require by id. Deny-closed."""

    def __init__(self) -> None:
        self._caps: Dict[str, Capability] = {}

    def register(self, cap: Capability) -> Capability:
        self._caps[cap.id] = cap
        return cap

    def require(self, cap_id: str) -> Capability:
        try:
            return self._caps[cap_id]
        except KeyError:
            raise KeyError(
                f"unregistered capability: {cap_id!r} — deny-closed"
            ) from None

    def search(self, query: str, limit: int = 20) -> List[Capability]:
        q = query.lower()
        scored = []
        for cap in self._caps.values():
            hay = f"{cap.id} {cap.name} {cap.description} {cap.domain} {' '.join(cap.tags)}".lower()
            if q in hay:
                scored.append(cap)
        return scored[:limit]

    def domains(self) -> List[str]:
        return sorted({c.domain for c in self._caps.values()})

    def __len__(self) -> int:
        return len(self._caps)
