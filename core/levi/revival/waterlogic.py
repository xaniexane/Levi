"""de Bono's water logic: think in flows, not in boxes.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #22)

The mechanism is a deliberate inversion of classification thinking.
Classification asks "what IS this?" and sorts concepts into fixed boxes.
Water logic asks "where does attention FLOW from here?" — following
association edges from a starting concept and tracing the *trajectories*
attention takes. A traced set of trajectories is a **flowscape**: a map
of where thinking naturally goes, rather than a map of what things are.

This module implements the flow side honestly:

* ``FlowField`` — a directed graph of "leads to" association edges
  between concepts.
* ``flow(start, ...)`` — trace trajectories from a starting concept,
  depth-first or breadth-first, with cycle protection.
* ``flowscape(starts)`` — the traced map: every reachable concept,
  which trajectories led there, and where flows converge (hubs) or
  terminate (sinks).
* ``compare_with_classification(start, classifier)`` — the required
  contrast: the same starting concept viewed as flow ("what does this
  lead to?") vs. classification ("what IS this?"), side by side, so the
  difference in the two views is visible instead of philosophical.

stdlib-only. No network. Edges are added by hand (or by whatever local
process harvests them) — the module does not pretend to generate real
human associations; it traces the ones it is given.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Set


ORIGIN = "levi-revival/waterlogic"


@dataclass
class FlowField:
    """Directed "leads to" edges between concepts."""

    edges: Dict[str, List[str]] = field(default_factory=dict)

    def lead(self, concept: str, leads_to: str) -> None:
        """Record that attention flows from ``concept`` to ``leads_to``."""
        for c in (concept, leads_to):
            if not c or not c.strip():
                raise ValueError("concepts must be non-empty")
        self.edges.setdefault(concept.strip(), [])
        if leads_to.strip() not in self.edges[concept.strip()]:
            self.edges[concept.strip()].append(leads_to.strip())

    def outflows(self, concept: str) -> List[str]:
        return list(self.edges.get(concept, []))

    def concepts(self) -> Set[str]:
        seen = set(self.edges)
        for targets in self.edges.values():
            seen.update(targets)
        return seen


def flow(
    field: FlowField, start: str, max_depth: int = 5, breadth: bool = False
) -> List[Dict[str, object]]:
    """Trace trajectories from ``start``, following "leads to" edges.

    Each trajectory is one path attention takes: a list of concepts and
    its length. Cycles terminate the path (no infinite loops). With
    ``breadth=False`` (default) paths run deep first; with
    ``breadth=True`` every path is the shortest route to its endpoint.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    paths: List[List[str]] = []
    if breadth:
        _bfs(field, start, max_depth, paths)
    else:
        _dfs(field, start, max_depth, [start], paths)
    return [{"trajectory": p, "length": len(p) - 1, "endpoint": p[-1]} for p in paths]


def _dfs(
    field: FlowField, node: str, remaining: int, path: List[str], out: List[List[str]]
) -> None:
    targets = field.outflows(node)
    advanced = False
    for nxt in targets:
        if nxt in path:  # cycle: stop this trajectory here
            continue
        if remaining - 1 < 0:
            continue
        advanced = True
        _dfs(field, nxt, remaining - 1, path + [nxt], out)
    if not advanced and len(path) > 1:
        out.append(path)


def _bfs(field: FlowField, start: str, max_depth: int, out: List[List[str]]) -> None:
    queue: deque = deque()
    queue.append((start, [start]))
    seen_endpoints: Set[str] = set()
    while queue:
        node, path = queue.popleft()
        extended = False
        for nxt in field.outflows(node):
            if nxt in path:
                continue
            if len(path) - 1 >= max_depth:
                continue
            extended = True
            new_path = path + [nxt]
            queue.append((nxt, new_path))
        if not extended and len(path) > 1 and path[-1] not in seen_endpoints:
            seen_endpoints.add(path[-1])
            out.append(path)


def flowscape(
    field: FlowField, starts: List[str], max_depth: int = 5
) -> Dict[str, object]:
    """The traced map for one or more starting concepts.

    Returns per-start trajectories plus the aggregate read-out: hubs
    (concepts many trajectories pass through), sinks (concepts where
    flows terminate), and coverage (how much of the known field the
    flowscape reaches). A flowscape is a *traced* object — it describes
    the given edges, nothing more.
    """
    per_start = {s: flow(field, s, max_depth=max_depth) for s in starts}
    pass_through: Dict[str, int] = {}
    sinks: Dict[str, int] = {}
    reached: Set[str] = set()
    for trajs in per_start.values():
        for t in trajs:
            path = t["trajectory"]
            reached.update(path)
            for c in path[1:-1]:
                pass_through[c] = pass_through.get(c, 0) + 1
            sinks[t["endpoint"]] = sinks.get(t["endpoint"], 0) + 1
    hubs = sorted(pass_through, key=lambda c: -pass_through[c])
    sink_ranked = sorted(sinks, key=lambda c: -sinks[c])
    total_concepts = len(field.concepts())
    return {
        "starts": starts,
        "trajectories": per_start,
        "hubs": [{"concept": c, "pass_through": pass_through[c]} for c in hubs],
        "sinks": [{"concept": c, "arrivals": sinks[c]} for c in sink_ranked],
        "coverage": {
            "reached": len(reached),
            "total": total_concepts,
            "fraction": round(len(reached) / total_concepts, 4)
            if total_concepts
            else 0.0,
        },
    }


def compare_with_classification(
    start: str,
    field: FlowField,
    classify: Callable[[str], List[str]],
    max_depth: int = 3,
) -> Dict[str, object]:
    """Flow view vs. classification view of the same concept, side by side.

    ``classify`` is the classifier: it takes the concept and returns the
    boxes it belongs to ("what it IS"). The flow view traces where
    attention goes ("what it leads to"). The comparison is the whole
    point of water logic: same starting point, two incompatible maps.
    """
    boxes = classify(start)
    trajs = flow(field, start, max_depth=max_depth)
    destinations = sorted({t["endpoint"] for t in trajs})
    overlap = sorted(set(boxes) & set(destinations))
    return {
        "concept": start,
        "classification_view": {
            "question": "what IS this?",
            "boxes": boxes,
        },
        "flow_view": {
            "question": "what does this lead to?",
            "destinations": destinations,
            "trajectories": len(trajs),
        },
        "overlap": overlap,
        "note": (
            "Overlap is usually small: classification parks a concept "
            "in boxes, flow follows it into neighbors. That gap is the "
            "reason to keep both views."
        ),
    }
