"""Uniterm coordinate indexing: uncontrolled terms, structure deferred to query time.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #11)

The load-bearing mechanism: terms come from the documents themselves —
no controlled vocabulary, no pre-built hierarchy, no citation-order
rules. Indexing is cheap (pull the words). The intellectual work moves
to the searcher, who *coordinates* terms at the moment of the question.
No black-box ranking: every query is an explicit AND/OR/NOT tree the
user can read, and every result shows its coordination.

:meth:`UnitermFile.coordinate` returns an inspectable Boolean core for
each query: the parsed tree in readable form, the per-term hit sets,
and exactly which terms each matched document satisfied.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is uncontrolled document-derived terms
plus explicit, inspectable query-time coordination. Not revived: manual
term-cards, or synonym thesauri — synonym scatter is documented as the
known weakness, not papered over.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ORIGIN = "levi-revival/uniterm"


_TOKEN = re.compile(r"[a-z0-9]+")


def extract_terms(text: str) -> list[str]:
    """Pull uniterms from a document: lowercase word tokens, in order,
    duplicates dropped. No vocabulary control — the documents decide."""
    seen: dict[str, None] = {}
    for token in _TOKEN.findall(text.lower()):
        seen.setdefault(token)
    return list(seen)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnitermError(Exception):
    """Base class for uniterm failures."""


class QuerySyntaxError(UnitermError):
    """A query could not be parsed."""


# ---------------------------------------------------------------------------
# The Boolean core: explicit AND/OR/NOT trees
# ---------------------------------------------------------------------------


class Node:
    """Base of the query tree."""

    def evaluate(self, postings: dict[str, set[str]]) -> set[str]:
        raise NotImplementedError

    def read(self) -> str:
        """The tree in plain, readable form."""
        raise NotImplementedError

    def terms(self) -> set[str]:
        raise NotImplementedError


class Term(Node):
    """One uniterm."""

    def __init__(self, term: str):
        self.term = term

    def evaluate(self, postings: dict[str, set[str]]) -> set[str]:
        return set(postings.get(self.term, ()))

    def read(self) -> str:
        return self.term

    def terms(self) -> set[str]:
        return {self.term}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Term({self.term!r})"


class And(Node):
    def __init__(self, *children: Node):
        if len(children) < 2:
            raise ValueError("AND needs at least two branches")
        self.children = list(children)

    def evaluate(self, postings: dict[str, set[str]]) -> set[str]:
        result = self.children[0].evaluate(postings)
        for child in self.children[1:]:
            result &= child.evaluate(postings)
        return result

    def read(self) -> str:
        return "(" + " AND ".join(c.read() for c in self.children) + ")"

    def terms(self) -> set[str]:
        return set().union(*(c.terms() for c in self.children))


class Or(Node):
    def __init__(self, *children: Node):
        if len(children) < 2:
            raise ValueError("OR needs at least two branches")
        self.children = list(children)

    def evaluate(self, postings: dict[str, set[str]]) -> set[str]:
        result: set[str] = set()
        for child in self.children:
            result |= child.evaluate(postings)
        return result

    def read(self) -> str:
        return "(" + " OR ".join(c.read() for c in self.children) + ")"

    def terms(self) -> set[str]:
        return set().union(*(c.terms() for c in self.children))


class Not(Node):
    def __init__(self, child: Node):
        self.child = child

    def evaluate(self, postings: dict[str, set[str]]) -> set[str]:
        universe = set().union(*postings.values()) if postings else set()
        return universe - self.child.evaluate(postings)

    def read(self) -> str:
        return f"NOT {self.child.read()}"

    def terms(self) -> set[str]:
        return self.child.terms()


# -- tiny query parser: "deadline AND grant NOT rejected" -------------------
_OPS = {"AND", "OR", "NOT"}


def parse_query(text: str) -> Node:
    """Parse an explicit Boolean query into a tree. Operators AND/OR/NOT
    (case-insensitive), parentheses for grouping, implicit AND between
    adjacent terms — so ``grant deadline`` means ``grant AND deadline``.

    Precedence: NOT binds tightest, then AND, then OR.
    """
    tokens = re.findall(r"\(|\)|[^\s()]+", text)
    if not tokens:
        raise QuerySyntaxError("empty query")
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def advance() -> str:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_or() -> Node:
        node = parse_and()
        while peek() and peek().upper() == "OR":
            advance()
            node = Or(node, parse_and())
        return node

    def parse_and() -> Node:
        node = parse_not()
        while True:
            nxt = peek()
            if nxt is None or nxt == ")" or nxt.upper() == "OR":
                break
            if nxt.upper() == "AND":
                advance()
            node = And(node, parse_not())
        return node

    def parse_not() -> Node:
        if peek() and peek().upper() == "NOT":
            advance()
            return Not(parse_not())
        return parse_atom()

    def parse_atom() -> Node:
        tok = peek()
        if tok is None:
            raise QuerySyntaxError("unexpected end of query")
        if tok == "(":
            advance()
            node = parse_or()
            if peek() != ")":
                raise QuerySyntaxError("missing closing parenthesis")
            advance()
            return node
        if tok.upper() in _OPS or tok == ")":
            raise QuerySyntaxError(f"unexpected {tok!r}")
        advance()
        return Term(tok.lower())

    tree = parse_or()
    if pos != len(tokens):
        raise QuerySyntaxError(f"trailing tokens: {' '.join(tokens[pos:])}")
    return tree


# ---------------------------------------------------------------------------
# The uniterm file
# ---------------------------------------------------------------------------


class UnitermFile:
    """Documents indexed under their own uncontrolled terms; meaning is
    composed at query time by coordinating them."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.docs: dict[str, str] = {}  # doc_id -> title
        self.postings: dict[str, set[str]] = {}  # uniterm -> doc_ids
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "uniterm.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.docs = dict(data.get("docs", {}))
        self.postings = {k: set(v) for k, v in data.get("postings", {}).items()}

    def save(self) -> Path:
        """Persist the file. Only meaningful when constructed with a path."""
        if self.path is None:
            raise UnitermError("no path: this file is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "docs": self.docs,
                    "postings": {k: sorted(v) for k, v in self.postings.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- indexing: cheap, uncontrolled -------------------------------------
    def index(self, doc_id: str, text: str, title: str = "") -> list[str]:
        """Post a document under its own terms. Returns the terms used."""
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        self.docs[doc_id] = title or doc_id
        terms = extract_terms(text)
        for term in terms:
            self.postings.setdefault(term, set()).add(doc_id)
        return terms

    def unindex(self, doc_id: str) -> None:
        """Withdraw a document from every term's posting list."""
        if doc_id not in self.docs:
            raise UnitermError(f"unknown document {doc_id!r}")
        del self.docs[doc_id]
        for term in list(self.postings):
            self.postings[term].discard(doc_id)
            if not self.postings[term]:
                del self.postings[term]

    def vocabulary(self) -> list[str]:
        """Every uniterm on file — the uncontrolled vocabulary, visible."""
        return sorted(self.postings)

    # -- coordination: structure at query time ------------------------------
    def coordinate(self, query: str | Node) -> dict:
        """Run a query and show the inspectable Boolean core: the readable
        tree, each term's hit set, and — per matched document — exactly
        which terms it satisfied."""
        tree = parse_query(query) if isinstance(query, str) else query
        matches = tree.evaluate(self.postings)
        per_term = {t: sorted(self.postings.get(t, ())) for t in sorted(tree.terms())}
        why = {
            doc: sorted(t for t in tree.terms() if doc in self.postings.get(t, ()))
            for doc in sorted(matches)
        }
        return {
            "tree": tree.read(),
            "matches": sorted(matches),
            "per_term": per_term,
            "why": why,
            "titles": {d: self.docs[d] for d in sorted(matches)},
        }

    def doc_count(self) -> int:
        return len(self.docs)


__all__ = [
    "ORIGIN",
    "UnitermError",
    "QuerySyntaxError",
    "Node",
    "Term",
    "And",
    "Or",
    "Not",
    "parse_query",
    "extract_terms",
    "UnitermFile",
]
