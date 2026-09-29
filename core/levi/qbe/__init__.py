"""qbe — Query By Example for LEVI's local stores.

Clean-room LEVI-native revival of Moshé Zloof's Query By Example
(IBM Research, 1975-77; perpetual-hunt daily 2026-09-27, record
``arch-method-qbe-query-by-example``): ask by *showing* an example row
instead of writing a query. This is NOT a database product clone — it is a
small example-row matcher over in-memory tables / JSONL records, built from
the 1977 paper's published semantics.

Cell language (a cell is a Python value; strings carry the syntax):

    "value"    literal — equality match
    "_x"       variable — unifies; the same name must hold equal values
               everywhere it appears (this is how tables join)
    "P."       print this column's matched value
    "P._x"     print + bind variable ``_x``
    ">700"     comparison — one of > < >= <= != = against a number or a
               'quoted' string
    "arch-*"   glob wildcard (fnmatch) on the string form of the value

Semantics (Zloof's, simplified honestly):
  * cells inside one example row are ANDed (L2);
  * example rows inside one skeleton are ORed (union);
  * skeletons join on shared variables — natural join (L1);
  * an empty match is honest: ``[]``, never an exception, never a guess (L3);
  * the result holds exactly the ``P.``-marked columns, in first-seen order,
    duplicates removed by default (L4).

LAWS (declared first, proved by tests/test_qbe.py):
  L1 variables unify — a variable bound in one cell constrains every other
     cell with the same name, across rows and tables.
  L2 rows are conjunctive — every cell of an example row must match.
  L3 emptiness is honest — no matching rows yields ``[]``.
  L4 projection is exact — results contain only P.-marked columns.

Public API:
    query(tables, skeletons, dedup=True) -> list[dict]
    load_jsonl(path) -> list[dict]
    example() -> dict  (a worked sailors/boats example)

CLI: ``python -m levi.qbe records.jsonl query.json`` — query.json holds
``{"skeletons": [...]}`` over the table named ``"records"`` (or
``{"tables": {...}, "skeletons": [...]}``).
"""

from __future__ import annotations

import fnmatch
from typing import Any, Dict, List, Tuple

__all__ = [
    "query",
    "load_jsonl",
    "example",
    "QueryError",
]

_MISSING = object()


class QueryError(ValueError):
    """A malformed skeleton (not a failed match — failures return [])."""


# ---------------------------------------------------------------------------
# cell parsing
# ---------------------------------------------------------------------------

_COND_OPS = (">=", "<=", "!=", ">", "<", "=")


def _is_var(token: str) -> bool:
    return (
        isinstance(token, str)
        and token.startswith("_")
        and len(token) > 1
        and token[1:].replace("_", "").isalnum()
    )


def _parse_cell(cell: Any) -> Tuple:
    """Parse a cell into a spec tuple. Raises QueryError on bad syntax."""
    if isinstance(cell, str) and cell.startswith("P."):
        rest = cell[2:]
        if rest == "":
            return ("print", ("any",))
        sub = _parse_cell(rest)
        if sub[0] in ("lit", "var", "cond", "glob"):
            return ("print", sub)
        raise QueryError("bad print cell %r: use P., P._var, P.>n, P.glob*" % cell)
    if isinstance(cell, str) and _is_var(cell):
        return ("var", cell)
    if isinstance(cell, str):
        for op in _COND_OPS:
            if cell.startswith(op) and len(cell) > len(op):
                rhs = cell[len(op):]
                return ("cond", op, _coerce(rhs))
        if "*" in cell or "?" in cell:
            return ("glob", cell)
    return ("lit", cell)


def _coerce(token: str) -> Any:
    """Turn a condition right-hand side into a number, quoted string, or str."""
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] == "'":
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _equals(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return a == b


def _compare(op: str, value: Any, rhs: Any) -> bool:
    if isinstance(rhs, (int, float)) and not isinstance(value, bool):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
    if op == ">":
        return value > rhs
    if op == "<":
        return value < rhs
    if op == ">=":
        return value >= rhs
    if op == "<=":
        return value <= rhs
    if op == "!=":
        return not _equals(value, rhs)
    if op == "=":
        return _equals(value, rhs)
    raise QueryError("unknown operator %r" % op)  # pragma: no cover


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

# (column, value) pairs collected for printing
_Print = Tuple[str, Any]


def _eval_spec(value: Any, spec: Tuple, binding: Dict[str, Any]) -> bool:
    """Evaluate a non-print spec against a value. Binds variables in place."""
    kind = spec[0]
    if kind == "any":
        return True
    if kind == "lit":
        return _equals(value, spec[1])
    if kind == "var":
        name = spec[1]
        if name in binding:
            return _equals(binding[name], value)
        binding[name] = value
        return True
    if kind == "cond":
        return _compare(spec[1], value, spec[2])
    if kind == "glob":
        return fnmatch.fnmatch(str(value), spec[1])
    raise QueryError("cannot nest P. inside P.: %r" % (spec,))


def _match_row(trow: Dict[str, Any], erow: Dict[str, Any],
               binding: Dict[str, Any]) -> Tuple[bool, List[_Print]]:
    """Match one example row against one table row. L2: every cell must match."""
    prints: List[_Print] = []
    for col, cell in erow.items():
        spec = _parse_cell(cell)
        value = trow.get(col, _MISSING)
        if value is _MISSING:
            return False, []
        if spec[0] == "print":
            if not _eval_spec(value, spec[1], binding):
                return False, []
            prints.append((col, value))
        elif not _eval_spec(value, spec, binding):
            return False, []
    return True, prints


def query(tables: Dict[str, List[Dict[str, Any]]],
          skeletons: List[Dict[str, Any]],
          dedup: bool = True) -> List[Dict[str, Any]]:
    """Run example skeletons over tables. Returns projected rows.

    ``skeletons``: [{"table": name, "rows": [{col: cell, ...}, ...]}, ...]
    Rows inside one skeleton are ORed; skeletons join on shared variables.
    """
    if not isinstance(skeletons, list):
        raise QueryError("skeletons must be a list")
    for sk in skeletons:
        if not isinstance(sk, dict) or "table" not in sk or "rows" not in sk:
            raise QueryError("bad skeleton %r: need {table, rows}" % (sk,))
        if sk["table"] not in tables:
            raise QueryError("unknown table %r" % (sk["table"],))

    results: List[Dict[str, Any]] = []

    def rec(idx: int, binding: Dict[str, Any], printed: List[_Print]) -> None:
        if idx == len(skeletons):
            row: Dict[str, Any] = {}
            for col, value in printed:
                if col not in row:  # first print wins; same column, same key
                    row[col] = value
            results.append(row)
            return
        sk = skeletons[idx]
        for trow in tables[sk["table"]]:
            for erow in sk["rows"]:
                b2 = dict(binding)
                ok, pv = _match_row(trow, erow, b2)
                if ok:
                    rec(idx + 1, b2, printed + pv)

    rec(0, {}, [])
    if dedup:
        seen = set()
        uniq: List[Dict[str, Any]] = []
        for row in results:
            key = tuple(sorted((k, _hashable(v)) for k, v in row.items()))
            if key not in seen:
                seen.add(key)
                uniq.append(row)
        return uniq
    return results


def _hashable(value: Any) -> Any:
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a table (one dict per line)."""
    import json

    rows = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def example() -> Dict[str, Any]:
    """The classic sailors/boats join, as data + skeletons."""
    sailors = [
        {"sid": 22, "sname": "Dustin", "rating": 7, "age": 45},
        {"sid": 29, "sname": "Brutus", "rating": 9, "age": 33},
        {"sid": 31, "sname": "Lubber", "rating": 8, "age": 55},
    ]
    reserves = [
        {"sid": 22, "bid": 101, "day": "2026-09-01"},
        {"sid": 29, "bid": 102, "day": "2026-09-02"},
        {"sid": 29, "bid": 103, "day": "2026-09-03"},
    ]
    boats = [
        {"bid": 101, "bname": "Interlake", "color": "blue"},
        {"bid": 102, "bname": "Clipper", "color": "red"},
        {"bid": 103, "bname": "Marine", "color": "red"},
    ]
    # Names and colors of red boats reserved by sailors rated over 7.
    skeletons = [
        {"table": "sailors",
         "rows": [{"sid": "_s", "sname": "P._n", "rating": ">7"}]},
        {"table": "reserves",
         "rows": [{"sid": "_s", "bid": "_b"}]},
        {"table": "boats",
         "rows": [{"bid": "_b", "color": "red", "bname": "P._c"}]},
    ]
    return {
        "tables": {"sailors": sailors, "reserves": reserves, "boats": boats},
        "skeletons": skeletons,
    }
