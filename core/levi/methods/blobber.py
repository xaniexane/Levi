"""Grid-based dungeon crawlers ("blobbers"): step, turn, map, endure.

Origin: Wizardry (1981), The Bard's Tale, Might and Magic, Dungeon Master —
first-person dungeons on a square grid, the whole party moving as one
unit, turn- or real-time combat.

What it is in LEVI: GridDelve — a tile grid with walls, a party token with
a position and a facing, step/turn movement (stepping into a wall or off
the map is denied, not absorbed), tile-based line of sight computed by
raycast, a persistent revealed map (mapping is the core skill), and an
attrition budget: every move burns a torch, every step eats a ration. When
the torches are gone the delve is dark and movement is refused.

Honesty label: LOAD-BEARING — discrete step/turn movement, Bresenham tile
line-of-sight, and per-move attrition are concrete mechanics.

Deny-closed inputs: ragged or empty grids, grids without exactly one
start, unknown tile characters, negative supplies, stepping into walls or
off the map, and any move with no torches left are all rejected with
ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GridDelve", "WALL", "FLOOR", "START", "FACINGS"]

WALL = "#"
FLOOR = "."
START = "S"
FACINGS = ("N", "E", "S", "W")

# (row, col) deltas: N up, E right, S down, W left.
_DELTAS = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}

_SIGHT_RADIUS = 6


def _parse_grid(grid: object) -> tuple[tuple[str, ...], tuple[int, int]]:
    if not isinstance(grid, (list, tuple)) or not grid:
        raise ValueError("grid must be a non-empty list of strings")
    rows: list[str] = []
    for row in grid:
        if not isinstance(row, str) or not row:
            raise ValueError("grid rows must be non-empty strings")
        rows.append(row)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("grid rows must all have the same length (no ragged maps)")
    starts: list[tuple[int, int]] = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == START:
                starts.append((r, c))
            elif ch not in (WALL, FLOOR):
                raise ValueError(f"unknown tile {ch!r} at ({r}, {c})")
    if len(starts) != 1:
        raise ValueError(
            f"grid must contain exactly one start tile {START!r}, found {len(starts)}"
        )
    return tuple(rows), starts[0]


def _ray(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Bresenham tiles from (x0, y0) to (x1, y1), inclusive of both ends."""
    tiles: list[tuple[int, int]] = []
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err = dx - dy
    x, y = x0, y0
    while True:
        tiles.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return tiles


@dataclass(frozen=True)
class Position:
    row: int
    col: int
    facing: str


class GridDelve:
    """One party, one grid: step, turn, see, and burn supplies doing it."""

    def __init__(self, grid: list[str], torches: int = 10, rations: int = 10):
        self._grid, start = _parse_grid(grid)
        for name, amount in (("torches", torches), ("rations", rations)):
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        self._torches = torches
        self._rations = rations
        self._pos = Position(row=start[0], col=start[1], facing="N")
        self._moves = 0
        self._mapped: set[tuple[int, int]] = set()
        self._reveal()  # the starting tile is always mapped

    # -- the map -----------------------------------------------------------
    @property
    def rows(self) -> int:
        return len(self._grid)

    @property
    def cols(self) -> int:
        return len(self._grid[0])

    def tile(self, row: int, col: int) -> str:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise ValueError(f"tile ({row}, {col}) is off the map")
        ch = self._grid[row][col]
        return FLOOR if ch == START else ch

    def is_wall(self, row: int, col: int) -> bool:
        return self.tile(row, col) == WALL

    # -- movement ----------------------------------------------------------
    def position(self) -> Position:
        return self._pos

    def _spend_torch(self) -> None:
        if self._torches <= 0:
            raise ValueError("no torches left — the delve is dark, no moving")
        self._torches -= 1

    def turn_left(self) -> Position:
        self._spend_torch()
        idx = FACINGS.index(self._pos.facing)
        self._pos = Position(self._pos.row, self._pos.col, FACINGS[(idx - 1) % 4])
        self._after_move()
        return self._pos

    def turn_right(self) -> Position:
        self._spend_torch()
        idx = FACINGS.index(self._pos.facing)
        self._pos = Position(self._pos.row, self._pos.col, FACINGS[(idx + 1) % 4])
        self._after_move()
        return self._pos

    def _step(self, forward: bool) -> Position:
        dr, dc = _DELTAS[self._pos.facing]
        if not forward:
            dr, dc = -dr, -dc
        nr, nc = self._pos.row + dr, self._pos.col + dc
        if not (0 <= nr < self.rows and 0 <= nc < self.cols):
            raise ValueError(f"bump: ({nr}, {nc}) is off the map")
        if self.is_wall(nr, nc):
            raise ValueError(f"bump: wall at ({nr}, {nc})")
        # Denied steps are side-effect free: only a real step burns supplies.
        if self._rations <= 0:
            raise ValueError("no rations left — the party cannot march")
        self._spend_torch()
        self._rations -= 1
        self._pos = Position(nr, nc, self._pos.facing)
        self._after_move()
        return self._pos

    def step_forward(self) -> Position:
        return self._step(forward=True)

    def step_backward(self) -> Position:
        return self._step(forward=False)

    def _after_move(self) -> None:
        self._moves += 1
        self._reveal()

    # -- line of sight and mapping ------------------------------------------
    def _los(self) -> set[tuple[int, int]]:
        """Tiles visible from the party now: raycast, walls block (but show)."""
        seen: set[tuple[int, int]] = set()
        r0, c0 = self._pos.row, self._pos.col
        for r in range(r0 - _SIGHT_RADIUS, r0 + _SIGHT_RADIUS + 1):
            for c in range(c0 - _SIGHT_RADIUS, c0 + _SIGHT_RADIUS + 1):
                if not (0 <= r < self.rows and 0 <= c < self.cols):
                    continue
                if (r - r0) ** 2 + (c - c0) ** 2 > _SIGHT_RADIUS**2:
                    continue
                for tr, tc in _ray(r0, c0, r, c):
                    if (tr, tc) != (r0, c0) and self.is_wall(tr, tc):
                        seen.add((tr, tc))  # the blocking wall itself is seen
                        break
                    seen.add((tr, tc))
        return seen

    def _reveal(self) -> None:
        self._mapped |= self._los()

    def visible(self) -> frozenset[tuple[int, int]]:
        """Tiles in line of sight right now."""
        return frozenset(self._los())

    def mapped(self) -> frozenset[tuple[int, int]]:
        """Every tile ever revealed: the map, the core skill."""
        return frozenset(self._mapped)

    def render_known(self) -> tuple[str, ...]:
        """The mapped region as text: walls '#', floors '.', unknown ' '."""
        out: list[str] = []
        for r in range(self.rows):
            row: list[str] = []
            for c in range(self.cols):
                if (r, c) not in self._mapped:
                    row.append(" ")
                elif (r, c) == (self._pos.row, self._pos.col):
                    row.append("@")
                else:
                    row.append(self.tile(r, c))
            out.append("".join(row))
        return tuple(out)

    # -- attrition -----------------------------------------------------------
    def supplies(self) -> dict[str, int]:
        return {"torches": self._torches, "rations": self._rations}

    def moves_made(self) -> int:
        return self._moves
