"""
Interpenetration matrix — true weighted graph model over the free lattice.

One canonical place for the graph (per the one-implementation-per-concept
rule). Built from two edge sources:

  1. declared ``combines_with`` edges on FreeIntegration entries .... weight 1.0
     (an operator-authored claim that two assets combine)
  2. symbiosis formal pairs from ``levi.graph.symbiosis`` ........... weight 2.0
     (first-class bonds carrying mutual-governance semantics)

If the same unordered pair is declared in BOTH registries, the weights ADD
(3.0): the bond is confirmed by two independent declarations, so the
reinforcement is real rather than double counting.

Dangling references: a ``combines_with`` target that is not a catalog id
becomes a graph node tagged ``external=True`` (the asset is real — it belongs
to another subsystem — so dropping it would sever real topology). Such ids are
ALSO reported as ``dangling_refs`` by the lint: visible, named, never a crash.

All metrics are stdlib-only. Unweighted distances (BFS hop counts) are used
for closeness and shortest paths; weights are used for weighted degree and
bond ranking.

JSON export schema ("levi.free_graph/v1")::

    {
      "schema": "levi.free_graph/v1",
      "nodes": [{"id": str, "era": str|null, "external": bool,
                 "degree": int, "weighted_degree": float,
                 "degree_centrality": float, "closeness": float,
                 "clustering": float}],
      "edges": [{"a": str, "b": str, "weight": float,
                 "kinds": ["combines_with"|"symbiosis", ...]}],
      "counts": {"nodes": int, "edges": int, "total_weight": float},
      "orphans": [str],
      "dangling_refs": [str],
      "top_bonds": [{"a": str, "b": str, "weight": float}]
    }
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from levi.integrations.free_lattice import CATALOG

# Weighting law — documented here and re-stated in the human-readable view.
W_COMBINES_WITH = 1.0  # declared combines_with edge
W_SYMBIOSIS = 2.0  # symbiosis formal pair (first-class bond)

JSON_SCHEMA = "levi.free_graph/v1"


@dataclass
class GraphNode:
    id: str
    era: Optional[str] = None
    external: bool = False


def _symbiosis_pairs() -> list:
    """Best-effort load of the symbiosis registry; never crashes the graph."""
    try:
        from levi.graph.symbiosis import PAIRS

        return list(PAIRS)
    except Exception:
        return []


class FreeGraph:
    """Weighted undirected graph of interpenetrating LEVI assets."""

    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.adj: Dict[str, Dict[str, float]] = {}
        self.edge_kinds: Dict[frozenset, Set[str]] = {}
        # combines_with targets not present as catalog ids (lint finding)
        self._dangling: Set[str] = set()

    # -- construction -----------------------------------------------------
    def add_node(
        self, node_id: str, era: Optional[str] = None, external: bool = False
    ) -> GraphNode:
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(node_id, era, external)
            self.adj[node_id] = {}
        return self.nodes[node_id]

    def add_edge(self, a: str, b: str, weight: float, kind: str) -> None:
        if a == b:  # self-loops would corrupt degree/clustering; skip
            return
        self.add_node(a)
        self.add_node(b)
        self.adj[a][b] = self.adj[a].get(b, 0.0) + weight
        self.adj[b][a] = self.adj[b].get(a, 0.0) + weight
        self.edge_kinds.setdefault(frozenset((a, b)), set()).add(kind)

    def edge_weight(self, a: str, b: str) -> float:
        return self.adj.get(a, {}).get(b, 0.0)

    def counts(self) -> Dict[str, float]:
        total = sum(sum(nbrs.values()) for nbrs in self.adj.values()) / 2.0
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edge_kinds),
            "total_weight": round(total, 6),
        }

    # -- metrics ----------------------------------------------------------
    def degree(self, node_id: str) -> int:
        return len(self.adj.get(node_id, {}))

    def weighted_degree(self, node_id: str) -> float:
        return round(sum(self.adj.get(node_id, {}).values()), 6)

    def degree_centrality(self) -> Dict[str, float]:
        n = len(self.nodes)
        if n < 2:
            return {nid: 0.0 for nid in self.nodes}
        return {nid: round(len(self.adj[nid]) / (n - 1), 6) for nid in self.nodes}

    def _bfs_distances(self, source: str) -> Dict[str, int]:
        dist = {source: 0}
        q = deque([source])
        while q:
            cur = q.popleft()
            for nxt in self.adj[cur]:
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1
                    q.append(nxt)
        return dist

    def closeness_centrality(self) -> Dict[str, float]:
        """Reachable-set closeness: reachable/(sum of hop distances); 0 if isolated."""
        out = {}
        for nid in self.nodes:
            dist = self._bfs_distances(nid)
            others = [d for m, d in dist.items() if m != nid]
            out[nid] = round(len(others) / sum(others), 6) if others else 0.0
        return out

    def clustering_coefficient(self, node_id: str) -> float:
        nbrs = list(self.adj.get(node_id, {}))
        k = len(nbrs)
        if k < 2:
            return 0.0
        e = 0
        for i in range(k):
            for j in range(i + 1, k):
                if nbrs[j] in self.adj[nbrs[i]]:
                    e += 1
        return round(2.0 * e / (k * (k - 1)), 6)

    def strongest_bonds(
        self, limit: int = 10
    ) -> List[Tuple[str, str, float, List[str]]]:
        edges = []
        for key, kinds in self.edge_kinds.items():
            a, b = sorted(key)
            edges.append((a, b, round(self.adj[a][b], 6), sorted(kinds)))
        edges.sort(key=lambda t: (-t[2], t[0], t[1]))
        return edges[:limit]

    # -- lint --------------------------------------------------------------
    def orphans(self) -> List[str]:
        """Degree-0 nodes. The lattice rule: orphans are defects."""
        return sorted(nid for nid in self.nodes if not self.adj[nid])

    def dangling_refs(self) -> List[str]:
        """combines_with targets with no catalog entry (kept as external nodes)."""
        return sorted(self._dangling)

    def lint(self) -> Dict[str, object]:
        orphans = self.orphans()
        dangling = self.dangling_refs()
        return {"orphans": orphans, "dangling_refs": dangling, "ok": not orphans}

    # -- queries -----------------------------------------------------------
    def shortest_path(self, a: str, b: str) -> Optional[List[str]]:
        """BFS shortest path; None when an id is unknown or disconnected."""
        if a not in self.nodes or b not in self.nodes:
            return None
        if a == b:
            return [a]
        prev: Dict[str, Optional[str]] = {a: None}
        q = deque([a])
        while q:
            cur = q.popleft()
            for nxt in self.adj[cur]:
                if nxt not in prev:
                    prev[nxt] = cur
                    if nxt == b:
                        path = [b]
                        while prev[path[-1]] is not None:
                            path.append(prev[path[-1]])  # type: ignore[arg-type]
                        return list(reversed(path))
                    q.append(nxt)
        return None

    def neighborhood(self, node_id: str, depth: int = 1) -> Dict[int, List[str]]:
        """Assets at each hop distance 1..depth. {} for unknown ids."""
        if node_id not in self.nodes or depth < 1:
            return {}
        dist = self._bfs_distances(node_id)
        layers: Dict[int, List[str]] = {}
        for nid, d in dist.items():
            if 1 <= d <= depth:
                layers.setdefault(d, []).append(nid)
        return {d: sorted(ids) for d, ids in sorted(layers.items())}

    # -- export ------------------------------------------------------------
    def to_json_dict(self) -> Dict[str, object]:
        deg_c = self.degree_centrality()
        close_c = self.closeness_centrality()
        nodes = [
            {
                "id": nid,
                "era": node.era,
                "external": node.external,
                "degree": self.degree(nid),
                "weighted_degree": self.weighted_degree(nid),
                "degree_centrality": deg_c[nid],
                "closeness": close_c[nid],
                "clustering": self.clustering_coefficient(nid),
            }
            for nid, node in sorted(self.nodes.items())
        ]
        edges = [
            {"a": a, "b": b, "weight": w, "kinds": kinds}
            for a, b, w, kinds in self.strongest_bonds(limit=len(self.edge_kinds))
        ]
        return {
            "schema": JSON_SCHEMA,
            "nodes": nodes,
            "edges": edges,
            "counts": self.counts(),
            "orphans": self.orphans(),
            "dangling_refs": self.dangling_refs(),
            "top_bonds": [
                {"a": a, "b": b, "weight": w} for a, b, w, _ in self.strongest_bonds(10)
            ],
        }

    def to_json_str(self) -> str:
        return json.dumps(self.to_json_dict(), indent=2)


def build_free_graph(
    catalog: Optional[Iterable] = None, pairs: Optional[Iterable] = None
) -> FreeGraph:
    """Assemble the weighted graph from the lattice catalog + symbiosis pairs."""
    entries = list(CATALOG) if catalog is None else list(catalog)
    sym = _symbiosis_pairs() if pairs is None else list(pairs)
    g = FreeGraph()
    catalog_ids = {c.id for c in entries}
    for c in entries:
        g.add_node(c.id, era=c.era, external=False)
        for target in c.combines_with:
            if target not in catalog_ids:
                g._dangling.add(target)
                node = g.add_node(target, era=None, external=True)
                node.external = True
            g.add_edge(c.id, target, W_COMBINES_WITH, "combines_with")
    for pair in sym:
        for asset in (pair.asset_a, pair.asset_b):
            if asset not in g.nodes:
                g.add_node(asset, era=None, external=True)
        g.add_edge(pair.asset_a, pair.asset_b, W_SYMBIOSIS, "symbiosis")
    return g


__all__ = [
    "FreeGraph",
    "GraphNode",
    "build_free_graph",
    "W_COMBINES_WITH",
    "W_SYMBIOSIS",
    "JSON_SCHEMA",
]
