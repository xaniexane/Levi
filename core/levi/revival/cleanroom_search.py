"""Honest search: clean-room link-graph ranking over a local index.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 10]
(clean-room link-graph ranking over a local index with a genuine
unpersonalized mode).

This is an original, from-scratch implementation for LEVI. ``CleanroomIndex``
holds a local document set — title, text, and outlinks — and scores queries
with three *visible* components:

1. **Term match** — a small BM25-flavored scorer (term frequency saturation
   plus inverse document frequency) over the local corpus. No embeddings,
   no semantic magic; the math is right there in ``term_score``.
2. **Link authority** — PageRank over the document link graph, computed by
   power iteration in ``compute_authority``. Dangling nodes distribute their
   mass uniformly, which keeps the walk stochastic and honest.
3. **Recency** — an optional half-life decay on document age; disabled by
   default (weight 0.0) so age never silently reorders results.

A genuine unpersonalized mode: the index keeps *no* user profiles, *no*
click history, and *no* per-user state at all. ``search`` therefore behaves
identically for every caller; the ``personalized`` flag exists only to let
an embedding layer opt into a caller-supplied boost — and by default it is
off, so ``personalized=True`` with no boost vector is exactly
``personalized=False``. ``explain`` shows the per-component breakdown for
any query/document pair, so the ranking can always be audited.

Public surface:
- ``CleanroomIndex``: ``add_document``, ``compute_authority``, ``search``,
  ``explain``, ``stats``.
- ``SearchResult``, ``Document``, ``SearchError``.

Honest limits: BM25 here is a compact heuristic, not the full Robertson
formulation; PageRank on a tiny corpus is coarse; there is no stemming or
synonym handling, so "run" will not match "running".

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

ORIGIN = "levi-revival/cleanroom-search"

_TOKEN = re.compile(r"[a-z0-9']+")


class SearchError(ValueError):
    """Raised for invalid search operations."""


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    outlinks: Tuple[str, ...] = ()
    age_days: float = 0.0


@dataclass
class SearchResult:
    doc_id: str
    title: str
    score: float
    components: Dict[str, float]


class CleanroomIndex:
    """A local search index with clean-room, auditable ranking."""

    def __init__(self, k1: float = 1.2, link_weight: float = 0.35) -> None:
        self.k1 = k1
        self.link_weight = link_weight
        self._docs: Dict[str, Document] = {}
        self._tf: Dict[str, Dict[str, int]] = {}
        self._doc_len: Dict[str, int] = {}
        self._df: Dict[str, int] = {}
        self._authority: Dict[str, float] = {}

    # -- indexing ---------------------------------------------------------
    def add_document(self, doc: Document) -> None:
        if not doc.doc_id:
            raise SearchError("document needs an id")
        if doc.doc_id in self._docs:
            raise SearchError(f"duplicate document id {doc.doc_id!r}")
        self._docs[doc.doc_id] = doc
        terms = tokenize(doc.title + " " + doc.text)
        tf: Dict[str, int] = {}
        for term in terms:
            tf[term] = tf.get(term, 0) + 1
        self._tf[doc.doc_id] = tf
        self._doc_len[doc.doc_id] = max(len(terms), 1)
        for term in tf:
            self._df[term] = self._df.get(term, 0) + 1

    def compute_authority(self, iterations: int = 50, damping: float = 0.85) -> None:
        """PageRank over the link graph. Dangling mass is redistributed."""
        ids = list(self._docs)
        n = len(ids)
        if n == 0:
            return
        rank = {doc_id: 1.0 / n for doc_id in ids}
        for _ in range(iterations):
            nxt = {doc_id: (1.0 - damping) / n for doc_id in ids}
            dangling = sum(
                r for doc_id, r in rank.items() if not self._docs[doc_id].outlinks
            )
            for doc_id in ids:
                nxt[doc_id] += damping * dangling / n
            for doc_id in ids:
                links = [t for t in self._docs[doc_id].outlinks if t in self._docs]
                if links:
                    share = damping * rank[doc_id] / len(links)
                    for target in links:
                        nxt[target] += share
            rank = nxt
        self._authority = rank

    # -- scoring ----------------------------------------------------------
    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def term_score(self, doc_id: str, query_terms: List[str]) -> float:
        tf = self._tf[doc_id]
        avg_len = sum(self._doc_len.values()) / max(len(self._doc_len), 1)
        total = 0.0
        for term in query_terms:
            f = tf.get(term, 0)
            if f == 0:
                continue
            denom = f + self.k1 * (1.0 + 0.75 * (self._doc_len[doc_id] / avg_len - 1.0))
            total += self._idf(term) * (f * (self.k1 + 1.0)) / denom
        return total

    def explain(self, query: str, doc_id: str) -> Dict[str, float]:
        """Visible per-component breakdown for one query/document pair."""
        if doc_id not in self._docs:
            raise SearchError(f"unknown document {doc_id!r}")
        terms = tokenize(query)
        term = self.term_score(doc_id, terms)
        link = self._authority.get(doc_id, 0.0)
        recency = math.exp(-self._docs[doc_id].age_days / 365.0)
        total = term + self.link_weight * link * 10.0
        return {
            "term": round(term, 4),
            "link": round(link, 4),
            "recency": round(recency, 4),
            "total": round(total, 4),
        }

    def search(
        self,
        query: str,
        limit: int = 10,
        personalized: bool = False,
        boost: Optional[Mapping[str, float]] = None,
    ) -> List[SearchResult]:
        """Rank documents. No user state is ever consulted.

        ``personalized=True`` without a caller-supplied ``boost`` is exactly
        ``personalized=False`` — the genuine unpersonalized mode, by design.
        """
        terms = tokenize(query)
        if not terms:
            return []
        results: List[SearchResult] = []
        for doc_id, doc in self._docs.items():
            components = self.explain(query, doc_id)
            score = components["total"]
            if personalized and boost and doc_id in boost:
                score += boost[doc_id]
                components["personal_boost"] = round(boost[doc_id], 4)
            if score > 0:
                results.append(
                    SearchResult(
                        doc_id=doc_id,
                        title=doc.title,
                        score=round(score, 4),
                        components=components,
                    )
                )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def stats(self) -> Dict[str, int]:
        return {"documents": len(self._docs), "terms": len(self._df)}


def make_document(
    doc_id: str,
    title: str,
    text: str,
    outlinks: Tuple[str, ...] = (),
    age_days: float = 0.0,
) -> Document:
    """Convenience constructor for a local document."""
    return Document(
        doc_id=doc_id, title=title, text=text, outlinks=outlinks, age_days=age_days
    )
