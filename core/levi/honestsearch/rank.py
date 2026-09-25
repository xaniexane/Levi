"""Ranking: clean-room PageRank-style link graph + tf-idf text match.

THE MATH (documented so anyone can check it by hand):

PageRank. For pages V with outlinks, with damping factor d (0.85):

    PR(v) = (1-d)/|V| + d * ( SUM_{u -> v} PR(u)/outdeg(u)
                              + dangling/|V| )

where ``dangling`` is the total rank of pages with no outlinks,
redistributed evenly (the standard dangling-node fix). Solved by power
iteration to a tolerance of 1e-9 (max 200 iterations). Only links between
*indexed* documents count — the graph is the corpus, not the web.

Text score. For query terms t in document d:

    text(d) = SUM_t  tf(t,d) * idf(t)
    tf(t,d)  = 1 + ln(count(t,d))          (log term frequency)
    idf(t)   = ln((N+1)/(df(t)+1)) + 1     (smoothed inverse doc frequency)

Combined score. Both signals are normalized to [0,1] by dividing by the
corpus max, then combined with the declared weight vector:

    score(d) = w_text * text_norm(d) + w_link * pr_norm(d)

Default weights are text=0.6, link=0.4 — visible, tunable, and printed
with every query.

UNPERSONALIZED MODE. This is structural, not a flag: ``search()``
accepts ``(index, query, weights, top_k)`` and nothing else. There is no
profile, history, or identity parameter anywhere in the ranking path, so
there is nothing to leak into the order. The test suite asserts this
from the function signature and by re-running queries against stores
polluted with fake profile data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

from levi.honestsearch.index import InvertedIndex, tokenize
from levi.honestsearch.model import Document

DAMPING = 0.85
PR_TOL = 1e-9
PR_MAX_ITER = 200

DEFAULT_WEIGHTS = {"text": 0.6, "link": 0.4}
SIGNAL_NAMES = ("text", "link")


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Validate and normalize a weight vector (sums to 1, all >= 0)."""
    cleaned = {}
    for name in SIGNAL_NAMES:
        if name not in weights:
            raise ValueError("weight vector missing signal %r" % name)
        value = float(weights[name])
        if not math.isfinite(value) or value < 0:
            raise ValueError("weight %r must be a finite non-negative number" % name)
        cleaned[name] = value
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return {k: v / total for k, v in cleaned.items()}


def parse_weights(spec: str) -> Dict[str, float]:
    """Parse ``text=0.6,link=0.4`` into a normalized weight vector."""
    parts = {}
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            raise ValueError("bad weight spec %r (want text=0.6,link=0.4)" % chunk)
        key, _, value = chunk.partition("=")
        key = key.strip()
        if key not in SIGNAL_NAMES:
            raise ValueError("unknown signal %r (want text and/or link)" % key)
        try:
            parts[key] = float(value)
        except ValueError:
            raise ValueError("bad weight value %r" % value) from None
    return normalize_weights(parts)


def pagerank(
    graph: Dict[str, List[str]],
    damping: float = DAMPING,
    tol: float = PR_TOL,
    max_iter: int = PR_MAX_ITER,
) -> Dict[str, float]:
    """Clean-room PageRank over ``{node: [out-neighbors]}``.

    Neighbors not present as keys are ignored (only indexed documents
    count). Dangling nodes (no outlinks) redistribute their rank evenly.
    Returns ranks summing to 1. Empty graph -> {}.
    """
    nodes = sorted(graph)
    n = len(nodes)
    if n == 0:
        return {}
    if not 0.0 < damping < 1.0:
        raise ValueError("damping must be in (0, 1)")
    node_set = set(nodes)
    # Only neighbors that are indexed documents count as links.
    out = {v: sorted({u for u in graph[v] if u in node_set}) for v in nodes}
    rank = {v: 1.0 / n for v in nodes}
    base = (1.0 - damping) / n
    for _ in range(max_iter):
        dangling = sum(r for v, r in rank.items() if not out[v])
        new = {}
        for v in nodes:
            incoming = sum(rank[u] / len(out[u]) for u in nodes if v in out[u])
            new[v] = base + damping * (incoming + dangling / n)
        delta = sum(abs(new[v] - rank[v]) for v in nodes)
        rank = new
        if delta < tol:
            break
    total = sum(rank.values()) or 1.0
    return {v: r / total for v, r in rank.items()}


def _link_graph(index: InvertedIndex) -> Dict[str, List[str]]:
    url_to_id = {d.url: d.doc_id for d in index.docs.values()}
    graph: Dict[str, List[str]] = {}
    for doc_id, doc in index.docs.items():
        nbrs = []
        for link in doc.outlinks:
            target = url_to_id.get(link)
            if target and target != doc_id and target not in nbrs:
                nbrs.append(target)
        graph[doc_id] = nbrs
    return graph


def text_scores(index: InvertedIndex, terms: List[str]) -> Dict[str, float]:
    """Summed tf-idf per document for *terms* (raw, unnormalized)."""
    n = len(index.docs)
    scores: Dict[str, float] = {}
    for term in set(terms):
        postings = index.postings.get(term)
        if not postings:
            continue
        idf = math.log((n + 1) / (len(postings) + 1)) + 1
        for doc_id, tf in postings.items():
            scores[doc_id] = scores.get(doc_id, 0.0) + (1 + math.log(tf)) * idf
    return scores


def _normalize(scores: Dict[str, float]) -> Dict[str, float]:
    peak = max(scores.values()) if scores else 0.0
    if peak <= 0:
        return {k: 0.0 for k in scores}
    return {k: v / peak for k, v in scores.items()}


@dataclass
class ScoredResult:
    doc: Document
    total: float
    contributions: Dict[str, float] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)


def search(
    index: InvertedIndex,
    query: str,
    weights: Dict[str, float] | None = None,
    top_k: int = 10,
) -> List[ScoredResult]:
    """Rank documents for *query*. No profile enters this function.

    Returns ScoredResults sorted by total desc (doc_id tie-break for
    determinism), each carrying per-signal contributions so the CLI can
    explain exactly what produced the order.
    """
    w = normalize_weights(dict(weights) if weights else DEFAULT_WEIGHTS)
    terms = [t for t in tokenize(query) if t]
    if not terms or not index.docs:
        return []
    raw_text = text_scores(index, terms)
    if not raw_text:
        return []
    # Retrieval gate: a candidate must match at least one query term.
    # Weights rank the candidates; they never smuggle in non-matching docs.
    text = _normalize(raw_text)
    link = _normalize(pagerank(_link_graph(index)))
    matched: Dict[str, List[str]] = {}
    for term in set(terms):
        for doc_id in index.postings.get(term, {}):
            matched.setdefault(doc_id, []).append(term)
    results = []
    for doc_id, doc in index.docs.items():
        if doc_id not in raw_text:
            continue  # retrieval gate: must match >= 1 query term
        contrib = {
            "text": w["text"] * text.get(doc_id, 0.0),
            "link": w["link"] * link.get(doc_id, 0.0),
        }
        results.append(
            ScoredResult(
                doc=doc,
                total=contrib["text"] + contrib["link"],
                contributions=contrib,
                matched_terms=sorted(matched.get(doc_id, [])),
            )
        )
    results.sort(key=lambda r: (-r.total, r.doc.doc_id))
    return [r for r in results if r.total > 0][: max(1, top_k)]


def explain(result: ScoredResult, weights: Dict[str, float]) -> str:
    """Human-readable account of which signals produced this result."""
    w = normalize_weights(dict(weights))
    lines = [
        "%s  (total %.4f)" % (result.doc.title or result.doc.url, result.total),
        "  url: %s" % result.doc.url,
        "  matched terms: %s" % (", ".join(result.matched_terms) or "(none)"),
    ]
    for signal in SIGNAL_NAMES:
        lines.append(
            "  %-4s  weight %.2f  norm-score %.4f  contribution %.4f"
            % (
                signal,
                w[signal],
                result.contributions[signal] / w[signal] if w[signal] else 0.0,
                result.contributions[signal],
            )
        )
    return "\n".join(lines)
