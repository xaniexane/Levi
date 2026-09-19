"""Resource offers — what each fleet device shares with the mesh.

A node advertises spare capacity: cpu units, memory, storage,
bandwidth, plus capability tags (e.g. "gpu", "camera", "always-on").
``ResourcePool`` tracks live offers and matches task requirements to
nodes, deterministically ranked so every farmer picks the same peers
for the same fleet state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ResourceOffer:
    node_id: str
    cpu_units: float = 0.0  # fractional cores offered
    memory_mb: float = 0.0  # RAM offered
    storage_mb: float = 0.0  # disk offered
    bandwidth_kbps: float = 0.0  # network offered
    tags: Tuple[str, ...] = ()  # capability tags: "gpu", "always-on", ...
    ts: float = field(default_factory=time)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "cpu_units": self.cpu_units,
            "memory_mb": self.memory_mb,
            "storage_mb": self.storage_mb,
            "bandwidth_kbps": self.bandwidth_kbps,
            "tags": list(self.tags),
            "ts": self.ts,
        }

    @staticmethod
    def from_dict(raw: Dict) -> "ResourceOffer":
        return ResourceOffer(
            node_id=str(raw.get("node_id", "")),
            cpu_units=float(raw.get("cpu_units", 0.0)),
            memory_mb=float(raw.get("memory_mb", 0.0)),
            storage_mb=float(raw.get("storage_mb", 0.0)),
            bandwidth_kbps=float(raw.get("bandwidth_kbps", 0.0)),
            tags=tuple(raw.get("tags", ())),
            ts=float(raw.get("ts", 0.0)),
        )

    def satisfies(
        self,
        cpu_units: float = 0.0,
        memory_mb: float = 0.0,
        tags: Tuple[str, ...] = (),
    ) -> bool:
        return (
            self.cpu_units >= cpu_units
            and self.memory_mb >= memory_mb
            and all(t in self.tags for t in tags)
        )


class ResourcePool:
    """Live offers across the fleet, with deterministic matching."""

    def __init__(self) -> None:
        self._offers: Dict[str, ResourceOffer] = {}

    def advertise(self, offer: ResourceOffer) -> None:
        if not offer.node_id:
            raise ValueError("offer needs a node_id")
        self._offers[offer.node_id] = offer

    def withdraw(self, node_id: str) -> None:
        self._offers.pop(node_id, None)

    def get(self, node_id: str) -> Optional[ResourceOffer]:
        return self._offers.get(node_id)

    def match(
        self,
        cpu_units: float = 0.0,
        memory_mb: float = 0.0,
        tags: Tuple[str, ...] = (),
        limit: Optional[int] = None,
    ) -> List[str]:
        """Node ids satisfying the requirements, best headroom first.

        Ties break on node_id so the ranking is deterministic across
        farmers observing the same pool state.
        """
        scored = []
        for offer in self._offers.values():
            if not offer.satisfies(cpu_units, memory_mb, tags):
                continue
            headroom = (offer.cpu_units - cpu_units) + (
                offer.memory_mb - memory_mb
            ) / 1024.0
            scored.append((-headroom, offer.node_id))
        scored.sort()
        ids = [nid for _, nid in scored]
        return ids[:limit] if limit is not None else ids

    def node_ids(self) -> List[str]:
        return sorted(self._offers)
