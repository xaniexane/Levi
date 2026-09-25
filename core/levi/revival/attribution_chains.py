"""Attribution chains: every remixed idea carries its provenance chain.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #7] (attribution chains: every remixed idea carries its provenance
chain — Xanadu-style trails).

This is an original, from-scratch implementation for LEVI. Ideas live in a
``Ledger``. An idea may *derive from* earlier ideas (its sources); deriving
records a ``Derivation`` edge carrying the author's note about *what was
taken* (a quote, a technique, a counter-argument). The full ancestry of any
idea is therefore a chain — a provenance trail from the newest remix back
through every ancestor to the root ideas that had no sources.

``trail(idea_id)`` returns the chain as an ordered list, newest first, each
link showing what was taken from that ancestor. ``roots()`` finds ultimate
ancestors. ``credit()`` walks the whole trail and tallies contribution weight
per originator: direct sources weigh more than distant ones (halving per
generation), so credit decays honestly down the chain rather than flattening.

Cycles are refused: deriving an idea from one of its own descendants (or
itself) raises ``ChainError``. Sources are recorded at derivation time and
are immutable afterwards — provenance is a record, not an editable story.

Honest limits:
- Credit weights are a heuristic (halving per generation), labeled as such.
  They are a convention for display, not a measure of actual intellectual
  contribution.
- The ledger records what authors *declare* they took. It cannot verify the
  declaration against the real world.
- Roots are ideas with no recorded sources *in this ledger*, not
  necessarily originators in any absolute sense.

Public surface:
- ``Idea``, ``Derivation``, ``Ledger``: ``add_idea``, ``derive``,
  ``trail``, ``roots``, ``credit``, ``descendants``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/attribution-chains"


class ChainError(ValueError):
    """Raised when a derivation would break provenance integrity."""


@dataclass
class Idea:
    """One recorded idea. Sources are immutable once recorded."""

    id: int
    title: str
    originator: str
    note: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class Derivation:
    """One link: `child` took `what` from `parent`, per the author."""

    child_id: int
    parent_id: int
    what: str  # what was taken: quote, technique, counter-argument, ...


class Ledger:
    """Provenance ledger: ideas plus immutable derivation edges."""

    def __init__(self) -> None:
        self._ideas: Dict[int, Idea] = {}
        self._edges: List[Derivation] = []
        self._parents: Dict[int, List[Derivation]] = {}
        self._next_id = 1

    # -- recording ------------------------------------------------------------

    def add_idea(self, title: str, originator: str, note: str = "") -> Idea:
        if not title.strip():
            raise ChainError("an idea needs a title")
        if not originator.strip():
            raise ChainError("an idea needs an originator")
        idea = Idea(
            id=self._next_id,
            title=title.strip(),
            originator=originator.strip(),
            note=note.strip(),
        )
        self._ideas[idea.id] = idea
        self._next_id += 1
        return idea

    def get(self, idea_id: int) -> Idea:
        try:
            return self._ideas[idea_id]
        except KeyError:
            raise ChainError(f"no idea #{idea_id}") from None

    def derive(
        self,
        title: str,
        originator: str,
        sources: List[Tuple[int, str]],
        note: str = "",
    ) -> Idea:
        """Record a remix: a new idea plus what it took from each source.

        ``sources`` is a list of ``(parent_id, what_was_taken)`` pairs.
        """
        if not sources:
            raise ChainError("a derivation needs at least one source")
        child = self.add_idea(title, originator, note)
        for parent_id, what in sources:
            self.get(parent_id)  # validates existence
            what = what.strip()
            if not what:
                raise ChainError("each derivation link must say what was taken")
            if parent_id == child.id:
                raise ChainError("an idea cannot derive from itself")
            if parent_id in self._descendants_of(child.id):
                raise ChainError(
                    f"deriving #{child.id} from #{parent_id} would close a cycle"
                )
            edge = Derivation(child_id=child.id, parent_id=parent_id, what=what)
            self._edges.append(edge)
            self._parents.setdefault(child.id, []).append(edge)
        return child

    # -- the trail ---------------------------------------------------------------

    def parents_of(self, idea_id: int) -> List[Derivation]:
        """Direct sources of an idea, in recorded order."""
        self.get(idea_id)
        return list(self._parents.get(idea_id, []))

    def trail(self, idea_id: int) -> List[Dict[str, object]]:
        """Full provenance chain, newest first: idea, what it took, from whom.

        Breadth-first walk so each generation appears together; visited set
        keeps shared ancestors listed once (at their shallowest depth).
        """
        self.get(idea_id)
        chain: List[Dict[str, object]] = []
        visited = {idea_id}
        queue: List[Tuple[int, int]] = [(idea_id, 0)]
        order: List[Tuple[int, int, str]] = []
        while queue:
            current, depth = queue.pop(0)
            for edge in self._parents.get(current, []):
                if edge.parent_id in visited:
                    continue
                visited.add(edge.parent_id)
                order.append((edge.parent_id, depth + 1, edge.what))
                queue.append((edge.parent_id, depth + 1))
        for parent_id, depth, what in order:
            idea = self._ideas[parent_id]
            chain.append(
                {
                    "id": idea.id,
                    "title": idea.title,
                    "originator": idea.originator,
                    "depth": depth,
                    "taken": what,
                }
            )
        return chain

    def roots(self, idea_id: int) -> List[Idea]:
        """Ultimate ancestors: ideas on the trail with no recorded sources."""
        self.get(idea_id)
        ancestors = {link["id"] for link in self.trail(idea_id)}
        ancestors.add(idea_id)
        return sorted(
            (self._ideas[i] for i in ancestors if not self._parents.get(i)),
            key=lambda idea: idea.id,
        )

    def descendants(self, idea_id: int) -> List[Idea]:
        """Every idea that (transitively) derives from this one."""
        self.get(idea_id)
        return sorted(
            (self._ideas[i] for i in self._descendants_of(idea_id)),
            key=lambda idea: idea.id,
        )

    def _descendants_of(self, idea_id: int) -> set:
        found: set = set()
        stack = [idea_id]
        while stack:
            current = stack.pop()
            for edge in self._edges:
                if edge.parent_id == current and edge.child_id not in found:
                    found.add(edge.child_id)
                    stack.append(edge.child_id)
        return found

    # -- credit (heuristic, labeled) --------------------------------------------------

    def credit(self, idea_id: int) -> Dict[str, float]:
        """Contribution weights per originator along the trail.

        Heuristic: the idea's own author gets 1.0; each source generation
        halves (0.5, 0.25, ...). Shared ancestors are counted once, at
        their shallowest depth. Display convention, not a true measure.
        """
        idea = self.get(idea_id)
        weights: Dict[str, float] = {idea.originator: 1.0}
        for link in self.trail(idea_id):
            originator = self._ideas[link["id"]].originator
            weights[originator] = weights.get(originator, 0.0) + 0.5 ** link["depth"]
        return dict(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])))

    def __len__(self) -> int:
        return len(self._ideas)
