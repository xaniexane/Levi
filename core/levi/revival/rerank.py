"""Cross-encoder reranking: cheap first stage → plug-in scorer → top-N.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.6)

Functional description: first-stage retrieval is cheap and approximate, so
it returns a wide top-K. A cross-encoder-style scorer then reads the
(query, document) pair together and assigns a relevance score; the top-N
survivors go into the prompt. The scorer here is an INJECTED CALLABLE —
never a real provider, never a bundled model. The module demonstrates the
pattern with a term-overlap scorer so the pipeline runs end to end offline.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

ORIGIN = "levi-revival/rerank"

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


# Plug-in scorer type: (query, doc_text) -> relevance score (higher = better).
Scorer = Callable[[str, str], float]


def term_overlap_scorer(query: str, doc: str) -> float:
    """Demonstration scorer: idf-weighted query-term overlap.

    Shared with the query as a pair, not scored independently — that is the
    cross-encoder idea at reference scale: the score is a function of the
    (query, document) pair. Rare query terms count more.
    """
    q_terms = _tokens(query)
    d_terms = set(_tokens(doc))
    if not q_terms or not d_terms:
        return 0.0
    # toy idf: treat the doc as its own corpus, weight by 1/(1+freq)
    from collections import Counter

    freq = Counter(_tokens(doc))
    score = 0.0
    for t in set(q_terms):
        if t in d_terms:
            score += q_terms.count(t) / (1.0 + math.log(1 + freq[t]))
    # exact-phrase bonus: the whole query appearing verbatim
    if query.lower().strip() and query.lower().strip() in doc.lower():
        score += 1.0
    return score / max(1, len(set(q_terms)))


@dataclass
class RerankedDoc:
    doc_id: int
    text: str
    first_stage_rank: int
    first_stage_score: float
    rerank_score: float


class CrossEncoderReranker:
    """Two-stage: keep top-K from stage one, re-score with the injected
    scorer, emit top-N. Also supports batch scoring for efficiency."""

    def __init__(self, scorer: Scorer = term_overlap_scorer) -> None:
        self.scorer = scorer

    def score_batch(self, query: str, docs: Sequence[str]) -> List[float]:
        return [self.scorer(query, d) for d in docs]

    def rerank(
        self, query: str, candidates: Sequence[Tuple[int, str, float]], top_n: int = 3
    ) -> List[RerankedDoc]:
        """candidates: (doc_id, text, first_stage_score), already rank-ordered."""
        scored: List[RerankedDoc] = []
        for rank, (doc_id, text, fs_score) in enumerate(candidates, start=1):
            scored.append(
                RerankedDoc(
                    doc_id=doc_id,
                    text=text,
                    first_stage_rank=rank,
                    first_stage_score=fs_score,
                    rerank_score=self.scorer(query, text),
                )
            )
        # stable: ties keep first-stage order
        scored.sort(key=lambda d: d.rerank_score, reverse=True)
        return scored[:top_n]

    def agreement(self, reranked: Sequence[RerankedDoc]) -> Dict[str, float]:
        """How much did reranking move things? Honest measurement, not hype."""
        if not reranked:
            return {"mean_rank_shift": 0.0, "kept_ratio": 0.0}
        shifts = [abs(d.first_stage_rank - (i + 1)) for i, d in enumerate(reranked)]
        return {
            "mean_rank_shift": sum(shifts) / len(shifts),
            "top1_changed": 1.0 if reranked[0].first_stage_rank != 1 else 0.0,
        }
