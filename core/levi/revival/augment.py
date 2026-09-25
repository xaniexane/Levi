"""LEVI's augmentation bench: the machine does the clerical, the human does the thinking.

Studied from: retired-software-revival-research-20260916-0004/report.md (§13).

The load-bearing mechanism of NLS/Augment: *augmentation over automation*.
Complex knowledge lives in structured outlines; the machine performs the
clerical work — numbering, filtering, filing, versioning — while the human
keeps the thinking seat. ``augment`` is LEVI's remix: an ``Outline`` of
``Node``s with *view filters* (a level filter that collapses depth, a
predicate filter that surfaces what matches), automatic outline numbering
done by the machine, and an append-only ``Journal`` that remembers every
move so nothing is ever quietly lost.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional


ORIGIN = "levi-revival/augment"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AugmentError(Exception):
    """Base class for augment failures."""


class UnknownNode(AugmentError):
    """An operation named a node that isn't in the outline."""

    def __init__(self, node_id: str):
        super().__init__(f"no node {node_id!r} in this outline")
        self.node_id = node_id


# ---------------------------------------------------------------------------
# Outline: nodes, filters, machine numbering
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """One thought in the outline. The machine handles position and
    numbering; the human owns the text."""

    node_id: str
    text: str
    note: str = ""
    tags: tuple[str, ...] = ()
    children: list["Node"] = field(default_factory=list)
    parent: Optional["Node"] = field(default=None, repr=False, compare=False)

    def add_child(self, node_id: str, text: str, **kwargs) -> "Node":
        child = Node(node_id=node_id, text=text, parent=self, **kwargs)
        self.children.append(child)
        return child

    def depth(self) -> int:
        d, node = 0, self.parent
        while node is not None:
            d += 1
            node = node.parent
        return d

    def walk(self) -> Iterator["Node"]:
        """Depth-first, the machine's orderly tour of the tree."""
        yield self
        for child in self.children:
            yield from child.walk()


class Outline:
    """A manipulable structured document. Views are computed — filtering
    never deletes, it only changes what the eye is shown."""

    def __init__(self, title: str = "untitled"):
        self.title = title
        self.root = Node(node_id="root", text=title)
        self._counter = 0

    # -- authoring (the human's seat) ---------------------------------------
    def add(self, text: str, parent_id: str = "root", **kwargs) -> Node:
        parent = self.node(parent_id)
        self._counter += 1
        node_id = kwargs.pop("node_id", f"n{self._counter}")
        if node_id in {n.node_id for n in self.root.walk()}:
            raise AugmentError(f"node {node_id!r} already exists")
        return parent.add_child(node_id, text, **kwargs)

    def node(self, node_id: str) -> Node:
        for candidate in self.root.walk():
            if candidate.node_id == node_id:
                return candidate
        raise UnknownNode(node_id)

    def retitle(self, node_id: str, text: str) -> None:
        self.node(node_id).text = text

    def move(self, node_id: str, new_parent_id: str) -> None:
        """Reparent a node. The machine re-files; the human re-thinks."""
        node = self.node(node_id)
        new_parent = self.node(new_parent_id)
        if node is self.root:
            raise AugmentError("the root stays where it is")
        probe = new_parent
        while probe is not None:
            if probe is node:
                raise AugmentError("cannot move a node inside itself")
            probe = probe.parent
        assert node.parent is not None
        node.parent.children.remove(node)
        node.parent = new_parent
        new_parent.children.append(node)

    # -- views (the machine's clerical work) --------------------------------
    def level_view(self, max_depth: int) -> list[tuple[int, Node]]:
        """Collapse everything deeper than ``max_depth``. Depth 0 is the root."""
        if max_depth < 0:
            raise AugmentError("max_depth cannot be negative")
        return [
            (node.depth(), node)
            for node in self.root.walk()
            if node.depth() <= max_depth
        ]

    def predicate_view(
        self, predicate: Callable[[Node], bool]
    ) -> list[tuple[int, Node]]:
        """Surface the nodes that match, each shown with its ancestor path
        for context. Nothing is hidden by deletion — only by the view."""
        hits = [n for n in self.root.walk() if predicate(n) and n is not self.root]
        keep: dict[str, Node] = {}
        for hit in hits:
            probe: Optional[Node] = hit
            while probe is not None and probe is not self.root:
                keep[probe.node_id] = probe
                probe = probe.parent
        ordered = [n for n in self.root.walk() if n.node_id in keep]
        return [(n.depth(), n) for n in ordered]

    def numbered(self, view: Optional[list[tuple[int, Node]]] = None) -> list[str]:
        """Machine clerical work #1: outline numbering (1., 1.1, 1.2, ...).

        Accepts any view so numbering always matches what is shown.
        """
        view = view if view is not None else [(n.depth(), n) for n in self.root.walk()]
        counters: list[int] = []
        lines: list[str] = []
        for depth, node in view:
            if node is self.root:
                continue
            while len(counters) <= depth:
                counters.append(0)
            counters = counters[: depth + 1]
            counters[depth] += 1
            for deeper in range(depth + 1, len(counters)):
                counters[deeper] = 0
            number = ".".join(str(c) for c in counters[1 : depth + 1] if c)
            lines.append(f"{number}. {node.text}")
        return lines

    def render(self, view: Optional[list[tuple[int, Node]]] = None) -> str:
        """Indentation view of the outline (or of a filtered view of it)."""
        view = view if view is not None else [(n.depth(), n) for n in self.root.walk()]
        return "\n".join(f"{'  ' * depth}• {node.text}" for depth, node in view)


# ---------------------------------------------------------------------------
# Journal: append-only memory of every move
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JournalEntry:
    seq: int
    timestamp: float
    action: str
    detail: str = ""

    def render(self) -> str:
        return f"[{self.seq}] {self.action}: {self.detail}".rstrip(": ")


class Journal:
    """Append-only. Entries are never edited or deleted — the past is
    the past; if a move was wrong, a new entry says so."""

    def __init__(self):
        self._entries: list[JournalEntry] = []

    def log(self, action: str, detail: str = "") -> JournalEntry:
        entry = JournalEntry(
            seq=len(self._entries) + 1,
            timestamp=time.time(),
            action=action,
            detail=detail,
        )
        self._entries.append(entry)
        return entry

    def __iter__(self) -> Iterator[JournalEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def since(self, seq: int) -> list[JournalEntry]:
        """Everything after (and not including) entry ``seq``."""
        return [e for e in self._entries if e.seq > seq]

    def render(self) -> str:
        return "\n".join(e.render() for e in self._entries)


__all__ = [
    "AugmentError",
    "UnknownNode",
    "Node",
    "Outline",
    "JournalEntry",
    "Journal",
]
