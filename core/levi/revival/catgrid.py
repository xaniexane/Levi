"""LEVI's meaning-first grid: categories, not cells.

Studied from: retired-software-revival-research-20260916-0004/report.md (§27).

The studied mechanism: a spreadsheet where the data model is built from
named *categories* — plain-English tiles like Sales, Region, Quarter —
instead of cell coordinates. Formulas reference categories by meaning
("Sales where Region is North"), never by address ("B7"); the model is
natively multidimensional; what you see is a *view* computed from the model,
with presentation kept strictly separate.

LEVI-native remix: ``CatGrid`` holds dimensions (named categories with
ordered members), facts keyed by full coordinate tuples (Sales × Region ×
Quarter is natural, not a pivot-table trick), and a small formula language
where ``SUM(Sales) WHERE Region = 'North' BY Quarter`` reads like the
thought itself. ``view()`` projects any slice into rows; ``render()`` turns
rows into text — the model never knows how it is displayed.

Honesty: LOAD-BEARING for small analytical models. The formula language is
deliberately tiny (SUM/AVG/COUNT/MIN/MAX, WHERE filters, one BY grouping);
everything lives in memory; there is no recalculation graph — formulas
evaluate on demand against current facts. Stdlib only, no network.
"""

import re
from itertools import product

ORIGIN = "levi-revival/catgrid"

_FORMULA_RE = re.compile(
    r"^\s*(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*([A-Za-z_][\w ]*?)\s*\)"
    r"\s*(?:WHERE\s+(.+?))?\s*(?:BY\s+([A-Za-z_][\w ]*?))?\s*$",
    re.IGNORECASE,
)
_COND_RE = re.compile(
    r"^\s*([A-Za-z_][\w ]*?)\s*(=|!=|>=|<=|>|<)\s*('[^']*'|\"[^\"]*\"|\S+)\s*$"
)


def _coerce(value):
    if isinstance(value, str):
        v = value.strip().strip("'\"")
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v
    return value


class CatGrid:
    """A multidimensional model addressed by meaning, not coordinates."""

    def __init__(self):
        self.dimensions = {}  # name -> [members] (ordered, plain English)
        self.facts = {}  # frozenset((dim, member)) -> {measure: value}
        self.formulas = {}  # name -> formula source string

    # -- categories ---------------------------------------------------------
    def add_dimension(self, name, members):
        """Name a category and give it its members, e.g. Region: North/South."""
        members = list(members)
        if not members:
            raise ValueError(f"dimension {name!r} needs at least one member")
        self.dimensions[name] = members
        return members

    def _key(self, coord):
        key = []
        for dim, member in coord.items():
            if dim not in self.dimensions:
                raise KeyError(f"unknown dimension {dim!r}")
            if member not in self.dimensions[dim]:
                raise KeyError(f"{member!r} is not a member of {dim!r}")
            key.append((dim, member))
        return frozenset(key)

    # -- facts --------------------------------------------------------------
    def set(self, coord, measure, value):
        """Record a fact at a full coordinate, e.g. {Region: North, Quarter: Q1}."""
        self.facts.setdefault(self._key(coord), {})[measure] = value

    def get(self, coord, measure, default=None):
        return self.facts.get(self._key(coord), {}).get(measure, default)

    # -- formulas: meaning, not coordinates ---------------------------------
    def define(self, name, formula):
        """Name a formula, e.g. SUM(Sales) WHERE Region = 'North' BY Quarter."""
        if not _FORMULA_RE.match(formula):
            raise ValueError(f"cannot parse formula: {formula!r}")
        self.formulas[name] = formula
        return name

    def _parse_conditions(self, clause):
        conds = []
        if not clause:
            return conds
        for part in re.split(r"\s+AND\s+", clause, flags=re.IGNORECASE):
            m = _COND_RE.match(part)
            if not m:
                raise ValueError(f"cannot parse condition: {part!r}")
            dim, op, raw = m.groups()
            dim = dim.strip()
            if dim not in self.dimensions:
                raise KeyError(f"unknown dimension {dim!r}")
            conds.append((dim, op, _coerce(raw)))
        return conds

    def _cell_matches(self, cell_key, conds):
        cell = dict(cell_key)
        for dim, op, want in conds:
            if dim not in cell:
                return False
            got = cell[dim]
            if op == "=" and not got == want:
                return False
            if op == "!=" and not got != want:
                return False
            if op == ">" and not got > want:
                return False
            if op == "<" and not got < want:
                return False
            if op == ">=" and not got >= want:
                return False
            if op == "<=" and not got <= want:
                return False
        return True

    def evaluate(self, name):
        """Evaluate a named formula against current facts.

        Returns a scalar, or a ``{member: value}`` dict when BY groups it.
        """
        m = _FORMULA_RE.match(self.formulas[name])
        func, measure, where_clause, by_dim = (
            m.group(1).upper(),
            m.group(2).strip(),
            m.group(3),
            m.group(4),
        )
        if by_dim:
            by_dim = by_dim.strip()
            if by_dim not in self.dimensions:
                raise KeyError(f"unknown dimension {by_dim!r}")
        conds = self._parse_conditions(where_clause)
        values = [
            cell[measure]
            for key, cell in self.facts.items()
            if measure in cell and self._cell_matches(key, conds)
        ]
        if by_dim:
            grouped = {}
            for member in self.dimensions[by_dim]:
                sub = [
                    cell[measure]
                    for key, cell in self.facts.items()
                    if measure in cell
                    and self._cell_matches(key, conds + [(by_dim, "=", member)])
                ]
                grouped[member] = self._aggregate(func, sub)
            return grouped
        return self._aggregate(func, values)

    @staticmethod
    def _aggregate(func, values):
        if func == "COUNT":
            return len(values)
        if not values:
            return None
        if func == "SUM":
            return sum(values)
        if func == "AVG":
            return sum(values) / len(values)
        if func == "MIN":
            return min(values)
        if func == "MAX":
            return max(values)
        raise ValueError(func)  # unreachable: parser gates the function set

    # -- views: presentation separated from the model -----------------------
    def view(self, *dims, measures=()):
        """Project a slice of the model into plain rows (presentation-free)."""
        for dim in dims:
            if dim not in self.dimensions:
                raise KeyError(f"unknown dimension {dim!r}")
        rows = []
        for combo in product(*(self.dimensions[d] for d in dims)):
            coord = dict(zip(dims, combo, strict=True))
            row = dict(zip(dims, combo, strict=True))
            for measure in measures:
                row[measure] = self.get(coord, measure)
            rows.append(row)
        return rows

    @staticmethod
    def render(rows):
        """Render view rows as a plain-text table. The model never sees this."""
        if not rows:
            return "(empty)"
        cols = list(rows[0].keys())
        widths = {
            c: max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in cols
        }
        head = " | ".join(str(c).ljust(widths[c]) for c in cols)
        bar = "-+-".join("-" * widths[c] for c in cols)
        body = [
            " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols) for r in rows
        ]
        return "\n".join([head, bar] + body)
