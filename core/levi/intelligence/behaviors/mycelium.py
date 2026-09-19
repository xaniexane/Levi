"""Mycelium — fungal network decomposition and routing (class MYC, reim).

Real mechanism: mycelial networks decompose dead organic matter and
route the recovered nutrients along concentration gradients to where the
network needs them, rerouting around damage. The forest's internet is a
compost heap with logistics. Translated: dead inputs are broken down
into reusable units and routed to sinks; severed links are bypassed.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


class Mycelium:
    """Decompose-then-route nutrient network."""

    def __init__(self) -> None:
        self.links: Dict[Tuple[str, str], float] = {}
        self.nodes: Dict[str, float] = {}  # node -> stored nutrient

    def grow(self, a: str, b: str, capacity: float = 1.0) -> None:
        key = (a, b) if a <= b else (b, a)
        self.links[key] = float(capacity)
        self.nodes.setdefault(a, 0.0)
        self.nodes.setdefault(b, 0.0)

    def sever(self, a: str, b: str) -> None:
        """Damage: cut a link. The network must route around it."""
        key = (a, b) if a <= b else (b, a)
        self.links.pop(key, None)

    def decompose(self, matter: str, yield_: float) -> float:
        """Break dead matter down into reusable nutrient. Returns yield."""
        assert yield_ >= 0.0
        self.nodes[matter] = self.nodes.get(matter, 0.0) + yield_
        return yield_

    def route(self, source: str, sink: str) -> float:
        """Move nutrient source->sink along the widest-capacity path.

        Returns amount delivered (0.0 if no path survives).
        """
        path = self._widest_path(source, sink)
        if not path:
            return 0.0
        bottleneck = min(
            self.links[
                (path[i], path[i + 1])
                if (path[i], path[i + 1]) in self.links
                else (path[i + 1], path[i])
            ]
            for i in range(len(path) - 1)
        )
        amount = min(self.nodes.get(source, 0.0), bottleneck)
        self.nodes[source] = self.nodes.get(source, 0.0) - amount
        self.nodes[sink] = self.nodes.get(sink, 0.0) + amount
        return amount

    def _widest_path(self, source: str, sink: str) -> List[str]:
        import heapq

        best = {n: -1.0 for n in self.nodes}
        prev: Dict[str, str] = {}
        best[source] = float("inf")
        heap = [(-float("inf"), source)]
        while heap:
            neg_w, n = heapq.heappop(heap)
            w = -neg_w
            if w < best[n]:
                continue
            if n == sink:
                break
            for (a, b), cap in self.links.items():
                m = b if a == n else (a if b == n else None)
                if m is None:
                    continue
                w2 = min(w, cap)
                if w2 > best[m]:
                    best[m] = w2
                    prev[m] = n
                    heapq.heappush(heap, (-w2, m))
        if best[sink] < 0:
            return []
        path = [sink]
        while path[-1] != source:
            path.append(prev[path[-1]])
        return list(reversed(path))
