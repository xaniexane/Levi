"""LEVI's semantic zoom: zooming changes *what* is shown, not how big it is.

Studied from: revival-50-more-20260916-0009/report-part2.md (§31).

The load-bearing mechanism of Pad++/Jazz: *semantic zooming* — a zoomable
scene graph where moving closer doesn't magnify the same pixels, it
reveals a different level of meaning. Zoom out on a year of life and you
see clusters; zoom into a day and you see the receipt. ``deepzoom`` is
LEVI's remix: a ``Scene`` of ``ZoomNode``s, each node carrying ordered
*detail levels* (a glyph, a label, a summary, the full text), each level
gated by a zoom threshold, and a text ``render(zoom)`` that draws what the
current altitude deserves — nothing more, nothing less.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional


ORIGIN = "levi-revival/deepzoom"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DeepzoomError(Exception):
    """Base class for deepzoom failures."""


class UnknownNode(DeepzoomError):
    """A lookup named a node that isn't in the scene."""

    def __init__(self, node_id: str):
        super().__init__(f"no node {node_id!r} in this scene")
        self.node_id = node_id


# ---------------------------------------------------------------------------
# Zoom nodes and the scene
# ---------------------------------------------------------------------------


@dataclass
class ZoomNode:
    """One thing in the scene at every altitude.

    ``levels`` is an ordered list of ``(min_zoom, text)``: at zoom ``z``,
    the node shows the text of the deepest level whose threshold ``z``
    has reached. ``children`` appear only once the zoom passes
    ``expand_at`` — the node's insides are a closer look, not a given.
    """

    node_id: str
    levels: list[tuple[float, str]] = field(default_factory=list)
    children: list["ZoomNode"] = field(default_factory=list)
    expand_at: float = 1.0
    parent: Optional["ZoomNode"] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not self.levels:
            raise DeepzoomError(
                f"node {self.node_id!r} needs at least one detail level"
            )
        self.levels = sorted(self.levels, key=lambda pair: pair[0])
        for threshold, _ in self.levels:
            if threshold < 0:
                raise DeepzoomError("zoom thresholds cannot be negative")

    def add_level(self, min_zoom: float, text: str) -> "ZoomNode":
        if min_zoom < 0:
            raise DeepzoomError("zoom thresholds cannot be negative")
        self.levels.append((min_zoom, text))
        self.levels.sort(key=lambda pair: pair[0])
        return self

    def add_child(self, node: "ZoomNode") -> "ZoomNode":
        node.parent = self
        self.children.append(node)
        return node

    def detail_at(self, zoom: float) -> str:
        """The deepest text this zoom level has earned."""
        text = self.levels[0][1]
        for threshold, candidate in self.levels:
            if zoom >= threshold:
                text = candidate
            else:
                break
        return text

    def expanded_at(self, zoom: float) -> bool:
        return bool(self.children) and zoom >= self.expand_at

    def depth(self) -> int:
        d, node = 0, self.parent
        while node is not None:
            d += 1
            node = node.parent
        return d

    def walk(self) -> Iterator["ZoomNode"]:
        yield self
        for child in self.children:
            yield from child.walk()


class Scene:
    """A zoomable world with one root. Rendering is a pure function of
    (scene, zoom): same altitude, same picture, every time."""

    def __init__(self, name: str = "untitled"):
        self.name = name
        self.root = ZoomNode(node_id="root", levels=[(0.0, name)], expand_at=0.0)

    def add(
        self,
        node_id: str,
        levels: list[tuple[float, str]],
        parent_id: str = "root",
        expand_at: float = 1.0,
    ) -> ZoomNode:
        parent = self.node(parent_id)
        if any(n.node_id == node_id for n in self.root.walk()):
            raise DeepzoomError(f"node {node_id!r} is already in the scene")
        return parent.add_child(
            ZoomNode(node_id=node_id, levels=levels, expand_at=expand_at)
        )

    def node(self, node_id: str) -> ZoomNode:
        for candidate in self.root.walk():
            if candidate.node_id == node_id:
                return candidate
        raise UnknownNode(node_id)

    def render(self, zoom: float, max_lines: Optional[int] = None) -> str:
        """Draw the scene at altitude ``zoom`` as indented text.

        Nodes show the detail level the zoom has earned; a node's children
        appear only past its ``expand_at``. Zoom out and clusters collapse
        to glyphs; zoom in and the fine print arrives.
        """
        if zoom < 0:
            raise DeepzoomError("zoom cannot be negative")
        lines: list[str] = []
        self._render_node(self.root, zoom, lines)
        if max_lines is not None:
            lines = lines[:max_lines]
        return "\n".join(lines)

    def _render_node(self, node: ZoomNode, zoom: float, lines: list[str]) -> None:
        indent = "  " * node.depth()
        lines.append(f"{indent}{node.detail_at(zoom)}")
        if node.expanded_at(zoom):
            for child in node.children:
                self._render_node(child, zoom, lines)
        elif node.children:
            lines.append(f"{indent}  … ({len(node.children)} inside)")

    def zoom_to_fit(self, node_id: str) -> float:
        """The zoom at which a node's children first become visible —
        a small clerical courtesy for "take me closer"."""
        return self.node(node_id).expand_at


def demo_scene() -> Scene:
    """A year of LEVI's memory at four altitudes: decade glyph, year
    label, month summaries, day detail."""
    scene = Scene("memory")
    year = scene.add(
        "y2026",
        levels=[(0.0, "◈"), (0.5, "2026"), (2.0, "2026 — the year LEVI grew teeth")],
        expand_at=1.0,
    )
    year.add_child(
        ZoomNode(
            node_id="sep",
            levels=[(0.0, "▫"), (1.0, "September"), (3.0, "September — build season")],
            expand_at=3.0,
        )
    )
    sep = scene.node("sep")
    sep.add_child(
        ZoomNode(
            node_id="sep16",
            levels=[
                (0.0, "·"),
                (3.0, "Sep 16"),
                (5.0, "Sep 16 — hypermedia batch lands, 7 modules green"),
            ],
        )
    )
    return scene


__all__ = [
    "DeepzoomError",
    "UnknownNode",
    "ZoomNode",
    "Scene",
    "demo_scene",
]
