"""Physarum — slime-mold adaptive network pruning (class SLM, organ reim).

Real mechanism (Nakagaki et al., Nature 2000; Tero et al., Science 2010):
Physarum polycephalum spans food sources with a tube network; tubes
carrying more protoplasmic flow thicken, starved tubes retract and vanish.
The mold keeps what works and composts what doesn't — no brain, no plan.
Translated: flow-reinforced network pruning that turns failed routes into
a shorter, tougher network. Failure is the raw material.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

Edge = Tuple[str, str]


class TubeNetwork:
    """Conductivity network that prunes itself by flow."""

    def __init__(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str, float]],
        reinforce: float = 0.2,
        decay: float = 0.1,
        prune_below: float = 0.05,
    ) -> None:
        self.nodes = list(nodes)
        # edge key -> [length, conductivity]
        self.tubes: Dict[Edge, List[float]] = {}
        for a, b, length in edges:
            key = (a, b) if a <= b else (b, a)
            self.tubes[key] = [float(length), 1.0]
        self.reinforce = reinforce
        self.decay = decay
        self.prune_below = prune_below

    def pulse(self, source: str, sink: str, flow: float = 1.0) -> None:
        """One foraging pulse: push flow source->sink along shortest tubes.

        Used tubes thicken; all tubes decay; dead tubes are composted.
        """
        path = self._shortest_path(source, sink)
        used = set()
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            key = (a, b) if a <= b else (b, a)
            used.add(key)
        for key, (_length, cond) in list(self.tubes.items()):
            if key in used:
                self.tubes[key][1] = cond + self.reinforce * flow
            else:
                self.tubes[key][1] = cond * (1.0 - self.decay)
            if self.tubes[key][1] < self.prune_below:
                del self.tubes[key]  # composted: failure becomes nothing

    def _shortest_path(self, source: str, sink: str) -> List[str]:
        """Dijkstra over current tubes; cost = length / conductivity."""
        import heapq

        dist = {n: float("inf") for n in self.nodes}
        prev: Dict[str, str] = {}
        dist[source] = 0.0
        heap = [(0.0, source)]
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist[n]:
                continue
            if n == sink:
                break
            for (a, b), (length, cond) in self.tubes.items():
                m = b if a == n else (a if b == n else None)
                if m is None:
                    continue
                cost = length / max(cond, 1e-9)
                if dist[n] + cost < dist[m]:
                    dist[m] = dist[n] + cost
                    prev[m] = n
                    heapq.heappush(heap, (dist[m], m))
        path = [sink]
        while path[-1] != source:
            path.append(prev[path[-1]])
        return list(reversed(path))

    def surviving_edges(self) -> List[Edge]:
        return sorted(self.tubes.keys())
