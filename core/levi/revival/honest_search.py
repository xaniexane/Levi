"""Honest search — a box that returns the web, ranked by the index.

Studied from: honest-markets-20260916, findings.jsonl
[arch-honest-altavista-honest-contract] — the AltaVista honest search
contract: a box returning the web ranked by the index — advanced
boolean/full-text querying, no engagement layer, no personalization
theater; the index is the product and the user is the customer.

This module models that contract: ``Index`` documents (id, title, body);
``search`` parses boolean queries (AND, OR, NOT, quoted phrases,
parentheses) and ranks matches by plain term-frequency score with a
title bonus — the same for every caller, every time. No profiles, no
click tracking, no engagement weighting. Local in-memory inverted index.

Honesty: term-frequency ranking is a deliberate simplification of
historical ranking (stated openly), not a reproduction of AltaVista's
algorithm; the "contract" kept is structural — deterministic,
impersonal, inspectable ranking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

ORIGIN = "levi-revival/honest-search"

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Document:
    """One indexed document."""

    doc_id: str
    title: str
    body: str


@dataclass(frozen=True)
class Hit:
    """A ranked result: document id, title, and the honest score."""

    doc_id: str
    title: str
    score: float


class _Node:
    def evaluate(self, index: "Index") -> Set[str]:
        raise NotImplementedError

    def terms(self) -> List[str]:
        raise NotImplementedError


class _Term(_Node):
    def __init__(self, text: str, phrase: bool = False) -> None:
        self.text = text
        self.phrase = phrase

    def evaluate(self, index: "Index") -> Set[str]:
        if self.phrase:
            needle = self.text.lower()
            return {
                d.doc_id
                for d in index.documents.values()
                if needle in (d.title + " " + d.body).lower()
            }
        return set(index.postings.get(self.text.lower(), ()))

    def terms(self) -> List[str]:
        return _tokenize(self.text)


class _Not(_Node):
    def __init__(self, child: _Node) -> None:
        self.child = child

    def evaluate(self, index: "Index") -> Set[str]:
        all_ids = set(index.documents)
        return all_ids - self.child.evaluate(index)

    def terms(self) -> List[str]:
        return []


class _And(_Node):
    def __init__(self, children: List[_Node]) -> None:
        self.children = children

    def evaluate(self, index: "Index") -> Set[str]:
        result: Set[str] | None = None
        for child in self.children:
            hits = child.evaluate(index)
            result = hits if result is None else result & hits
        return result or set()

    def terms(self) -> List[str]:
        return [t for c in self.children for t in c.terms()]


class _Or(_Node):
    def __init__(self, children: List[_Node]) -> None:
        self.children = children

    def evaluate(self, index: "Index") -> Set[str]:
        result: Set[str] = set()
        for child in self.children:
            result |= child.evaluate(index)
        return result

    def terms(self) -> List[str]:
        return [t for c in self.children for t in c.terms()]


_QUERY_TOKEN = re.compile(
    r'"([^"]*)"|(\()|(\))|\b(AND|OR|NOT)\b|([^\s()"]+)',
    re.IGNORECASE,
)


def _parse(query: str) -> _Node:
    """Recursive-descent parse of AND/OR/NOT, quotes, parentheses."""
    tokens: List[Tuple[str, str]] = []
    for match in _QUERY_TOKEN.finditer(query):
        phrase, lpar, rpar, op, word = match.groups()
        if phrase is not None:
            tokens.append(("PHRASE", phrase))
        elif lpar:
            tokens.append(("LPAR", lpar))
        elif rpar:
            tokens.append(("RPAR", rpar))
        elif op:
            tokens.append(("OP", op.upper()))
        else:
            tokens.append(("WORD", word))
    pos = [0]

    def peek() -> Tuple[str, str] | None:
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def parse_or() -> _Node:
        node = parse_and()
        children = [node]
        while peek() == ("OP", "OR"):
            pos[0] += 1
            children.append(parse_and())
        return children[0] if len(children) == 1 else _Or(children)

    def parse_and() -> _Node:
        children = [parse_not()]
        while True:
            nxt = peek()
            if nxt is None or nxt == ("RPAR", ")") or nxt == ("OP", "OR"):
                break
            if nxt == ("OP", "AND"):
                pos[0] += 1
            children.append(parse_not())
        return children[0] if len(children) == 1 else _And(children)

    def parse_not() -> _Node:
        if peek() == ("OP", "NOT"):
            pos[0] += 1
            return _Not(parse_not())
        return parse_atom()

    def parse_atom() -> _Node:
        tok = peek()
        if tok is None:
            raise ValueError("empty query")
        if tok[0] == "LPAR":
            pos[0] += 1
            node = parse_or()
            if peek() != ("RPAR", ")"):
                raise ValueError("unbalanced parenthesis")
            pos[0] += 1
            return node
        if tok[0] == "PHRASE":
            pos[0] += 1
            return _Term(tok[1], phrase=True)
        if tok[0] == "WORD":
            pos[0] += 1
            return _Term(tok[1])
        raise ValueError(f"unexpected token {tok[1]!r}")

    node = parse_or()
    if peek() is not None:
        raise ValueError(f"unexpected token {peek()[1]!r}")
    return node


class Index:
    """An impersonal inverted index: same query, same answer, always."""

    def __init__(self) -> None:
        self.documents: Dict[str, Document] = {}
        self.postings: Dict[str, Set[str]] = {}

    def add(self, document: Document) -> None:
        if document.doc_id in self.documents:
            raise ValueError(f"duplicate doc {document.doc_id!r}")
        self.documents[document.doc_id] = document
        for token in set(_tokenize(document.title + " " + document.body)):
            self.postings.setdefault(token, set()).add(document.doc_id)

    def search(self, query: str, limit: int = 10) -> List[Hit]:
        """Boolean match, then rank by term frequency (title x3)."""
        if not query.strip():
            return []
        node = _parse(query)
        matched = node.evaluate(self)
        terms = node.terms()
        hits: List[Hit] = []
        for doc_id in matched:
            doc = self.documents[doc_id]
            title_tokens = _tokenize(doc.title)
            body_tokens = _tokenize(doc.body)
            score = 0.0
            for term in terms:
                score += 3.0 * title_tokens.count(term)
                score += 1.0 * body_tokens.count(term)
            hits.append(Hit(doc_id, doc.title, score))
        hits.sort(key=lambda h: (-h.score, h.doc_id))
        return hits[:limit]
