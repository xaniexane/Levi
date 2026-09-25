"""LEVI's multivalued record store: attributes that genuinely hold N values.

Studied from: revival-50-more-20260916-0009/report-part2.md (§42).

The studied mechanism refuses first normal form on purpose: an attribute
is not a single slot but a *list that means it* — a contact's ``phone``
holds three numbers because the contact has three numbers, not because a
join table says so. Queries are English-like (``LIST contacts WITH phone
CONTAINING 555``), and the dictionaries — the schema — are stored as data,
in the same store, queryable like everything else.

LEVI-native remix: ``MultiDB`` keeps files of records where every
attribute maps to a list of values. ``LIST`` parses plain-English
conditions (CONTAINING, STARTING, =, !=, >, <, AND) against any of the
values an attribute holds. ``DICT.<file>`` is itself a file whose records
describe each attribute — ask the store about its own shape with the same
``LIST`` you use for data.

Honesty: LOAD-BEARING for small personal datasets. The query language is
deliberately small (no joins, no subqueries, no aggregates beyond COUNT);
matching is any-value semantics on in-memory lists; values must be
JSON-serializable for the store to stay honest. Stdlib only, no network.
"""

import shlex

ORIGIN = "levi-revival/manyfields"

_OPS = ("CONTAINING", "STARTING", "!=", ">=", "<=", "=", ">", "<")


def _num(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class MultiDB:
    """Records whose attributes hold N values; schema stored as data."""

    def __init__(self):
        self._files = {}  # file -> {"dict": {attr: spec}, "records": [record]}
        self._seq = 0

    # -- dictionaries: the schema, stored as data ---------------------------
    def define_file(self, name, attributes):
        """Declare a file; ``attributes`` maps attr -> spec dict.

        A spec is ``{"multivalued": bool, "note": str}``. The declaration is
        stored as ordinary records in the ``DICT.<name>`` file — the schema
        is data, queryable with LIST like everything else.
        """
        self._files[name] = {"dict": dict(attributes), "records": []}
        dict_file = f"DICT.{name}"
        self._files[dict_file] = {"dict": {}, "records": []}
        for attr, spec in attributes.items():
            self._files[dict_file]["records"].append(
                {
                    "id": [attr],
                    "attribute": [attr],
                    "multivalued": [bool(spec.get("multivalued", False))],
                    "note": [spec.get("note", "")],
                }
            )
        return name

    def dictionary(self, name):
        """The schema of ``name`` as plain data."""
        return self._files[name]["dict"]

    # -- records: attributes hold lists, genuinely --------------------------
    def add(self, file, **fields):
        """Add a record; each attribute value may be scalar or a list."""
        entry = self._files[file]
        record = {}
        for attr, value in fields.items():
            vals = list(value) if isinstance(value, (list, tuple)) else [value]
            mv = entry["dict"].get(attr, {}).get("multivalued", True)
            if not mv and len(vals) > 1:
                raise ValueError(
                    f"{file}.{attr} is single-valued; got {len(vals)} values"
                )
            record[attr] = vals
        self._seq += 1
        record["id"] = [f"{file}*{self._seq}"]
        entry["records"].append(record)
        return record["id"][0]

    # -- English-like queries ------------------------------------------------
    def query(self, text):
        """Run ``LIST <file> [attrs...] [WITH <cond> [AND <cond>...]]``."""
        tokens = shlex.split(text)
        if not tokens or tokens[0].upper() != "LIST":
            raise ValueError("queries start with LIST")
        if len(tokens) < 2:
            raise ValueError("LIST needs a file name")
        file = tokens[1]
        if file not in self._files:
            raise KeyError(f"unknown file {file!r}")
        rest = tokens[2:]
        with_at = next((i for i, t in enumerate(rest) if t.upper() == "WITH"), None)
        if with_at is None:
            attrs, cond_tokens = rest, []
        else:
            attrs, cond_tokens = rest[:with_at], rest[with_at + 1 :]
        conds = self._parse_conditions(cond_tokens)
        rows = []
        for record in self._files[file]["records"]:
            if all(self._satisfies(record, c) for c in conds):
                rows.append(self._project(record, attrs))
        return rows

    def count(self, text):
        """How many records a LIST query would return."""
        return len(self.query(text))

    def _parse_conditions(self, tokens):
        conds, current = [], []
        for tok in tokens:
            if tok.upper() == "AND":
                conds.append(self._parse_one(current))
                current = []
            else:
                current.append(tok)
        if current:
            conds.append(self._parse_one(current))
        return conds

    def _parse_one(self, tokens):
        upper = [t.upper() for t in tokens]
        for op in _OPS:
            if op in upper:
                i = upper.index(op)
                attr = " ".join(tokens[:i])
                value = " ".join(tokens[i + 1 :])
                if not attr or not value:
                    raise ValueError(f"bad condition: {' '.join(tokens)!r}")
                return (attr, op, value)
        raise ValueError(f"no operator in condition: {' '.join(tokens)!r}")

    def _satisfies(self, record, cond):
        attr, op, want = cond
        values = record.get(attr, [])
        if op == "CONTAINING":
            return any(want.lower() in str(v).lower() for v in values)
        if op == "STARTING":
            return any(str(v).lower().startswith(want.lower()) for v in values)
        if op == "=":
            return any(self._eq(v, want) for v in values)
        if op == "!=":
            return values and all(not self._eq(v, want) for v in values)
        if op in (">", "<", ">=", "<="):
            return any(self._cmp(v, want, op) for v in values)
        raise ValueError(op)  # unreachable: parser gates operators

    @staticmethod
    def _eq(got, want):
        gn, wn = _num(got), _num(want)
        if gn is not None and wn is not None:
            return gn == wn
        return str(got) == want

    @staticmethod
    def _cmp(got, want, op):
        gn, wn = _num(got), _num(want)
        a, b = (gn, wn) if gn is not None and wn is not None else (str(got), want)
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]

    @staticmethod
    def _project(record, attrs):
        if not attrs:
            return {k: list(v) for k, v in record.items()}
        return {a: list(record.get(a, [])) for a in attrs}
