"""LEVI's category tiles — models by meaning, not by cell address.

Studied from: retired-software-revival-research-20260916-0004/report.md
[catalog #27] (Lotus Improv).

The studied capability shape: data, formulas, and presentation kept as
three *separate* layers; plain-English "category tiles" instead of cell
grids; natively multidimensional models addressed by *meaning* ("Region:
North", "Quarter: Q1") rather than coordinates ("B7"). This module is an
original, from-scratch expression of that shape: a ``CategoryModel`` of
named tiles. Each tile holds *data* (values keyed by named-category
coordinates), optionally a *formula* written in plain-English-ish
phrases ("sum Sales minus Costs"), and *presentation* is never stored —
``View`` objects compute readable renderings from the model on demand.

Honest limits, stated plainly: the formula language is a small,
heuristic phrase evaluator (sum / average / total of / plus / minus /
times / divided by, left-associative, no parentheses, numbers and tile
names). It is deliberately tiny — enough to show the separation of
layers — not a spreadsheet engine. Formula cycles raise instead of
hanging. Aggregation is summation over matching category coordinates.

Original, from-scratch implementation for LEVI. Local-first, stdlib
only, no network. Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/category-tiles"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TileError(Exception):
    """Base class for category-tile failures."""


class UnknownTile(TileError):
    """A formula or read named a tile that isn't in the model."""

    def __init__(self, name: str):
        super().__init__(f"no tile named {name!r}")
        self.name = name


class DuplicateTile(TileError):
    """A tile name was defined twice."""

    def __init__(self, name: str):
        super().__init__(f"tile {name!r} already exists")
        self.name = name


class FormulaError(TileError):
    """A formula could not be parsed, evaluated, or it cycles."""

    def __init__(self, message: str):
        super().__init__(message)


# ---------------------------------------------------------------------------
# Tiles
# ---------------------------------------------------------------------------


@dataclass
class Tile:
    """One category tile: named, multidimensional, optionally computed.

    ``data`` maps coordinate tuples of (category, value) pairs to
    numbers — e.g. ``(("Region", "North"), ("Quarter", "Q1")): 4200``.
    ``formula`` is plain-English-ish and evaluated against other tiles;
    ``categories`` names the dimensions this tile's data spans.
    """

    name: str
    formula: Optional[str] = None
    data: Dict[Tuple[Tuple[str, str], ...], float] = field(default_factory=dict)

    @property
    def dimensions(self) -> Set[str]:
        """The category names this tile's data is addressed by."""
        dims: Set[str] = set()
        for coord in self.data:
            for category, _value in coord:
                dims.add(category)
        return dims


# ---------------------------------------------------------------------------
# Formula language (small, heuristic, documented)
# ---------------------------------------------------------------------------
#
# Grammar (left-associative, no parentheses):
#   expr   := term (("plus" | "minus") term)*
#   term   := factor (("times" | "divided by") factor)*
#   factor := ("sum" | "total of" | "average") NAME | NAME | NUMBER
#
# A bare tile NAME evaluates to that tile's total (sum over its data).
# "sum X" / "total of X" are the same explicit spelling; "average X"
# divides by the cell count.

_AGGREGATORS = ("sum", "average")
_MULTIWORD = {"total of": "sum", "divided by": "/"}


def _tokenize(formula: str) -> List[str]:
    text = formula.strip().lower()
    for phrase, replacement in _MULTIWORD.items():
        text = text.replace(phrase, replacement)
    return text.split()


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


class _FormulaParser:
    """Recursive-descent over the tiny phrase grammar."""

    def __init__(self, tokens: List[str], model: "CategoryModel", seen: Set[str]):
        self.tokens = tokens
        self.pos = 0
        self.model = model
        self.seen = seen  # tiles already on the evaluation stack (cycle guard)

    def parse(self) -> float:
        value = self._expr()
        if self.pos != len(self.tokens):
            raise FormulaError(f"unexpected phrase {self.tokens[self.pos]!r}")
        return value

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _expr(self) -> float:
        value = self._term()
        while self._peek() in ("plus", "minus"):
            op = self.tokens[self.pos]
            self.pos += 1
            rhs = self._term()
            value = value + rhs if op == "plus" else value - rhs
        return value

    def _term(self) -> float:
        value = self._factor()
        while self._peek() in ("times", "/"):
            op = self.tokens[self.pos]
            self.pos += 1
            rhs = self._factor()
            if op == "/" and rhs == 0:
                raise FormulaError("division by zero")
            value = value * rhs if op == "times" else value / rhs
        return value

    def _factor(self) -> float:
        token = self._peek()
        if token is None:
            raise FormulaError("formula ended mid-phrase")
        if token in _AGGREGATORS:
            self.pos += 1
            name = self._tile_name()
            tile = self.model._get(name)
            return self.model._aggregate(tile, token, self.seen)
        if _is_number(token):
            self.pos += 1
            return float(token)
        name = self._tile_name()
        tile = self.model._get(name)
        return self.model._tile_value(tile, self.seen)

    def _tile_name(self) -> str:
        token = self._peek()
        if (
            token is None
            or _is_number(token)
            or token
            in (
                "plus",
                "minus",
                "times",
                "/",
                *_AGGREGATORS,
            )
        ):
            raise FormulaError(f"expected a tile name, found {token!r}")
        self.pos += 1
        # Tile names are case-insensitive here; resolve against the model.
        match = self.model._resolve_name(token)
        if match is None:
            raise UnknownTile(token)
        return match


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------


class CategoryModel:
    """Data, formulas, and presentation — three separate layers.

    Define tiles, record data against named categories, write formulas in
    plain-English-ish phrases, and render views. Reads never mutate;
    views never store.
    """

    def __init__(self) -> None:
        self._tiles: Dict[str, Tile] = {}

    # -- definition ------------------------------------------------------

    def define(self, name: str, formula: Optional[str] = None) -> Tile:
        """Define a tile; give it a formula to make it computed."""
        if name in self._tiles:
            raise DuplicateTile(name)
        tile = Tile(name, formula)
        self._tiles[name] = tile
        return tile

    def tiles(self) -> List[str]:
        """Every tile name, in definition order."""
        return list(self._tiles.keys())

    def _get(self, name: str) -> Tile:
        tile = self._tiles.get(name)
        if tile is None:
            raise UnknownTile(name)
        return tile

    def _resolve_name(self, token: str) -> Optional[str]:
        for name in self._tiles:
            if name.lower() == token:
                return name
        return None

    # -- data layer ------------------------------------------------------

    def record(self, name: str, value: float, **categories: str) -> None:
        """Record a datum addressed by meaning, not coordinates.

        ``record("Sales", 4200, Region="North", Quarter="Q1")`` — the
        coordinate is the *meaning* of the cell. Recording onto a
        formula tile is refused: computed tiles hold no raw data.
        """
        tile = self._get(name)
        if tile.formula is not None:
            raise TileError(f"tile {name!r} is computed; it holds no raw data")
        coord = tuple(sorted(categories.items()))
        tile.data[coord] = float(value)

    def dimensions(self, name: str) -> Set[str]:
        """The category dimensions a tile's data spans."""
        return self._get(name).dimensions

    def cells(
        self, name: str, **categories: str
    ) -> Dict[Tuple[Tuple[str, str], ...], float]:
        """Raw data cells matching all given category filters."""
        tile = self._get(name)
        wanted = tuple(sorted(categories.items()))
        return {
            coord: value
            for coord, value in tile.data.items()
            if all(pair in coord for pair in wanted)
        }

    # -- formula layer ---------------------------------------------------

    def value(self, name: str, **categories: str) -> float:
        """A tile's value: its formula evaluated, or its data summed.

        Category filters apply to raw-data tiles (sum over matching
        cells); formula tiles evaluate over their referenced tiles.
        """
        tile = self._get(name)
        if tile.formula is not None:
            if categories:
                raise TileError(
                    f"tile {name!r} is computed; category filters apply to data tiles"
                )
            return self._evaluate(tile.formula, {name})
        return sum(self.cells(name, **categories).values())

    def _tile_value(self, tile: Tile, seen: Set[str]) -> float:
        if tile.formula is not None:
            if tile.name in seen:
                raise FormulaError(f"formula cycle through {tile.name!r}")
            return self._evaluate(tile.formula, seen | {tile.name})
        return sum(tile.data.values())

    def _aggregate(self, tile: Tile, how: str, seen: Set[str]) -> float:
        values = (
            [self._tile_value(tile, seen)]
            if tile.formula is not None
            else list(tile.data.values())
        )
        if how == "average":
            if not values:
                raise FormulaError(f"cannot average empty tile {tile.name!r}")
            return sum(values) / len(values)
        return sum(values)

    def _evaluate(self, formula: str, seen: Set[str]) -> float:
        return _FormulaParser(_tokenize(formula), self, seen).parse()

    # -- presentation layer (computed, never stored) ---------------------

    def view(self, names: Optional[List[str]] = None) -> "View":
        """Build a presentation view over tiles; computes, doesn't store."""
        return View(self, names or self.tiles())


class View:
    """A computed presentation of tiles: data and formulas, side by side."""

    def __init__(self, model: CategoryModel, names: List[str]):
        self.model = model
        self.names = names

    def rows(self) -> List[Dict[str, object]]:
        """One row per tile: name, value, kind, formula, dimensions."""
        rows = []
        for name in self.names:
            tile = self.model._get(name)
            rows.append(
                {
                    "tile": name,
                    "value": self.model.value(name),
                    "kind": "computed" if tile.formula else "data",
                    "formula": tile.formula or "",
                    "dimensions": sorted(tile.dimensions),
                }
            )
        return rows

    def render(self) -> str:
        """The view as readable text: tiles by meaning, not by address."""
        lines = ["tiles — models by meaning, not by cell address:", ""]
        for row in self.rows():
            dims = ", ".join(row["dimensions"]) or "—"
            if row["kind"] == "computed":
                lines.append(f"  {row['tile']}: {row['value']:g}  (= {row['formula']})")
            else:
                lines.append(f"  {row['tile']}: {row['value']:g}  [dims: {dims}]")
        return "\n".join(lines)

    def summary(self) -> Dict[str, float]:
        """Tile name → value, for programmatic use."""
        return {row["tile"]: row["value"] for row in self.rows()}


__all__ = [
    "ORIGIN",
    "TileError",
    "UnknownTile",
    "DuplicateTile",
    "FormulaError",
    "Tile",
    "CategoryModel",
    "View",
]
