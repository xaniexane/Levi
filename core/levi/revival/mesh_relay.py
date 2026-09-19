"""Pole-top mesh: everyone relays for everyone.

Studied from: dead-networks-20260916/report.md (Metricom Ricochet)

The load-bearing mechanism: cheap radio nodes relay each other's
traffic over short hops, so no node needs to reach a tower. Packets
carry a hop budget; each relay spends one hop, drops duplicates it has
already seen, and refuses to forward when the budget is exhausted.
Coverage grows by adding nodes, not by raising power.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is flood-based mesh relaying with
per-packet duplicate suppression and hop budgets. Not revived: real
radio behavior — adjacency is configured, not measured; routing is
flooding, not link-state.
"""

from __future__ import annotations

from dataclasses import dataclass, field


ORIGIN = "levi-revival/mesh-relay"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MeshError(Exception):
    """Base class for mesh failures."""


@dataclass
class MeshPacket:
    """One packet traveling the mesh."""

    packet_id: str
    source: str
    destination: str
    payload: str
    ttl: int = 8  # hop budget; dies at zero
    path: list[str] = field(default_factory=list)


class MeshNode:
    """One relay node.

    Nodes forward packets to all neighbors (flooding), but each node
    forwards a given packet_id only once — duplicates arriving via
    another path are dropped. The destination keeps the packet instead
    of forwarding it.
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.neighbors: set[str] = set()
        self._seen: set[str] = set()  # packet_ids already handled
        self.received: list[MeshPacket] = []  # packets addressed to us

    def link(self, other: "MeshNode") -> None:
        self.neighbors.add(other.node_id)
        other.neighbors.add(self.node_id)

    def can_accept(self, packet: MeshPacket) -> bool:
        return packet.packet_id not in self._seen and packet.ttl > 0

    def handle(self, packet: MeshPacket) -> list[tuple[str, MeshPacket]]:
        """Process one incoming packet.

        Returns (neighbor_id, packet) pairs to forward next — the *caller*
        (the mesh simulator) performs the actual hand-off, so the node
        stays honest about topology.
        """
        if not self.can_accept(packet):
            return []
        self._seen.add(packet.packet_id)
        packet.path.append(self.node_id)
        if packet.destination == self.node_id:
            self.received.append(packet)
            return []  # delivered: do not forward
        packet.ttl -= 1
        if packet.ttl <= 0:
            return []  # hop budget exhausted
        previous = packet.path[-2] if len(packet.path) > 1 else None
        return [
            (n, packet) for n in sorted(self.neighbors) if n != previous
        ]  # don't bounce it straight back

    def forget(self, packet_id: str) -> None:
        """Release the duplicate-suppression record (aging out)."""
        self._seen.discard(packet_id)


class Mesh:
    """A simulator for the relay mesh: inject packets, run rounds."""

    def __init__(self) -> None:
        self.nodes: dict[str, MeshNode] = {}
        self.delivered: int = 0
        self.dropped_ttl: int = 0
        self._inflight: list[tuple[str, MeshPacket]] = []

    def add(self, node: MeshNode) -> None:
        if node.node_id in self.nodes:
            raise MeshError(f"duplicate node: {node.node_id}")
        self.nodes[node.node_id] = node

    def send(
        self, source: str, destination: str, payload: str, packet_id: str, ttl: int = 8
    ) -> None:
        packet = MeshPacket(
            packet_id=packet_id,
            source=source,
            destination=destination,
            payload=payload,
            ttl=ttl,
        )
        self._inflight.append((source, packet))

    def rounds(self, max_rounds: int = 64) -> dict[str, int]:
        """Advance until nothing is in flight or the round cap hits."""
        for _ in range(max_rounds):
            if not self._inflight:
                break
            current, self._inflight = self._inflight, []
            for node_id, packet in current:
                node = self.nodes.get(node_id)
                if node is None:
                    continue
                received_before = len(node.received)
                forwards = node.handle(packet)
                if len(node.received) > received_before:
                    self.delivered += 1
                elif not forwards and packet.ttl <= 0 and packet.destination != node_id:
                    # Hop budget spent with no delivery and no onward path.
                    self.dropped_ttl += 1
                self._inflight.extend(forwards)
        stats = {
            "delivered": self.delivered,
            "dropped_ttl": self.dropped_ttl,
            "inflight": len(self._inflight),
        }
        return stats

    def path_of(self, packet_id: str) -> list[str] | None:
        for node in self.nodes.values():
            for packet in node.received:
                if packet.packet_id == packet_id:
                    return packet.path
        return None
