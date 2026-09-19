"""Hybrid retrieval: dense + BM25 sparse, fused by Reciprocal Rank Fusion.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.6)

Functional description: two first-stage retrievers run side by side. The
dense retriever is a plug-in similarity callable over caller-supplied
vectors (any embedding source — never a bundled provider). The sparse
retriever is BM25 implemented from scratch here, over the same corpus, for
exact terms, IDs, and rare tokens that embeddings smear away. Each
retriever returns a ranked list; Reciprocal Rank Fusion
(1/(k+rank) per list, summed) merges them without needing comparable
scores. Pure Python, stdlib only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

ORIGIN = "levi-revival/hybridfind"

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# BM25 from scratch
# --------------------------------------------------------------------------


class BM25:
    """Okapi BM25 over a corpus of token lists. Built from scratch."""

    def __init__(
        self, corpus: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.corpus = [list(doc) for doc in corpus]
        self.k1 = k1
        self.b = b
        self.n = len(self.corpus)
        self.doc_lens = [len(d) for d in self.corpus]
        self.avgdl = sum(self.doc_lens) / self.n if self.n else 0.0
        # document frequencies
        self.df: Dict[str, int] = {}
        for doc in self.corpus:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1
        # idf with the standard +1 smoothing so rare-but-present terms help
        self.idf: Dict[str, float] = {}
        for term, df in self.df.items():
            self.idf[term] = math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query_terms: Sequence[str], doc_idx: int) -> float:
        doc = self.corpus[doc_idx]
        dl = self.doc_lens[doc_idx]
        tf: Dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        total = 0.0
        for term in set(query_terms):
            if term not in self.idf:
                continue
            f = tf.get(term, 0)
            if not f:
                continue
            denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            total += self.idf[term] * (f * (self.k1 + 1) / denom)
        return total

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        terms = tokenize(query)
        scored = [(i, self.score(terms, i)) for i in range(self.n)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda p: -p[1])
        return scored[:top_k]


# --------------------------------------------------------------------------
# Dense (plug-in) retrieval
# --------------------------------------------------------------------------

Vector = List[float]
Similarity = Callable[[Vector, Vector], float]


def cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DenseIndex:
    """Brute-force dense index; similarity is injected, never built in."""

    def __init__(
        self, vectors: Sequence[Vector], similarity: Similarity = cosine
    ) -> None:
        self.vectors = [list(v) for v in vectors]
        self.similarity = similarity

    def search(self, query_vec: Vector, top_k: int = 10) -> List[Tuple[int, float]]:
        scored = [
            (i, self.similarity(query_vec, v)) for i, v in enumerate(self.vectors)
        ]
        scored.sort(key=lambda p: -p[1])
        return scored[:top_k]


# --------------------------------------------------------------------------
# RRF fusion
# --------------------------------------------------------------------------


def rrf_fuse(
    ranked_lists: Sequence[Sequence[Tuple[int, float]]], k: int = 60
) -> List[Tuple[int, float]]:
    """Reciprocal Rank Fusion: score(doc) = Σ 1/(k + rank)."""
    fused: Dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _score) in enumerate(ranked, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    out = sorted(fused.items(), key=lambda p: -p[1])
    return out


@dataclass
class HybridHit:
    doc_id: int
    fused_score: float
    dense_rank: int = -1
    sparse_rank: int = -1
    dense_score: float = 0.0
    sparse_score: float = 0.0


@dataclass
class HybridFinder:
    """Runs dense and sparse retrieval, fuses with RRF."""

    corpus_texts: List[str] = field(default_factory=list)
    vectors: List[Vector] = field(default_factory=list)
    similarity: Similarity = cosine
    rrf_k: int = 60

    def __post_init__(self) -> None:
        self._bm25 = BM25([tokenize(t) for t in self.corpus_texts])
        self._dense = DenseIndex(self.vectors, self.similarity)

    def search(self, query: str, query_vec: Vector, top_k: int = 10) -> List[HybridHit]:
        sparse = self._bm25.search(query, top_k=top_k)
        dense = self._dense.search(query_vec, top_k=top_k)
        fused = rrf_fuse([dense, sparse], k=self.rrf_k)
        dense_rank = {doc: r for r, (doc, _s) in enumerate(dense, 1)}
        sparse_rank = {doc: r for r, (doc, _s) in enumerate(sparse, 1)}
        dense_score = dict(dense)
        sparse_score = dict(sparse)
        return [
            HybridHit(
                doc_id=doc,
                fused_score=fscore,
                dense_rank=dense_rank.get(doc, -1),
                sparse_rank=sparse_rank.get(doc, -1),
                dense_score=dense_score.get(doc, 0.0),
                sparse_score=sparse_score.get(doc, 0.0),
            )
            for doc, fscore in fused[:top_k]
        ]
