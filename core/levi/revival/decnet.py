"""revival/decnet.py — peer-symmetric routing and the learning bridge.

Studied from: dead-networks-20260916 (report.md [DECnet]).

Revival of: DECnet's peer-to-peer symmetry and the transparent learning
Ethernet bridge.

Why it matters: two ideas that still do heavy lifting. First, symmetry —
no master/slave, any node routes for any other, so the network has no
single point of control and every node carries the same routing capability.
Second, the transparent bridge — it learns which addresses live on which
port by watching source addresses, forwards only where needed, and ages
entries out so the table follows the real topology. Plug it in and it just
works; no configuration.

LEVI adaptation:
- ``Topology``: a shared cost map of links. Every ``DecnetNode`` computes
  its own routes (Dijkstra) from the same view — symmetric capability, no
  coordinator.
- ``DecnetNode.route(dest, payload)``: forwards hop by hop; every node can
  forward for any other. ``deliveries`` records what arrived where.
- ``LearningBridge``: ``observe(src, port)`` learns; ``switch(src, dst,
  in_port)`` returns the egress ports (directed when known, flooded when
  not); ``age(now)`` expires stale entries.

Honest limits:
- The topology view is supplied, not discovered — there is no routing
  protocol here, just the symmetric forwarding discipline on top of a
  known map. Bridge aging uses caller-supplied timestamps.
- Cost ties break by node name; the model is shortest-path only, with no
  congestion or failure handling.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


class Topology:
    """Undirected cost map shared (as a view) by every node."""

    def __init__(self) -> None:
        self._links: Dict[str, Dict[str, float]] = {}

    def add_link(self, a: str, b: str, cost: float = 1.0) -> None:
        if cost <= 0:
            raise ValueError("cost must be positive")
        self._links.setdefault(a, {})[b] = cost
        self._links.setdefault(b, {})[a] = cost

    def neighbors(self, node: str) -> Dict[str, float]:
        return dict(self._links.get(node, {}))

    def nodes(self) -> Set[str]:
        return set(self._links)


def shortest_path(topology: Topology, source: str, dest: str) -> List[str]:
    """Dijkstra over the topology view; ties break on node name."""
    if source == dest:
        return [source]
    dist: Dict[str, float] = {source: 0.0}
    prev: Dict[str, str] = {}
    heap: List[Tuple[float, str]] = [(0.0, source)]
    visited: Set[str] = set()
    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == dest:
            break
        for neighbor in sorted(topology.neighbors(node)):
            step = topology.neighbors(node)[neighbor]
            alt = cost + step
            if alt < dist.get(neighbor, float("inf")):
                dist[neighbor] = alt
                prev[neighbor] = node
                heapq.heappush(heap, (alt, neighbor))
    if dest not in prev and dest != source:
        raise KeyError(f"no route from {source!r} to {dest!r}")
    path = [dest]
    while path[-1] != source:
        path.append(prev[path[-1]])
    return list(reversed(path))


@dataclass
class Datagram:
    source: str
    dest: str
    payload: str
    path: List[str] = field(default_factory=list)


class DecnetNode:
    """A peer: routes for itself and for any other node, symmetrically."""

    def __init__(self, name: str, topology: Topology, net: "Decnet") -> None:
        self.name = name
        self._topology = topology
        self._net = net
        self.deliveries: List[Datagram] = []

    def route(self, dest: str, payload: str) -> Datagram:
        """Send a datagram; any node may originate and any may forward."""
        path = shortest_path(self._topology, self.name, dest)
        datagram = Datagram(
            source=self.name, dest=dest, payload=payload, path=list(path)
        )
        self._net.forward(datagram)
        return datagram

    def next_hop(self, dest: str) -> Optional[str]:
        path = shortest_path(self._topology, self.name, dest)
        return path[1] if len(path) > 1 else None


class Decnet:
    """The wire: moves datagrams hop by hop through peer nodes."""

    def __init__(self, topology: Topology) -> None:
        self.topology = topology
        self.nodes: Dict[str, DecnetNode] = {}
        self.forward_count = 0

    def add_node(self, name: str) -> DecnetNode:
        if name in self.nodes:
            raise ValueError(f"node {name!r} already exists")
        node = DecnetNode(name, self.topology, self)
        self.nodes[name] = node
        return node

    def forward(self, datagram: Datagram) -> None:
        """Walk the computed path; each peer forwards in turn."""
        for hop in datagram.path[1:]:
            if hop not in self.nodes:
                raise KeyError(f"no such node on path: {hop!r}")
            self.forward_count += 1
        self.nodes[datagram.dest].deliveries.append(datagram)


class LearningBridge:
    """Transparent bridge: learns addresses from sources, ages them out."""

    def __init__(self, max_age: float = 300.0) -> None:
        if max_age <= 0:
            raise ValueError("max_age must be positive")
        self.max_age = max_age
        self._table: Dict[str, Tuple[int, float]] = {}  # addr -> (port, last_seen)
        self.floods = 0
        self.directs = 0

    def observe(self, src: str, port: int, now: float) -> None:
        """Learn (or refresh): src lives on port."""
        self._table[src] = (port, now)

    def switch(self, src: str, dst: str, in_port: int, now: float) -> List[int]:
        """Return egress ports for a frame. Floods when dst is unknown."""
        self.observe(src, in_port, now)
        entry = self._table.get(dst)
        if entry is not None and now - entry[1] <= self.max_age:
            port = entry[0]
            self.directs += 1
            return [] if port == in_port else [port]
        self.floods += 1
        return []  # caller floods to all ports except in_port

    def age(self, now: float) -> int:
        """Expire entries older than max_age. Returns the number removed."""
        stale = [
            addr for addr, (_, seen) in self._table.items() if now - seen > self.max_age
        ]
        for addr in stale:
            del self._table[addr]
        return len(stale)

    def table(self) -> Dict[str, int]:
        return {addr: port for addr, (port, _) in self._table.items()}


ORIGIN = "levi-revival/decnet"
