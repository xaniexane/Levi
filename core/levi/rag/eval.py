"""Retrieval eval harness: makes "good memory" a number.

Builds templated questions from ingested RAG chunks and measures
recall@k / hit-rate@k of :func:`levi.memory.retrieval.retrieve`.

A question is *answerable by* the chunk it was built from; a hit means
that chunk appears in the top-k results. This is a retrieval check, not
a generation check — it tells you whether the ranker finds the right
evidence, which is where "bad memory" usually lives (bad chunking, weak
ranking, or missing expansion).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from levi.memory.retrieval import retrieve, tokenize


@dataclass
class EvalQuestion:
    question: str
    expected_id: str      # chunk entry that answers it
    source_doc: str = ""


@dataclass
class EvalRow:
    question: str
    expected_id: str
    hit: bool
    rank: Optional[int]   # 1-based rank of expected chunk, None on miss
    top_ids: List[str] = field(default_factory=list)


def _keywords(section: str) -> List[str]:
    terms = [t for t in tokenize(section) if len(t) > 3]
    # longest-first: most distinctive keywords first
    return sorted(set(terms), key=lambda t: (-len(t), t))


def build_questions(store, per_chunk: int = 1,
                    max_questions: int = 50) -> List[EvalQuestion]:
    """Templated questions from ingested RAG chunks.

    For each chunk with a section header: "What does the document say
    about <keyword>?" using the most distinctive keywords. For chunks
    without headers, fall back to a distinctive content keyword.
    """
    entries = [e for e in (store.list(limit=100000) or [])
               if (e.metadata or {}).get("rag")]
    questions: List[EvalQuestion] = []
    for entry in sorted(entries, key=lambda e: e.id):
        prov = (entry.metadata or {}).get("provenance") or {}
        section = prov.get("section") or ""
        kws = _keywords(section)
        if not kws:
            # fall back: distinctive content terms (long, non-stopword)
            content_terms = sorted(set(t for t in tokenize(entry.content or "")
                                       if len(t) > 5),
                                   key=lambda t: (-len(t), t))
            kws = content_terms[:3]
        for kw in kws[:per_chunk]:
            questions.append(EvalQuestion(
                question="What does the document say about %s?" % kw,
                expected_id=entry.id,
                source_doc=prov.get("source_doc", ""),
            ))
            if len(questions) >= max_questions:
                return questions
    return questions


def evaluate(store, k: int = 5, per_chunk: int = 1,
             max_questions: int = 50,
             method: str = "hybrid") -> Dict:
    """Run the harness. Returns a report dict; also see print_report()."""
    questions = build_questions(store, per_chunk=per_chunk,
                                max_questions=max_questions)
    rows: List[EvalRow] = []
    for q in questions:
        hits = retrieve(q.question, store, limit=k, method=method)
        ids = [e.id for e, _s, _x in hits]
        rank = ids.index(q.expected_id) + 1 if q.expected_id in ids else None
        rows.append(EvalRow(question=q.question, expected_id=q.expected_id,
                            hit=rank is not None, rank=rank, top_ids=ids))
    total = len(rows)
    hits_n = sum(1 for r in rows if r.hit)
    return {
        "k": k,
        "method": method,
        "total": total,
        "hits": hits_n,
        "hit_rate": (hits_n / total) if total else 0.0,
        # recall@k == hit-rate@k here (one relevant chunk per question)
        "recall_at_k": (hits_n / total) if total else 0.0,
        "mean_rank": (sum(r.rank for r in rows if r.rank) / hits_n)
                     if hits_n else None,
        "rows": [r.__dict__ for r in rows],
    }


def print_report(report: Dict) -> str:
    """Render the eval report as a text table."""
    lines = [
        "=== LEVI retrieval eval ===",
        "method=%s k=%d questions=%d" % (report["method"], report["k"],
                                         report["total"]),
        "hit-rate@%d: %.1f%% (%d/%d)" % (report["k"],
                                         100 * report["hit_rate"],
                                         report["hits"], report["total"]),
        "recall@%d:   %.1f%%" % (report["k"], 100 * report["recall_at_k"]),
    ]
    mr = report.get("mean_rank")
    lines.append("mean rank of hits: %s" % ("%.2f" % mr if mr else "n/a"))
    lines.append("")
    lines.append("%-5s %-4s %s" % ("HIT", "RANK", "QUESTION"))
    for row in report["rows"]:
        lines.append("%-5s %-4s %s" % (
            "yes" if row["hit"] else "no",
            row["rank"] if row["rank"] else "-",
            row["question"][:70]))
    return "\n".join(lines)
