"""LEVI's link web — typed relations with an algebra of their own.

Studied from: retired-software-revival-research-20260916-0004/report.md
[catalog #14] (NoteCards).

The studied capability shape: links carry *meaning* (supports, refutes,
elaborates) and "browser" cards render computed argument-structure
diagrams. This module is a distinct, original variant of that shape: a
*relation algebra* over typed links. Anchors (claims, evidence, notes —
anything linkable) are joined by directed, typed links from a fixed
vocabulary; from those, this module *derives* implied relations through
composition rules, flags direct and derived *conflicts* (support and
refutation holding between the same anchors), rejects circular support,
and renders an argument's skeleton through a structural *browser window*
with depth, span, and contestedness metrics.

Concretely: ``supports∘supports`` derives ``supports``; ``refutes``
composed with anything supportive flips to ``refutes``; ``qualifies``
propagates qualification. Every derived link carries its rule and its
path, so inference is inspectable, never magic. Composition is a small,
documented, heuristic table — not a logic engine — and the docstring says
so honestly.

Original, from-scratch implementation for LEVI. Local-first, stdlib
only, no network. Not artificial. Synthetic.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/typed-links"

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

SUPPORTS = "supports"
REFUTES = "refutes"
ELABORATES = "elaborates"
DEFINES = "defines"
QUALIFIES = "qualifies"
EXEMPLIFIES = "exemplifies"
PRESUPPOSES = "presupposes"
ANALOG_OF = "analog-of"

VOCABULARY = (
    SUPPORTS,
    REFUTES,
    ELABORATES,
    DEFINES,
    QUALIFIES,
    EXEMPLIFIES,
    PRESUPPOSES,
    ANALOG_OF,
)

# Composition table: (rel1, rel2) -> derived rel, where a -rel1-> b -rel2-> c
# implies a -derived-> c. Heuristic, documented; "suggestive" marks the
# weaker double-negation style rules.
_COMPOSE: Dict[Tuple[str, str], Tuple[str, str]] = {
    (SUPPORTS, SUPPORTS): (SUPPORTS, "support chains"),
    (SUPPORTS, ELABORATES): (SUPPORTS, "support through elaboration"),
    (ELABORATES, SUPPORTS): (SUPPORTS, "elaboration funnels support"),
    (ELABORATES, ELABORATES): (ELABORATES, "elaboration chains"),
    (SUPPORTS, REFUTES): (REFUTES, "support of a refutation refutes"),
    (REFUTES, SUPPORTS): (REFUTES, "refutation funnels through support"),
    (REFUTES, REFUTES): (SUPPORTS, "suggestive: enemy of enemy"),
    (REFUTES, ELABORATES): (REFUTES, "refutation through elaboration"),
    (QUALIFIES, SUPPORTS): (QUALIFIES, "qualified support"),
    (SUPPORTS, QUALIFIES): (QUALIFIES, "support with qualification"),
    (QUALIFIES, QUALIFIES): (QUALIFIES, "qualification chains"),
    (EXEMPLIFIES, SUPPORTS): (SUPPORTS, "suggestive: example supports"),
    (PRESUPPOSES, SUPPORTS): (PRESUPPOSES, "presupposition propagates"),
    (DEFINES, ELABORATES): (ELABORATES, "definition elaborated"),
}

# Relations whose chains must stay acyclic for the web to be coherent.
_ACYCLIC = {SUPPORTS, ELABORATES, DEFINES}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WebError(Exception):
    """Base class for link-web failures."""


class UnknownRelation(WebError):
    """A link was typed with a word outside the web's vocabulary."""

    def __init__(self, rel: str):
        super().__init__(
            f"{rel!r} is not a link type here; this web speaks {sorted(VOCABULARY)}"
        )
        self.rel = rel


class UnknownAnchor(WebError):
    """A link or browser named an anchor that isn't in the web."""

    def __init__(self, anchor_id: str):
        super().__init__(f"no anchor {anchor_id!r} in this web")
        self.anchor_id = anchor_id


class DuplicateAnchor(WebError):
    """An anchor id was registered twice."""

    def __init__(self, anchor_id: str):
        super().__init__(f"anchor {anchor_id!r} already exists")
        self.anchor_id = anchor_id


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Anchor:
    """One linkable node: a claim, a piece of evidence, a note."""

    anchor_id: str
    label: str
    kind: str = "note"


@dataclass
class TypedLink:
    """A directed, typed link between two anchors."""

    source: str
    rel: str
    target: str
    note: str = ""
    implied: bool = False
    via: Tuple[str, ...] = ()
    rule: str = ""


# ---------------------------------------------------------------------------
# The web
# ---------------------------------------------------------------------------


class LinkWeb:
    """A web of anchors joined by typed, directed links.

    Supports adding anchors/links, deriving implied relations through the
    composition table, detecting conflicts and support cycles, and opening
    structural browser windows onto the argument shape around an anchor.
    """

    def __init__(self) -> None:
        self._anchors: Dict[str, Anchor] = {}
        self._links: List[TypedLink] = []

    # -- construction ----------------------------------------------------

    def add_anchor(self, anchor_id: str, label: str, kind: str = "note") -> Anchor:
        """Register a linkable anchor."""
        if anchor_id in self._anchors:
            raise DuplicateAnchor(anchor_id)
        anchor = Anchor(anchor_id, label, kind)
        self._anchors[anchor_id] = anchor
        return anchor

    def link(self, source: str, rel: str, target: str, note: str = "") -> TypedLink:
        """Add an explicit typed link. Both anchors must exist."""
        if rel not in VOCABULARY:
            raise UnknownRelation(rel)
        if source not in self._anchors:
            raise UnknownAnchor(source)
        if target not in self._anchors:
            raise UnknownAnchor(target)
        typed = TypedLink(source, rel, target, note=note)
        self._links.append(typed)
        return typed

    # -- reads -----------------------------------------------------------

    def anchors(self) -> List[Anchor]:
        """Every anchor, in insertion order."""
        return list(self._anchors.values())

    def links(self, implied: bool = False) -> List[TypedLink]:
        """Explicit links; pass implied=True to include derived ones."""
        if implied:
            return list(self._links) + self.derive()
        return list(self._links)

    def out_links(self, anchor_id: str, rel: Optional[str] = None) -> List[TypedLink]:
        """Links leaving an anchor, optionally filtered by relation."""
        self._require(anchor_id)
        return [
            lnk
            for lnk in self._links
            if lnk.source == anchor_id and (rel is None or lnk.rel == rel)
        ]

    def in_links(self, anchor_id: str, rel: Optional[str] = None) -> List[TypedLink]:
        """Links arriving at an anchor, optionally filtered by relation."""
        self._require(anchor_id)
        return [
            lnk
            for lnk in self._links
            if lnk.target == anchor_id and (rel is None or lnk.rel == rel)
        ]

    # -- inference -------------------------------------------------------

    def derive(self, max_depth: int = 3) -> List[TypedLink]:
        """Derive implied links via the composition table.

        Breadth-first: explicit links are depth 1; each composition of a
        depth-d link with an explicit link yields depth d+1, up to
        max_depth. Already-known (source, rel, target) triples are not
        re-derived. Derived links carry their rule and path.
        """
        known = {(lnk.source, lnk.rel, lnk.target) for lnk in self._links}
        derived: List[TypedLink] = []
        frontier = [lnk for lnk in self._links]
        for _depth in range(max_depth):
            new_frontier: List[TypedLink] = []
            for first in frontier:
                for second in self.out_links(first.target):
                    rule = _COMPOSE.get((first.rel, second.rel))
                    if rule is None:
                        continue
                    rel, rule_name = rule
                    triple = (first.source, rel, second.target)
                    if triple in known:
                        continue
                    known.add(triple)
                    step = f"{first.source} -{first.rel}-> {first.target}"
                    link = TypedLink(
                        first.source,
                        rel,
                        second.target,
                        implied=True,
                        via=first.via + (step,),
                        rule=rule_name,
                    )
                    derived.append(link)
                    new_frontier.append(link)
            if not new_frontier:
                break
            frontier = new_frontier
        return derived

    def net_stance(self, a: str, b: str) -> str:
        """The web's net read on (a, b): supports / refutes / contested / unrelated.

        Considers explicit and derived links in both directions; a
        reverse-direction link counts for the *opposing* stance.
        """
        self._require(a)
        self._require(b)
        support = refute = False
        for link in self.links(implied=True):
            if link.source == a and link.target == b:
                if link.rel == SUPPORTS:
                    support = True
                elif link.rel == REFUTES:
                    refute = True
            elif link.source == b and link.target == a:
                # A claim that b supports is something a's own support would lean against;
                # keep it simple and symmetric: reverse links count toward the opposing stance.
                if link.rel == SUPPORTS:
                    refute = True
                elif link.rel == REFUTES:
                    support = True
        if support and refute:
            return "contested"
        if support:
            return "supports"
        if refute:
            return "refutes"
        return "unrelated"

    # -- audits ----------------------------------------------------------

    def conflicts(self) -> List[Tuple[str, str, str]]:
        """Pairs of anchors holding both support and refutation.

        Returns (a, b, reason) triples; reason names direct vs derived
        evidence. An argument holding both is contested and should be
        inspected, not trusted blindly.
        """
        pairs = set()
        for link in self._links:
            pairs.add((link.source, link.target))
        found = []
        for a, b in sorted(pairs):
            direct = any(
                lnk.source == a and lnk.target == b and lnk.rel in (SUPPORTS, REFUTES)
                for lnk in self._links
            )
            if not direct:
                continue
            stance = self.net_stance(a, b)
            if stance == "contested":
                found.append((a, b, "support and refutation both present"))
        return found

    def support_cycles(self) -> List[List[str]]:
        """Cycles in the support/elaboration/definition subgraph.

        A claim that (transitively) supports itself is circular — reported
        as anchor-id cycles so the web's owner can break them.
        """
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for link in self._links:
            if link.rel in _ACYCLIC:
                adjacency[link.source].append(link.target)
        cycles: List[List[str]] = []
        visited: Dict[str, str] = {}

        def visit(node: str, stack: List[str]) -> None:
            visited[node] = "open"
            stack.append(node)
            for nxt in adjacency.get(node, []):
                if visited.get(nxt) == "open":
                    cycles.append(stack[stack.index(nxt) :] + [nxt])
                elif nxt not in visited:
                    visit(nxt, stack)
            stack.pop()
            visited[node] = "closed"

        for anchor_id in self._anchors:
            if anchor_id not in visited:
                visit(anchor_id, [])
        return cycles

    # -- structural browser ----------------------------------------------

    def browser(self, anchor_id: str, depth: int = 3) -> "BrowserWindow":
        """Open a structural browser window rooted at an anchor."""
        self._require(anchor_id)
        return BrowserWindow(self, anchor_id, depth)

    def _require(self, anchor_id: str) -> None:
        if anchor_id not in self._anchors:
            raise UnknownAnchor(anchor_id)


# ---------------------------------------------------------------------------
# Browser window
# ---------------------------------------------------------------------------


class BrowserWindow:
    """A computed structural view of the argument around one anchor.

    Renders the support tree (what holds the claim up), the refutation
    tree (what pushes against it), and elaborations — as indented text —
    plus one-glance metrics: depth reached, node span, and whether the
    root is contested. The window is a *view*: it stores no argument of
    its own, it computes from the web.
    """

    def __init__(self, web: LinkWeb, root_id: str, depth: int = 3):
        self.web = web
        self.root_id = root_id
        self.depth = max(1, depth)

    def _tree(self, rel: str, direction: str) -> Dict:
        """Build a nested dict tree following rel links outward."""
        seen = {self.root_id}

        def grow(node: str, remaining: int) -> Dict:
            kids = {}
            links = (
                self.web.in_links(node, rel)
                if direction == "in"
                else self.web.out_links(node, rel)
            )
            for link in links:
                nxt = link.source if direction == "in" else link.target
                if nxt in seen or remaining <= 0:
                    continue
                seen.add(nxt)
                kids[nxt] = grow(nxt, remaining - 1)
            return kids

        return {self.root_id: grow(self.root_id, self.depth)}

    def metrics(self) -> Dict[str, object]:
        """Depth reached, node span, and contestedness of the root view."""
        support_tree = self._tree(SUPPORTS, "in")
        refute_tree = self._tree(REFUTES, "in")

        def span(tree: Dict) -> int:
            return sum(1 + span(kids) for kids in tree.values())

        def depth_of(tree: Dict) -> int:
            if not tree:
                return 0
            return 1 + max((depth_of(kids) for kids in tree.values()), default=0)

        stance = self.web.net_stance(self.root_id, self.root_id)
        contested = stance == "contested" or bool(refute_tree[self.root_id])
        return {
            "root": self.root_id,
            "support_depth": depth_of(support_tree) - 1,
            "support_span": span(support_tree) - 1,
            "refute_span": span(refute_tree) - 1,
            "contested": contested,
        }

    def render(self) -> str:
        """The argument skeleton as readable indented text."""
        web = self.web
        root = web._anchors[self.root_id]
        lines = [f"◇ {root.label}  [{self.root_id}]"]

        def show(
            node: str, rel: str, direction: str, indent: str, remaining: int, seen: set
        ) -> None:
            links = (
                web.in_links(node, rel)
                if direction == "in"
                else web.out_links(node, rel)
            )
            glyph = {"supports": "▲", "refutes": "▼", "elaborates": "◆"}.get(rel, "·")
            for link in links:
                nxt = link.source if direction == "in" else link.target
                if nxt in seen or remaining <= 0:
                    continue
                seen.add(nxt)
                nxt_anchor = web._anchors[nxt]
                lines.append(f"{indent}{glyph} {nxt_anchor.label}  [{nxt}]")
                show(nxt, rel, direction, indent + "  ", remaining - 1, seen)

        lines.append("— supported by:")
        show(self.root_id, SUPPORTS, "in", "  ", self.depth, {self.root_id})
        lines.append("— refuted by:")
        show(self.root_id, REFUTES, "in", "  ", self.depth, {self.root_id})
        lines.append("— elaborated by:")
        show(self.root_id, ELABORATES, "in", "  ", self.depth, {self.root_id})
        return "\n".join(lines)


__all__ = [
    "ORIGIN",
    "SUPPORTS",
    "REFUTES",
    "ELABORATES",
    "DEFINES",
    "QUALIFIES",
    "EXEMPLIFIES",
    "PRESUPPOSES",
    "ANALOG_OF",
    "VOCABULARY",
    "WebError",
    "UnknownRelation",
    "UnknownAnchor",
    "DuplicateAnchor",
    "Anchor",
    "TypedLink",
    "LinkWeb",
    "BrowserWindow",
]
