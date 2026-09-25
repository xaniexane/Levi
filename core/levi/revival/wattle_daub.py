"""wattle_daub — tensile frame + compressive fill memory.

Studied from: lost-crafts-20260916 — report.md [Batch 3]
(Wattle-and-Daub / Cob).

Load-bearing idea: wattle is the tensile frame — woven hazel rods that
hold the wall's shape; daub is the compressive fill — mud, clay, and
straw pressed into the weave, re-wettable and re-workable. LEVI's take:
memory is an associative link-graph of ``Node``s (the wattle) joined by
typed edges, with consolidated learnings pressed into nodes as ``Daub``
summaries (the compressive fill). Pressing many small notes into one
node compacts the graph; re-wetting expands a daub summary back toward
its source notes. Daub is a heuristic compression — the module says so —
not lossless storage.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/wattle-daub"


@dataclass
class Edge:
    """One associative link between wattle nodes."""

    target: str
    kind: str  # e.g. "reminds", "causes", "part-of", "contradicts"
    weight: float = 1.0


@dataclass
class Daub:
    """A pressed-in consolidation: heuristic summary of source notes.

    ``source_ids`` keeps provenance so the fill can be re-wetted later.
    """

    summary: str
    source_ids: List[str] = field(default_factory=list)
    pressed_at: float = 0.0
    damp: bool = False  # True after rewet(): the fill is workable again


@dataclass
class Node:
    id: str
    label: str
    edges: List[Edge] = field(default_factory=list)
    daub: Optional[Daub] = None


class WattleDaub:
    """Associative memory: woven link-graph (wattle) + pressed fill (daub)."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self._notes: Dict[str, str] = {}  # note id -> raw text (the straw)

    # -- weaving the frame -------------------------------------------------

    def weave(self, label: str) -> Node:
        node = Node(id=uuid.uuid4().hex[:8], label=label)
        self.nodes[node.id] = node
        return node

    def link(self, from_id: str, to_id: str, kind: str, weight: float = 1.0) -> Edge:
        edge = Edge(target=to_id, kind=kind, weight=weight)
        self.nodes[from_id].edges.append(edge)
        return edge

    def stake_note(self, node_id: str, text: str) -> str:
        """Pin a raw note (straw) to a node, awaiting pressing."""
        note_id = uuid.uuid4().hex[:8]
        self._notes[note_id] = text
        self.nodes[node_id].edges.append(Edge(target=f"note:{note_id}", kind="note"))
        return note_id

    def note_text(self, note_id: str) -> str:
        return self._notes[note_id]

    # -- pressing the daub ---------------------------------------------------

    def press(
        self,
        node_id: str,
        summary: str,
        now: Optional[float] = None,
    ) -> Daub:
        """Press the node's staked notes into one consolidated fill.

        The summary is supplied by the caller (a model or a human) — this
        module only packs and tracks provenance. Notes stay in the
        ledger so the fill can be re-wetted later.
        """
        node = self.nodes[node_id]
        note_ids = [
            e.target.split("note:", 1)[1]
            for e in node.edges
            if e.target.startswith("note:")
        ]
        node.daub = Daub(
            summary=summary,
            source_ids=note_ids,
            pressed_at=now if now is not None else time.time(),
        )
        return node.daub

    def rewet(self, node_id: str) -> List[str]:
        """Re-wet a pressed fill: return the source notes, mark fill damp."""
        node = self.nodes[node_id]
        if node.daub is None:
            raise KeyError(f"node {node_id!r} has no daub to re-wet")
        node.daub.damp = True
        return [self._notes[nid] for nid in node.daub.source_ids]

    # -- walking the frame -----------------------------------------------------

    def neighbors(
        self, node_id: str, kind: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """(target, kind) pairs; node-links only (note targets excluded)."""
        return [
            (e.target, e.kind)
            for e in self.nodes[node_id].edges
            if not e.target.startswith("note:") and (kind is None or e.kind == kind)
        ]

    def consolidated(self, node_id: str) -> Optional[str]:
        """The pressed summary, or None if the node is unfilled."""
        daub = self.nodes[node_id].daub
        return daub.summary if daub else None
