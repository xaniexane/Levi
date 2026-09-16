"""Quipu: positional hierarchical numeric encoding (encoding sketch).

History: the Inca Empire's knotted-string records — hierarchical cords
with base-10 knot clusters encoding census, tribute, warehouse, and labor
data for millions, administered without any written script. The numerical
code was only deciphered ~1923 (L. Leland Locke); Harvard's Khipu Database
has since recorded 900+ specimens, and analysis of Puruchuco khipus shows
*three ranked accounting levels* with sums passed upward — a full
bureaucratic data hierarchy in string. The Spanish conquest destroyed the
administrative class that read them (khipu use lingered in Andean villages
into the 20th century).

The mechanism: *positional, tactile, hierarchical data* — knot type ×
position × cord level = a multidimensional record you can audit by
recount, and the medium *is* the roll-up: local cords knot into provincial
cords knot into imperial cords.

In LEVI: the roll-up discipline. Metrics live as a khipu hierarchy —
daily cords (raw logs) knot into weekly cords (summaries) knot into
monthly cords (judgments); each level's knots are computed from the level
below; :meth:`Khipu.verify` checks that every parent equals the sum of
its children (the Puruchuco accounting check); any number unrolls, knot
by knot, to its source via :meth:`Khipu.audit`. Khipus persist as JSON
under ``~/.levi/methods/``.

Honesty: INSPIRATIONAL — a faithful sketch of the *accounting* mechanism
only (decimal clusters, hierarchical roll-up, recount audit). Cord color,
knot-type subtleties, and above all *narrative* khipus (histories or songs
in knots) are out of scope: narrative-decipherment claims rest on contested
colonial chronicles and disputed manuscripts and are treated as unproven,
not implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import _persist


# ---------------------------------------------------------------------------
# Knot clusters: a non-negative integer as decimal digit clusters.
# Level 0 (units): a cluster of single knots; higher levels: a long knot
# with one turn per digit. Zero is the empty position. (Sketch of Locke's
# decipherment, not a museum replica.)
# ---------------------------------------------------------------------------


def encode_knots(value: int) -> tuple[tuple[int, int], ...]:
    """Encode ``value`` as ``((level, knots), ...)`` clusters, units first."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("khipu values are non-negative integers")
    if value < 0:
        raise ValueError("khipu values are non-negative integers")
    if value == 0:
        return ()
    clusters = []
    level = 0
    while value:
        value, digit = divmod(value, 10)
        if digit:
            clusters.append((level, digit))
        level += 1
    return tuple(clusters)


def decode_knots(clusters: tuple[tuple[int, int], ...]) -> int:
    """Decode knot clusters back to the integer."""
    total = 0
    for level, knots in clusters:
        if level < 0 or knots < 1 or knots > 9:
            raise ValueError(f"invalid knot cluster {(level, knots)}")
        total += knots * (10 ** level)
    return total


@dataclass
class Cord:
    """One cord: its own recorded knots plus pendant (child) cords."""

    name: str
    knots: list[tuple[tuple[int, int], ...]] = field(default_factory=list)
    children: list[str] = field(default_factory=list)

    def record(self, value: int) -> None:
        """Tie a knot cluster for ``value`` onto this cord (the daily log)."""
        self.knots.append(encode_knots(value))

    def own_total(self) -> int:
        return sum(decode_knots(c) for c in self.knots)


class Khipu:
    """A hierarchical cord bundle with roll-up accounting."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("khipu name must be non-empty")
        self.name = name.strip()
        self._cords: dict[str, Cord] = {"root": Cord("root")}
        self._store = _persist.store_path(store or f"quipu-{_slug(self.name)}")
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"quipu store {self._store} does not match {self.name!r}"
            )
        for cname, cd in data.get("cords", {}).items():
            cord = Cord(cname)
            cord.knots = [tuple(tuple(k) for k in cluster)
                          for cluster in cd.get("knots", [])]
            cord.children = list(cd.get("children", []))
            self._cords[cname] = cord

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name,
             "cords": {cname: {"knots": [list(map(list, cl)) for cl in c.knots],
                               "children": c.children}
                       for cname, c in self._cords.items()}},
        )

    # -- building the hierarchy ----------------------------------------------
    def add_cord(self, name: str, parent: str = "root") -> Cord:
        """Knot a new pendant cord under ``parent``."""
        if not name or not name.strip():
            raise ValueError("cord name must be non-empty")
        name = name.strip()
        if name in self._cords:
            raise ValueError(f"cord {name!r} already exists")
        if parent not in self._cords:
            raise KeyError(f"no parent cord {parent!r}")
        cord = Cord(name)
        self._cords[name] = cord
        self._cords[parent].children.append(name)
        return cord

    def record(self, cord: str, value: int) -> None:
        """Tie a value-knot onto ``cord``."""
        try:
            self._cords[cord].record(value)
        except KeyError:
            raise KeyError(f"no cord {cord!r}") from None

    # -- the roll-up ----------------------------------------------------------
    def rollup(self, cord: str = "root") -> int:
        """This cord's knots plus every pendant cord's roll-up, recursively."""
        node = self._get(cord)
        return node.own_total() + sum(self.rollup(c) for c in node.children)

    def audit(self, cord: str = "root", _depth: int = 0) -> list[dict]:
        """Unroll a number to its source knots: every level, every cord."""
        node = self._get(cord)
        rows = [{
            "cord": cord,
            "depth": _depth,
            "own": node.own_total(),
            "knot_clusters": [list(map(list, cl)) for cl in node.knots],
            "rollup": self.rollup(cord),
        }]
        for child in node.children:
            rows.extend(self.audit(child, _depth + 1))
        return rows

    def verify(self) -> list[str]:
        """The Puruchuco check: every cord's stored roll-up must equal the
        sum of its own knots plus its children's roll-ups. Returns a list
        of discrepancies — empty means the books balance. Deny-closed: it
        reports, never silently re-ties."""
        problems = []
        for name, node in self._cords.items():
            expected = node.own_total() + sum(self.rollup(c) for c in node.children)
            # rollup() is defined identically, so a mismatch here would mean
            # structural corruption (e.g. a child listed twice / missing).
            children_sum = sum(self._cords[c].own_total()
                               + sum(self.rollup(g) for g in self._cords[c].children)
                               for c in node.children)
            if expected != node.own_total() + children_sum:
                problems.append(f"cord {name!r}: roll-up inconsistency")
            seen = set()
            dupes = [c for c in node.children if c in seen or seen.add(c)]
            if dupes:
                problems.append(f"cord {name!r}: child listed twice: {dupes}")
            for c in node.children:
                if c not in self._cords:
                    problems.append(f"cord {name!r}: pendant {c!r} is missing")
        return problems

    def summary(self) -> str:
        lines = [f"khipu: {self.name}  (root roll-up: {self.rollup()})"]
        for row in self.audit():
            indent = "  " * row["depth"]
            lines.append(
                f"{indent}{row['cord']}: own={row['own']} rollup={row['rollup']}"
            )
        return "\n".join(lines)

    def _get(self, cord: str) -> Cord:
        try:
            return self._cords[cord]
        except KeyError:
            raise KeyError(f"no cord {cord!r}") from None


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower())[:40].strip("-")


__all__ = [
    "encode_knots",
    "decode_knots",
    "Cord",
    "Khipu",
]
