"""Uniterm coordinate indexing: post-coordinate boolean search.

History: Mortimer Taube's 1950s system — extract single descriptive words
(*uniterms*) from each document; post each document number under its
uniterms on term-cards; at search time, *coordinate* (AND) the term-cards.
No controlled vocabulary, no pre-built hierarchy — terms come from the
documents, and combination happens at the moment of the question. The direct
ancestor of keyword search and the inverted index. Died as a manual system
(term-cards don't scale by hand; uncontrolled vocabulary caused synonym
scatter); computers absorbed the mechanism.

In LEVI: the revival is a *discipline*. :class:`UnitermIndex` indexes
everything with uncontrolled, document-derived terms; at query time a small
boolean parser (AND/OR/NOT, parentheses) coordinates them, and every search
returns an explicit coordination trace ("matched: 'deadline' AND 'grant' NOT
'rejected'") so you can see *why* a result matched and toggle each term.
Synonym expansion is caller-provided and visible — no hidden NLP, no
black-box ranking without an inspectable Boolean core.

Honesty: LOAD-BEARING — the ancestor of the inverted index, with its manual
transparency restored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Document:
    doc_id: str
    terms: set[str]
    title: str = ""


class _Parser:
    """Tiny recursive-descent parser for AND/OR/NOT with parentheses."""

    TOKEN = re.compile(r"\s*(\(|\)|AND|OR|NOT|\"[^\"]+\"|[^\s()]+)\s*", re.IGNORECASE)

    def __init__(self, query: str):
        self.tokens = [t for t in self.TOKEN.findall(query) if t]
        self.pos = 0
        # normalize quoted phrases to single terms
        self.tokens = [t[1:-1] if t.startswith('"') else t for t in self.tokens]

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self):
        if not self.tokens:
            raise ValueError("empty query")
        node = self._or()
        if self.peek() is not None:
            raise ValueError(f"unexpected token {self.peek()!r}")
        return node

    def _or(self):
        node = self._and()
        while self.peek() and self.peek().upper() == "OR":
            self.next()
            node = ("OR", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while True:
            tok = self.peek()
            if tok is None or tok.upper() == "OR" or tok == ")":
                return node
            if tok.upper() == "AND":
                self.next()
            # implicit AND between adjacent terms
            node = ("AND", node, self._not())

    def _not(self):
        if self.peek() and self.peek().upper() == "NOT":
            self.next()
            return ("NOT", self._not())
        return self._atom()

    def _atom(self):
        tok = self.next()
        if tok is None:
            raise ValueError("unexpected end of query")
        if tok == "(":
            node = self._or()
            if self.next() != ")":
                raise ValueError("missing closing parenthesis")
            return node
        if tok.upper() in ("AND", "OR", "NOT") or tok in ("(", ")"):
            raise ValueError(f"unexpected token {tok!r}")
        return ("TERM", tok.lower())


class UnitermIndex:
    """Post-coordinate index: terms -> doc sets, combined at query time."""

    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.postings: dict[str, set[str]] = {}  # term -> doc_ids

    def add(self, doc_id: str, terms: list[str], title: str = "") -> None:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("doc_id must be non-empty")
        if doc_id in self.documents:
            raise ValueError(f"document {doc_id!r} already indexed")
        clean = {t.strip().lower() for t in terms if t and t.strip()}
        if not clean:
            raise ValueError("document needs at least one term")
        self.documents[doc_id] = Document(doc_id, clean, title)
        for term in clean:
            self.postings.setdefault(term, set()).add(doc_id)

    def _eval(self, node) -> set[str]:
        kind = node[0]
        if kind == "TERM":
            return set(self.postings.get(node[1], ()))
        if kind == "NOT":
            return set(self.documents) - self._eval(node[1])
        if kind == "AND":
            return self._eval(node[1]) & self._eval(node[2])
        if kind == "OR":
            return self._eval(node[1]) | self._eval(node[2])
        raise ValueError(f"bad node {node!r}")  # unreachable; deny-closed

    @staticmethod
    def _render(node) -> str:
        kind = node[0]
        if kind == "TERM":
            return f"'{node[1]}'"
        if kind == "NOT":
            return f"NOT {UnitermIndex._render(node[1])}"
        return f"({UnitermIndex._render(node[1])} {kind} {UnitermIndex._render(node[2])})"

    def search(self, query: str, synonyms: dict[str, list[str]] | None = None) -> dict:
        """Coordinate the query. ``synonyms`` is caller-provided and reported
        in the trace — expansion is explicit, never hidden.

        Returns {doc_ids, coordination, trace, expanded_terms}."""
        node = _Parser(query).parse()
        expanded: dict[str, list[str]] = {}
        if synonyms:
            node = self._expand_synonyms(node, synonyms, expanded)
        doc_ids = sorted(self._eval(node))
        return {
            "doc_ids": doc_ids,
            "coordination": self._render(node),
            "trace": f"matched: {self._render(node)} -> {doc_ids if doc_ids else 'no documents'}",
            "expanded_terms": expanded,
        }

    def _expand_synonyms(self, node, synonyms, expanded):
        kind = node[0]
        if kind == "TERM":
            term = node[1]
            syns = [s.strip().lower() for s in synonyms.get(term, []) if s and s.strip()]
            syns = [s for s in syns if s != term]
            if syns:
                expanded[term] = syns
                or_node: tuple = ("TERM", term)
                for s in syns:
                    or_node = ("OR", or_node, ("TERM", s))
                return or_node
            return node
        if kind == "NOT":
            return ("NOT", self._expand_synonyms(node[1], synonyms, expanded))
        return (kind, self._expand_synonyms(node[1], synonyms, expanded),
                self._expand_synonyms(node[2], synonyms, expanded))

    def vocabulary(self) -> list[str]:
        return sorted(self.postings)
