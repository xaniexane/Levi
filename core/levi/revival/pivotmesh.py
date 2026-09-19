"""LEVI's pivot mesh: the same knowledge, re-oriented by rotating the view.

Studied from: retired-software-revival-research-20260916-0004/report.md (§29).

The load-bearing mechanism of ZigZag: the **zzstructure** — cells connected
*both ways* along *arbitrarily many named dimensions* (each cell holds at
most one positive and one negative connection per dimension). The display
shows any two dimensions as a table, and **pivoting** rotates a hidden
dimension into view — no new search, just a re-orientation. ``pivotmesh``
is LEVI's remix: a ``Mesh`` of cells, a view with two visible dimensions,
``pivot(cell, dim)`` to rotate the view, and ``walk`` to travel a dimension
in either direction.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional


ORIGIN = "levi-revival/pivotmesh"


POS = "+"
NEG = "-"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PivotmeshError(Exception):
    """Base class for pivotmesh failures."""


class UnknownCell(PivotmeshError):
    """A connection or walk named a cell that isn't in the mesh."""

    def __init__(self, cell_id: str):
        super().__init__(f"no cell {cell_id!r} in this mesh")
        self.cell_id = cell_id


class DimensionClash(PivotmeshError):
    """A cell already holds a connection in that direction of that dimension."""


# ---------------------------------------------------------------------------
# Cells and the mesh
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    """One node in the mesh. ``links`` maps dimension -> {+/−: cell_id}."""

    cell_id: str
    label: str = ""
    payload: object = None
    links: dict[str, dict[str, str]] = field(default_factory=dict)

    def neighbor(self, dim: str, direction: str) -> Optional[str]:
        return self.links.get(dim, {}).get(direction)


class Mesh:
    """A zzstructure: cells joined both ways along named dimensions.

    Rule of the mesh: along one dimension, a cell has at most one "+"
    neighbor and at most one "−" neighbor — a zippered list, not a tangle.
    Dimensions may loop back on themselves; the mesh is not Euclidean and
    doesn't pretend to be.
    """

    def __init__(self):
        self.cells: dict[str, Cell] = {}

    # -- building -----------------------------------------------------------
    def add_cell(self, cell_id: str, label: str = "", payload: object = None) -> Cell:
        if not cell_id or not cell_id.strip():
            raise PivotmeshError("cell_id must be non-empty")
        if cell_id in self.cells:
            raise PivotmeshError(f"cell {cell_id!r} is already in the mesh")
        cell = Cell(cell_id=cell_id, label=label or cell_id, payload=payload)
        self.cells[cell_id] = cell
        return cell

    def cell(self, cell_id: str) -> Cell:
        if cell_id not in self.cells:
            raise UnknownCell(cell_id)
        return self.cells[cell_id]

    def connect(self, first: str, second: str, dim: str) -> None:
        """Join two cells along ``dim``: first is the "−" side of second,
        second is the "+" side of first. Both directions, one call."""
        a, b = self.cell(first), self.cell(second)
        if not dim or not dim.strip():
            raise PivotmeshError("dimension name must be non-empty")
        for cell, direction, other in ((a, POS, b), (b, NEG, a)):
            existing = cell.neighbor(dim, direction)
            if existing is not None and existing != other.cell_id:
                raise DimensionClash(
                    f"cell {cell.cell_id!r} already has a {direction} "
                    f"connection along {dim!r} (to {existing!r})"
                )
            cell.links.setdefault(dim, {})[direction] = other.cell_id

    def disconnect(self, cell_id: str, dim: str, direction: str) -> None:
        """Sever one directional link; the mirror side is severed too."""
        cell = self.cell(cell_id)
        other_id = cell.neighbor(dim, direction)
        if other_id is None:
            raise PivotmeshError(
                f"cell {cell_id!r} has no {direction} link along {dim!r}"
            )
        other = self.cell(other_id)
        mirror = NEG if direction == POS else POS
        del cell.links[dim][direction]
        if not cell.links[dim]:
            del cell.links[dim]
        if other.links.get(dim, {}).get(mirror) == cell_id:
            del other.links[dim][mirror]
            if not other.links[dim]:
                del other.links[dim]

    def dimensions(self) -> list[str]:
        dims: set[str] = set()
        for cell in self.cells.values():
            dims.update(cell.links)
        return sorted(dims)

    # -- traveling ------------------------------------------------------------
    def walk(
        self,
        start: str,
        dim: str,
        direction: str = POS,
        steps: Optional[int] = None,
    ) -> Iterator[Cell]:
        """Travel one dimension from a cell, one hop at a time. Loops are
        followed honestly — a dimension that circles back will circle back.
        ``steps`` caps the journey; without it, the walk stops at a dead end
        or when it returns to where it started."""
        if direction not in (POS, NEG):
            raise PivotmeshError('direction must be "+" or "-"')
        current = self.cell(start)
        seen = {current.cell_id}
        count = 0
        while True:
            nxt = current.neighbor(dim, direction)
            if nxt is None:
                return
            if nxt in seen and steps is None:
                return  # a loop would walk forever; stop at the return
            current = self.cell(nxt)
            seen.add(current.cell_id)
            yield current
            count += 1
            if steps is not None and count >= steps:
                return

    def row(self, cell_id: str, dim: str) -> list[Cell]:
        """The whole visible strip along a dimension through a cell:
        everything "−" of it, the cell itself, everything "+" of it."""
        cell = self.cell(cell_id)
        neg = list(self.walk(cell_id, dim, NEG))
        pos = list(self.walk(cell_id, dim, POS))
        return list(reversed(neg)) + [cell] + pos


# ---------------------------------------------------------------------------
# The view: two visible dimensions, pivot to rotate
# ---------------------------------------------------------------------------


class View:
    """What the eye sees: a cursor cell plus two visible dimensions —
    horizontal and vertical. ``pivot`` rotates a hidden dimension into
    view; the data never moves, only the orientation."""

    def __init__(self, mesh: Mesh, cursor: str, h_dim: str, v_dim: str):
        self.mesh = mesh
        self.cursor = mesh.cell(cursor).cell_id  # validates
        if h_dim == v_dim:
            raise PivotmeshError("the two visible dimensions must differ")
        self.h_dim = h_dim
        self.v_dim = v_dim

    def pivot(self, dim: str, axis: str = "h") -> "View":
        """Rotate ``dim`` into view on the chosen axis, pushing the old
        visible dimension back into the hidden set. The mesh doesn't
        change; the *question* changes."""
        if axis not in ("h", "v"):
            raise PivotmeshError('axis must be "h" or "v"')
        if dim not in (self.h_dim, self.v_dim) and dim not in self.mesh.dimensions():
            raise PivotmeshError(f"no dimension {dim!r} in this mesh")
        if dim == (self.v_dim if axis == "h" else self.h_dim):
            raise PivotmeshError(f"{dim!r} is already visible on the other axis")
        if axis == "h":
            return View(self.mesh, self.cursor, dim, self.v_dim)
        return View(self.mesh, self.cursor, self.h_dim, dim)

    def move_cursor(self, cell_id: str) -> None:
        self.cursor = self.mesh.cell(cell_id).cell_id

    def step(self, dim: str, direction: str = POS) -> Optional[Cell]:
        """Move the cursor one hop along a dimension, if there is one."""
        nxt = self.mesh.cell(self.cursor).neighbor(dim, direction)
        if nxt is None:
            return None
        self.cursor = nxt
        return self.mesh.cell(nxt)

    def render(self) -> str:
        """The visible table: the cursor's strip along each visible dimension."""
        mesh = self.mesh
        h_row = mesh.row(self.cursor, self.h_dim)
        v_col = mesh.row(self.cursor, self.v_dim)
        cursor_label = mesh.cell(self.cursor).label
        lines = [
            f"cursor: {cursor_label}",
            f"h [{self.h_dim}]: "
            + " — ".join(
                f"[{c.label}]" if c.cell_id == self.cursor else c.label for c in h_row
            ),
            f"v [{self.v_dim}]: "
            + " — ".join(
                f"[{c.label}]" if c.cell_id == self.cursor else c.label for c in v_col
            ),
        ]
        return "\n".join(lines)


def demo_mesh() -> tuple[Mesh, View]:
    """A tiny mesh worth pivoting: three notes along ``time``, ``topic``,
    and ``people`` dimensions."""
    mesh = Mesh()
    for cid, label in (
        ("n1", "visa form"),
        ("n2", "flight booked"),
        ("n3", "packing list"),
    ):
        mesh.add_cell(cid, label)
    # time runs n1 -> n2 -> n3
    mesh.connect("n1", "n2", "time")
    mesh.connect("n2", "n3", "time")
    # topic chains: n1 -> travel-docs -> n3, and n2 -> logistics
    mesh.add_cell("t-docs", "travel-docs")
    mesh.add_cell("t-log", "logistics")
    mesh.connect("n1", "t-docs", "topic")
    mesh.connect("t-docs", "n3", "topic")
    mesh.connect("n2", "t-log", "topic")
    # people chain: n1 -> sam -> jo -> n3 (zippered, one link per direction)
    mesh.add_cell("p-sam", "sam")
    mesh.add_cell("p-jo", "jo")
    mesh.connect("n1", "p-sam", "people")
    mesh.connect("p-sam", "p-jo", "people")
    mesh.connect("p-jo", "n3", "people")
    view = View(mesh, "n2", "time", "topic")
    return mesh, view


__all__ = [
    "POS",
    "NEG",
    "PivotmeshError",
    "UnknownCell",
    "DimensionClash",
    "Cell",
    "Mesh",
    "View",
    "demo_mesh",
]
