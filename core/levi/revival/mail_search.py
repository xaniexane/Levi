"""LEVI's mail search: instant local search over the archive.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(Ultra-fast search over the local archive.)

The studied shape refused the waiting cursor: your whole archive was
searchable *now*, because the index lived on your own disk. This
module rebuilds that as LEVI's own search index. An inverted index
maps every token to the documents and fields containing it, with
positions for phrase queries. Searches are boolean AND by default,
with ``field:term`` restriction and ``"quoted phrases"``.

What this is NOT: a relevance engine. Ranking is simple term
frequency — documents with more hits sort first, ties break by
document id. No stemming, no synonyms, no learning; what you type is
what it looks for, tokenized the same way on both sides. The index is
in-memory, so "ultra-fast" means "no disk round-trip" — honest about
the scale it serves (a personal archive, not a data center).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


ORIGIN = "levi-revival/mail-search"

_TOKEN = re.compile(r"[a-z0-9]+")
_QUERY_TERM = re.compile(r'"([^"]+)"|(\S+)')
_FIELD_TERM = re.compile(r"^([a-zA-Z]+):(.+)$")

SEARCHABLE_FIELDS = ("from", "to", "subject", "body")


@dataclass
class SearchHit:
    """One result: the document id, its score, and what matched."""

    doc_id: str
    score: int
    matched_terms: List[str] = field(default_factory=list)


class MailIndex:
    """An inverted index over mail documents.

    A document is ``{"id": ..., "from": ..., "to": ..., "subject": ...,
    "body": ...}``. Indexing is incremental; removal is supported; the
    whole thing lives in memory.
    """

    def __init__(self) -> None:
        # token -> field -> doc_id -> [positions]
        self._index: Dict[str, Dict[str, Dict[str, List[int]]]] = {}
        self._docs: Dict[str, Dict[str, str]] = {}

    # -- indexing --------------------------------------------------------

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return _TOKEN.findall(text.lower())

    def add(self, doc: Dict[str, str]) -> None:
        """Index (or re-index) one document. ``doc["id"]`` is required."""
        doc_id = doc["id"]
        if doc_id in self._docs:
            self.remove(doc_id)
        stored = {f: doc.get(f, "") for f in SEARCHABLE_FIELDS}
        self._docs[doc_id] = stored
        for fname, text in stored.items():
            for pos, token in enumerate(self.tokenize(text)):
                self._index.setdefault(token, {}).setdefault(fname, {}).setdefault(
                    doc_id, []
                ).append(pos)

    def remove(self, doc_id: str) -> bool:
        """Drop a document. Returns False if it wasn't indexed."""
        if doc_id not in self._docs:
            return False
        del self._docs[doc_id]
        for token, fields in list(self._index.items()):
            for fname, docs in list(fields.items()):
                docs.pop(doc_id, None)
                if not docs:
                    del fields[fname]
            if not fields:
                del self._index[token]
        return True

    def document_count(self) -> int:
        return len(self._docs)

    def token_count(self) -> int:
        return len(self._index)

    # -- searching ----------------------------------------------------------

    def search(self, query: str, limit: Optional[int] = None) -> List[SearchHit]:
        """Search the index.

        Terms are ANDed: a document must contain every term. Prefix a
        term with ``from:`` / ``to:`` / ``subject:`` / ``body:`` to
        restrict it to that field. Quote words for an exact phrase.
        Returns hits sorted by score (term frequency), then doc id.
        """
        clauses = self._parse_query(query)
        if not clauses:
            return []
        per_clause: List[Dict[str, int]] = []  # doc_id -> hit count
        for is_phrase, fname, terms in clauses:
            per_clause.append(self._match_clause(is_phrase, fname, terms))
        common: Optional[Set[str]] = None
        for matches in per_clause:
            ids = set(matches)
            common = ids if common is None else common & ids
        if not common:
            return []
        hits = []
        for doc_id in common:
            score = sum(m[doc_id] for m in per_clause)
            matched = [
                term
                for is_phrase, _, terms in clauses
                for term in ([" ".join(terms)] if is_phrase else terms)
            ]
            hits.append(SearchHit(doc_id=doc_id, score=score, matched_terms=matched))
        hits.sort(key=lambda h: (-h.score, h.doc_id))
        return hits[:limit] if limit is not None else hits

    def _parse_query(self, query: str) -> List[Tuple[bool, Optional[str], List[str]]]:
        clauses = []
        for quoted, bare in _QUERY_TERM.findall(query):
            raw = quoted if quoted else bare
            fname: Optional[str] = None
            m = _FIELD_TERM.match(raw)
            if m and m.group(1).lower() in SEARCHABLE_FIELDS:
                fname = m.group(1).lower()
                raw = m.group(2)
            terms = self.tokenize(raw)
            if terms:
                clauses.append((bool(quoted), fname, terms))
        return clauses

    def _match_clause(
        self, is_phrase: bool, fname: Optional[str], terms: List[str]
    ) -> Dict[str, int]:
        fields = [fname] if fname else list(SEARCHABLE_FIELDS)
        if not is_phrase:
            # plain AND of terms across the allowed fields
            counts: Optional[Dict[str, int]] = None
            for term in terms:
                term_hits: Dict[str, int] = {}
                for f in fields:
                    for doc_id, positions in (
                        self._index.get(term, {}).get(f, {}).items()
                    ):
                        term_hits[doc_id] = term_hits.get(doc_id, 0) + len(positions)
                counts = (
                    term_hits
                    if counts is None
                    else {d: counts[d] + term_hits[d] for d in counts if d in term_hits}
                )
            return counts or {}
        # phrase: positions must be consecutive in one field
        first = terms[0]
        result: Dict[str, int] = {}
        for f in fields:
            postings = self._index.get(first, {}).get(f, {})
            for doc_id, positions in postings.items():
                others = [
                    set(self._index.get(t, {}).get(f, {}).get(doc_id, []))
                    for t in terms[1:]
                ]
                for pos in positions:
                    if all((pos + i + 1) in others[i] for i in range(len(others))):
                        result[doc_id] = result.get(doc_id, 0) + 1
        return result
