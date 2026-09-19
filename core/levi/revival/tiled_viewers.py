"""Tiled viewers instead of overlapping windows.

Studied from: interfaces-hunt-20260915/report.md [2. The Oberon System]

Functional description: no overlapping windows, no applications, no modes —
the whole interface is one persistent text space, recursively split into
tiles. Each tile holds an editable text buffer; splits are vertical or
horizontal with proportional sizes; closing a tile merges its space back
into a sibling; focus moves between tiles by direction. Rendering draws the
whole space as ASCII so the tiling logic is inspectable and testable
without a display server.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/tiled-viewers"


@dataclass
class TextBuffer:
    """An editable text buffer living inside one tile."""

    name: str
    lines: List[str] = field(default_factory=list)

    def insert(self, line_no: int, text: str) -> None:
        line_no = max(0, min(line_no, len(self.lines)))
        self.lines.insert(line_no, text)

    def append(self, text: str) -> None:
        self.lines.append(text)

    def delete(self, line_no: int) -> str:
        return self.lines.pop(line_no)

    def replace(self, line_no: int, text: str) -> None:
        self.lines[line_no] = text

    def text(self) -> str:
        return "\n".join(self.lines)


class _Tile:
    """One node in the recursive tiling tree (leaf holds a buffer)."""

    _counter = 0

    def __init__(self, buffer: Optional[TextBuffer] = None) -> None:
        _Tile._counter += 1
        self.id = _Tile._counter
        self.buffer = buffer
        self.direction: Optional[str] = None  # "v" | "h" for split nodes
        self.ratio: float = 0.5
        self.children: List["_Tile"] = []

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def leaves(self) -> List["_Tile"]:
        if self.is_leaf:
            return [self]
        out: List["_Tile"] = []
        for child in self.children:
            out.extend(child.leaves())
        return out

    def find(self, tile_id: int) -> Optional["_Tile"]:
        if self.id == tile_id:
            return self
        for child in self.children:
            found = child.find(tile_id)
            if found:
                return found
        return None

    def parent_of(self, tile_id: int) -> Optional["_Tile"]:
        for child in self.children:
            if child.id == tile_id:
                return self
            found = child.parent_of(tile_id)
            if found:
                return found
        return None


class TileSpace:
    """The whole interface: one space, tiled, every tile an editable text."""

    def __init__(self, width: int = 80, height: int = 24) -> None:
        if width < 10 or height < 4:
            raise ValueError("space must be at least 10x4")
        self.width = width
        self.height = height
        self.root = _Tile(TextBuffer("scratch"))
        self.focused: int = self.root.id

    # -- tiling ------------------------------------------------------------
    def split(
        self,
        tile_id: int,
        direction: str,
        ratio: float = 0.5,
        name: str = "scratch",
    ) -> Tuple[int, int]:
        """Split a leaf tile; returns (original_tile_id, new_tile_id)."""
        if direction not in ("v", "h"):
            raise ValueError("direction must be 'v' or 'h'")
        if not 0.1 <= ratio <= 0.9:
            raise ValueError("ratio must be within [0.1, 0.9]")
        tile = self.root.find(tile_id)
        if tile is None or not tile.is_leaf:
            raise ValueError(f"cannot split tile {tile_id}")
        old_buffer = tile.buffer
        tile.buffer = None
        tile.direction = direction
        tile.ratio = ratio
        first = _Tile(old_buffer)
        second = _Tile(TextBuffer(name))
        tile.children = [first, second]
        return first.id, second.id

    def close(self, tile_id: int) -> bool:
        """Close a leaf tile; its sibling absorbs the space."""
        tile = self.root.find(tile_id)
        if tile is None or not tile.is_leaf:
            return False
        parent = self.root.parent_of(tile_id)
        if parent is None:
            return False  # cannot close the last tile
        sibling = next(c for c in parent.children if c.id != tile_id)
        parent.buffer = sibling.buffer
        parent.direction = None
        parent.children = []
        if self.focused == tile_id:
            self.focused = parent.id
        return True

    def focus(self, tile_id: int) -> None:
        tile = self.root.find(tile_id)
        if tile is None or not tile.is_leaf:
            raise ValueError(f"unknown leaf tile: {tile_id}")
        self.focused = tile_id

    def focus_dir(self, direction: str) -> bool:
        """Move focus to the nearest tile in a compass direction.

        Implemented on rendered geometry: pick the leaf whose cell center is
        closest in the given direction from the focused tile's center.
        """
        cells = {tid: (x, y, w, h) for tid, x, y, w, h in self._layout()}
        if self.focused not in cells:
            return False
        fx, fy, fw, fh = cells[self.focused]
        cx, cy = fx + fw / 2, fy + fh / 2
        best: Optional[int] = None
        best_score = float("inf")
        for tid, (x, y, w, h) in cells.items():
            if tid == self.focused:
                continue
            ox, oy = x + w / 2, y + h / 2
            dx, dy = ox - cx, oy - cy
            if direction == "left" and dx >= 0:
                continue
            if direction == "right" and dx <= 0:
                continue
            if direction == "up" and dy >= 0:
                continue
            if direction == "down" and dy <= 0:
                continue
            score = abs(dx) + abs(dy)
            if score < best_score:
                best_score = score
                best = tid
        if best is None:
            return False
        self.focused = best
        return True

    # -- editing -----------------------------------------------------------
    def buffer(self, tile_id: Optional[int] = None) -> TextBuffer:
        tile = self.root.find(tile_id if tile_id is not None else self.focused)
        if tile is None or tile.buffer is None:
            raise ValueError("no editable buffer at that tile")
        return tile.buffer

    def type(self, text: str, tile_id: Optional[int] = None) -> None:
        """Append lines of text to a tile's buffer (the persistent space)."""
        buf = self.buffer(tile_id)
        for line in text.splitlines() or [""]:
            buf.append(line)

    # -- rendering ---------------------------------------------------------
    def _layout(self) -> List[Tuple[int, int, int, int, int]]:
        """(tile_id, x, y, w, h) for every leaf tile."""

        out: List[Tuple[int, int, int, int, int]] = []

        def walk(tile: _Tile, x: int, y: int, w: int, h: int) -> None:
            if tile.is_leaf:
                out.append((tile.id, x, y, w, h))
                return
            a, b = tile.children
            if tile.direction == "v":
                w1 = max(2, int(w * tile.ratio))
                walk(a, x, y, w1, h)
                walk(b, x + w1 + 1, y, w - w1 - 1, h)
            else:
                h1 = max(1, int(h * tile.ratio))
                walk(a, x, y, w, h1)
                walk(b, x, y + h1 + 1, w, h - h1 - 1)

        walk(self.root, 0, 0, self.width, self.height)
        return out

    def render(self) -> str:
        """Draw the whole space as ASCII: tiles, names, focus, text."""
        canvas = [[" "] * self.width for _ in range(self.height)]
        for tid, x, y, w, h in self._layout():
            tile = self.root.find(tid)
            assert tile is not None and tile.buffer is not None
            focused = tid == self.focused
            edge = "=" if focused else "-"
            for i in range(w):
                canvas[y][i + x] = edge
                canvas[y + h - 1][i + x] = edge
            for j in range(h):
                canvas[j + y][x] = edge
                canvas[j + y][x + w - 1] = edge
            label = f" {tile.buffer.name}{'*' if focused else ''} "
            for i, ch in enumerate(label[: w - 2]):
                canvas[y][x + 1 + i] = ch
            for j, line in enumerate(tile.buffer.lines[: h - 2]):
                for i, ch in enumerate(line[: w - 2]):
                    canvas[y + 1 + j][x + 1 + i] = ch
        return "\n".join("".join(row) for row in canvas)

    def tiles(self) -> List[Dict[str, object]]:
        return [
            {"id": tid, "x": x, "y": y, "w": w, "h": h, "focused": tid == self.focused}
            for tid, x, y, w, h in self._layout()
        ]


def demo_tiles() -> Dict[str, object]:
    space = TileSpace(width=60, height=16)
    space.type("morning notes")
    left, right = space.split(space.root.id, "v", name="tasks")
    space.type("buy milk\nship wave 33", tile_id=right)
    top, bottom = space.split(right, "h", name="log")
    space.type("tile closed demo", tile_id=bottom)
    space.focus(top)
    return {
        "render": space.render(),
        "tile_count": len(space.tiles()),
        "focused": space.focused,
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_tiles(), indent=2))
