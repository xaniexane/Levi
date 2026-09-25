"""LEVI's typed item graph: ask what things *are* and how they *relate*, not where they're filed.

Studied from: retired-software-revival-research-20260916-0004/report.md (§5).

The load-bearing mechanism of WinFS: data as typed **Items** with schemas,
**relationships as first-class citizens**, and organization by query
instead of by folder. ``thingraph`` is LEVI's remix at library scale: a
``Graph`` of typed items joined by named ``Edge``s that are objects in
their own right (an edge can carry its own properties — when, why, how
sure). Queries run *by type* and *by relationship traversal*; there are no
folders here, and nothing needs them.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


ORIGIN = "levi-revival/thingraph"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ThingraphError(Exception):
    """Base class for thingraph failures."""


class UnknownItem(ThingraphError):
    """A relationship or query named an item that isn't in the graph."""

    def __init__(self, item_id: str):
        super().__init__(f"no item {item_id!r} in this graph")
        self.item_id = item_id


class UnknownEdge(ThingraphError):
    """An operation named an edge id that doesn't exist."""


# ---------------------------------------------------------------------------
# Items and first-class edges
# ---------------------------------------------------------------------------


@dataclass
class Item:
    """One typed thing: people, tasks, documents, events — whatever the
    graph is asked to hold. ``kind`` is the type; ``props`` is the rest."""

    item_id: str
    kind: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """A relationship as a first-class citizen: it has an id, a name, a
    direction, and room for its own story (props)."""

    edge_id: str
    name: str
    source: str
    target: str
    props: dict[str, Any] = field(default_factory=dict)


class Graph:
    """One typed graph. Items are typed, relationships are edges, and
    every question is a query — never a folder path."""

    def __init__(self):
        self.items: dict[str, Item] = {}
        self.edges: dict[str, Edge] = {}
        self._edge_counter = 0

    # -- authoring ----------------------------------------------------------
    def add_item(
        self, item_id: str, kind: str, props: Optional[dict[str, Any]] = None
    ) -> Item:
        if not item_id or not item_id.strip():
            raise ThingraphError("item_id must be non-empty")
        if not kind or not kind.strip():
            raise ThingraphError("kind must be non-empty")
        if item_id in self.items:
            raise ThingraphError(f"item {item_id!r} is already in the graph")
        item = Item(item_id=item_id, kind=kind, props=dict(props or {}))
        self.items[item_id] = item
        return item

    def relate(
        self,
        source: str,
        name: str,
        target: str,
        props: Optional[dict[str, Any]] = None,
    ) -> Edge:
        """Draw a named relationship between two items. The edge itself
        is stored — queryable, annotatable, removable."""
        for item_id in (source, target):
            if item_id not in self.items:
                raise UnknownItem(item_id)
        if not name or not name.strip():
            raise ThingraphError("relationship name must be non-empty")
        self._edge_counter += 1
        edge = Edge(
            edge_id=f"e{self._edge_counter}",
            name=name,
            source=source,
            target=target,
            props=dict(props or {}),
        )
        self.edges[edge.edge_id] = edge
        return edge

    def unrelate(self, edge_id: str) -> Edge:
        if edge_id not in self.edges:
            raise UnknownEdge(f"no edge {edge_id!r}")
        return self.edges.pop(edge_id)

    def remove_item(self, item_id: str) -> Item:
        """Remove an item and every edge that touches it — a relationship
        to something gone is a relationship to nothing."""
        if item_id not in self.items:
            raise UnknownItem(item_id)
        for edge_id in [
            e.edge_id
            for e in self.edges.values()
            if e.source == item_id or e.target == item_id
        ]:
            del self.edges[edge_id]
        return self.items.pop(item_id)

    # -- queries -------------------------------------------------------------
    def item(self, item_id: str) -> Item:
        if item_id not in self.items:
            raise UnknownItem(item_id)
        return self.items[item_id]

    def by_kind(self, kind: str) -> list[Item]:
        """All items of a type — the "virtual folder" that needs no folder."""
        return [i for i in self.items.values() if i.kind == kind]

    def find(self, kind: Optional[str] = None, **props: Any) -> list[Item]:
        """Items whose kind and properties match. ``find(kind="task",
        status="open")`` reads like the question it is."""
        out = []
        for item in self.items.values():
            if kind is not None and item.kind != kind:
                continue
            if all(item.props.get(k) == v for k, v in props.items()):
                out.append(item)
        return out

    def edges_from(self, item_id: str, name: Optional[str] = None) -> list[Edge]:
        self.item(item_id)  # validates
        return [
            e
            for e in self.edges.values()
            if e.source == item_id and (name is None or e.name == name)
        ]

    def edges_to(self, item_id: str, name: Optional[str] = None) -> list[Edge]:
        self.item(item_id)  # validates
        return [
            e
            for e in self.edges.values()
            if e.target == item_id and (name is None or e.name == name)
        ]

    def related(
        self, item_id: str, name: Optional[str] = None
    ) -> list[tuple[Edge, Item]]:
        """(edge, item) pairs reachable by following outgoing relationships."""
        return [(e, self.items[e.target]) for e in self.edges_from(item_id, name)]

    def traverse(
        self,
        start: str,
        name: Optional[str] = None,
        depth: int = 1,
        reverse: bool = False,
    ) -> list[Item]:
        """Walk the graph along named relationships up to ``depth`` hops.
        ``reverse=True`` walks edges backwards (who relates *to* me?).

        Breadth-first, cycle-safe, and the start item is never returned
        as its own neighbor.
        """
        self.item(start)  # validates
        if depth < 1:
            raise ThingraphError("depth must be at least 1")
        seen = {start}
        frontier = [start]
        found: list[Item] = []
        for _ in range(depth):
            nxt: list[str] = []
            for item_id in frontier:
                edges = (
                    self.edges_to(item_id, name)
                    if reverse
                    else self.edges_from(item_id, name)
                )
                for edge in edges:
                    other = edge.source if reverse else edge.target
                    if other not in seen:
                        seen.add(other)
                        nxt.append(other)
                        found.append(self.items[other])
            frontier = nxt
            if not frontier:
                break
        return found

    def kinds(self) -> list[str]:
        return sorted({i.kind for i in self.items.values()})

    def relationship_names(self) -> list[str]:
        return sorted({e.name for e in self.edges.values()})

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[Item]:
        return iter(self.items.values())


__all__ = [
    "ThingraphError",
    "UnknownItem",
    "UnknownEdge",
    "Item",
    "Edge",
    "Graph",
]
