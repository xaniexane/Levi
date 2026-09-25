"""Cube — the Improv idea, LEVI-native.

Lotus Improv (1991-1996) was the cube spreadsheet: dimensions first,
formulas on named members instead of cell addresses, views as projections.
The grid giants won the rectangle war; the dimension-first model is the
load-bearing idea, rebuilt here stdlib-only, local-first.

LAWS (declared before implementation, enforced by tests):
  L1. Dimensions-first: facts are addressed by {dimension: member} tuples,
      never by positional addresses. There are no cells.
  L2. Named formulas: a formula is defined once on a fact name and broadcasts
      over every coordinate tuple; formulas reference other facts by name.
  L3. Views never mutate: slice/dice/project return new read-only views.
  L4. Honest absence: a missing fact reads as None, never as 0.
      Confusing absence with zero is the original spreadsheet sin.
  L5. stdlib only, JSON-round-trippable: save/load preserves equality.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple


class CubeError(ValueError):
    """Raised when a coordinate, dimension, or formula breaks a law."""


FormulaFn = Callable[["Cube", Dict[str, str]], Any]


class Cube:
    """A named multidimensional store with named broadcast formulas."""

    def __init__(self, name: str, dimensions: Mapping[str, Iterable[str]]) -> None:
        self.name = name
        self.dimensions: Dict[str, List[str]] = {
            dim: list(members) for dim, members in dimensions.items()
        }
        if not self.dimensions:
            raise CubeError("a cube needs at least one dimension")
        for dim, members in self.dimensions.items():
            if not members:
                raise CubeError(f"dimension {dim!r} needs at least one member")
            if len(set(members)) != len(members):
                raise CubeError(f"dimension {dim!r} has duplicate members")
        # fact name -> {coord tuple (dim-sorted) -> value}
        self._facts: Dict[str, Dict[Tuple[Tuple[str, str], ...], Any]] = {}
        self._formulas: Dict[str, FormulaFn] = {}
        self._formula_order: List[str] = []

    # -- coordinates -----------------------------------------------------
    def _key(self, coord: Mapping[str, str]) -> Tuple[Tuple[str, str], ...]:
        if set(coord) != set(self.dimensions):
            raise CubeError(
                f"coordinate must name every dimension {sorted(self.dimensions)}; "
                f"got {sorted(coord)}"
            )
        for dim, member in coord.items():
            if member not in self.dimensions[dim]:
                raise CubeError(f"{member!r} is not a member of dimension {dim!r}")
        return tuple(sorted(coord.items()))

    def _full_coords(self) -> Iterable[Dict[str, str]]:
        dims = list(self.dimensions)
        pools = [self.dimensions[d] for d in dims]

        def rec(i: int, acc: Dict[str, str]):
            if i == len(dims):
                yield dict(acc)
                return
            for m in pools[i]:
                acc[dims[i]] = m
                yield from rec(i + 1, acc)

        yield from rec(0, {})

    # -- facts ------------------------------------------------------------
    def set(self, fact: str, coord: Mapping[str, str], value: Any) -> None:
        """Store a raw value. L4: store None explicitly; never invent a value."""
        if fact in self._formulas:
            raise CubeError(f"{fact!r} is a formula; it cannot be set directly")
        self._facts.setdefault(fact, {})[self._key(coord)] = value

    def define_formula(self, name: str, fn: FormulaFn) -> None:
        """L2: one definition, broadcasts over every coordinate tuple."""
        if name in self._facts:
            raise CubeError(f"{name!r} already holds raw facts")
        if name in self._formulas:
            raise CubeError(f"formula {name!r} already defined")
        self._formulas[name] = fn
        if name not in self._formula_order:  # may exist as a load-stub
            self._formula_order.append(name)

    def get(self, fact: str, coord: Mapping[str, str]) -> Any:
        """L4: missing fact -> None. Never 0."""
        key = self._key(coord)
        if fact in self._formula_order:
            if fact not in self._formulas:
                raise CubeError(
                    f"formula {fact!r} was recorded but not re-registered "
                    "after load; call define_formula() first"
                )
            return self._formulas[fact](self, dict(coord))
        return self._facts.get(fact, {}).get(key)

    # -- views (L3: never mutate) -----------------------------------------
    def slice(self, fixed: Mapping[str, str]) -> Dict[str, Dict[Tuple, Any]]:
        """Fix some dimensions; return {fact: {remaining coord key: value}}."""
        for dim, member in fixed.items():
            if dim not in self.dimensions:
                raise CubeError(f"unknown dimension {dim!r}")
            if member not in self.dimensions[dim]:
                raise CubeError(f"{member!r} not in {dim!r}")
        out: Dict[str, Dict[Tuple, Any]] = {}
        facts = list(self._facts) + self._formula_order
        for fact in facts:
            rows: Dict[Tuple, Any] = {}
            for coord in self._full_coords():
                if all(coord[d] == m for d, m in fixed.items()):
                    rest = tuple((d, coord[d]) for d in sorted(coord) if d not in fixed)
                    rows[rest] = self.get(fact, coord)
            out[fact] = rows
        return out

    def dice(
        self, fact: str, where: Optional[Mapping[str, str]] = None
    ) -> List[Tuple[Dict[str, str], Any]]:
        """All (coord, value) pairs for a fact, optionally filtered."""
        where = where or {}
        rows = []
        for coord in self._full_coords():
            if all(coord[d] == m for d, m in where.items()):
                rows.append((coord, self.get(fact, coord)))
        return rows

    def aggregate(
        self, fact: str, over: str, fn: Callable[[List[Any]], Any] = sum
    ) -> Dict[str, Any]:
        """Collapse one dimension with an aggregation fn (None values skipped)."""
        if over not in self.dimensions:
            raise CubeError(f"unknown dimension {over!r}")
        out: Dict[str, Any] = {}
        for member in self.dimensions[over]:
            vals = [v for _, v in self.dice(fact, {over: member}) if v is not None]
            out[member] = fn(vals) if vals else None  # L4: empty set -> None, not 0
        return out

    # -- persistence (L5) --------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        facts = {
            fact: {",".join(f"{d}={m}" for d, m in key): v for key, v in rows.items()}
            for fact, rows in self._facts.items()
        }
        return {
            "name": self.name,
            "dimensions": self.dimensions,
            "facts": facts,
            "formulas": self._formula_order,  # names only; fns re-registered on load
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path: str) -> "Cube":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        cube = cls(data["name"], data["dimensions"])
        for fact, rows in data["facts"].items():
            for ckey, value in rows.items():
                coord = dict(pair.split("=", 1) for pair in ckey.split(","))
                cube.set(fact, coord, value)
        # L5: formula names round-trip as stubs; fns must be re-registered.
        cube._formula_order = list(data.get("formulas", []))
        return cube

    def fact_names(self) -> List[str]:
        return list(self._facts) + self._formula_order
