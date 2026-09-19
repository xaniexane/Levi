"""morphoutline — hoisting, cloning, and shape-shifting outlines.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 14).

The load-bearing idea: an outliner where structure is *live* — you focus
a subtree (hoist), you see one node in two places at once (clone), and the
same outline wears different shapes on demand (flat list, table, slides).

LEVI's take: ``Outline`` is a small tree of ``Node``s with plain methods,
no windowing system, no rich text engine. A clone is a real shared
reference — edit it anywhere and both views move, because there is only
one node. ``flatten``, ``tabulate`` and ``slides`` are pure transforms of
the tree, so the outline stays the source of truth no matter which skin
you look at.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from typing import List, Optional

ORIGIN = "levi-revival/morphoutline"


class Node:
    """One outline node: text, children, and an optional note."""

    def __init__(self, text: str, note: str = "") -> None:
        self.text = text
        self.note = note
        self.children: List[Node] = []

    def add(self, child: "Node") -> "Node":
        self.children.append(child)
        return child

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Node({self.text!r})"


class Outline:
    """A live outline tree with hoist, clone and shape transforms."""

    def __init__(self, title: str = "") -> None:
        self.title = title
        self.roots: List[Node] = []
        self.focus: Optional[Node] = None  # None == whole tree is visible

    # -- construction --------------------------------------------------
    def add_root(self, node: Node) -> Node:
        self.roots.append(node)
        return node

    def _visible(self) -> List[Node]:
        return [self.focus] if self.focus is not None else self.roots

    # -- hoisting ------------------------------------------------------
    def hoist(self, node: Node) -> None:
        """Focus the outline on ``node``'s subtree; everything else hides."""
        self.focus = node

    def unhoist(self) -> None:
        """Return to the full tree."""
        self.focus = None

    def find(self, text: str) -> Optional[Node]:
        """First node whose text matches, depth-first over the whole tree."""
        stack = list(self.roots)
        while stack:
            node = stack.pop(0)
            if node.text == text:
                return node
            stack[0:0] = node.children
        return None

    # -- cloning -------------------------------------------------------
    def clone(self, node: Node, under: Node) -> Node:
        """Make ``node`` appear under ``under`` too.

        The clone is the SAME node object — edits made through either
        appearance reflect in both, because there is only one node.
        """
        under.add(node)
        return node

    def appears(self, node: Node) -> int:
        """How many places in the tree this node appears."""
        count = 0
        stack = list(self.roots)
        seen_roots = 0
        while stack:
            current = stack.pop(0)
            if current is node:
                count += 1
            else:
                # still walk children; node may sit under several parents
                stack[0:0] = current.children
            seen_roots += 1
            if seen_roots > 10000:  # pragma: no cover - pathological guard
                break
        # Re-walk children of the node itself once, to keep this simple
        # without infinite recursion on clones:
        return count

    # -- transforms ----------------------------------------------------
    def flatten(self) -> List[tuple]:
        """Outline -> flat list of ``(depth, text)`` tuples."""
        rows: List[tuple] = []

        def walk(node: Node, depth: int) -> None:
            rows.append((depth, node.text))
            for child in node.children:
                walk(child, depth + 1)

        for root in self._visible():
            walk(root, 0)
        return rows

    def tabulate(self) -> List[dict]:
        """Outline -> table rows: path, text, depth, children."""
        rows: List[dict] = []

        def walk(node: Node, depth: int, path: str) -> None:
            rows.append(
                {
                    "path": path,
                    "text": node.text,
                    "depth": depth,
                    "children": len(node.children),
                }
            )
            for i, child in enumerate(node.children, 1):
                walk(child, depth + 1, f"{path}.{i}")

        for i, root in enumerate(self._visible(), 1):
            walk(root, 0, str(i))
        return rows

    def slides(self) -> List[dict]:
        """Outline -> slide-like sections: top level = slides, children = bullets."""
        slides: List[dict] = []
        for root in self._visible():
            slides.append(
                {
                    "title": root.text,
                    "bullets": [child.text for child in root.children],
                }
            )
        return slides
