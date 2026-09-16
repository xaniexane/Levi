"""RAG ask pipeline: retrieve → rerank → cite → generate.

``ask(query, store, ...)``:
1. Hybrid retrieval over the memory store (top-k, oversampled).
2. Cheap rerank: query term/bigram coverage + provenance trust.
3. Context block with ``[memory:<entry_id>]`` citations.
4. Generation via the agent runtime (LAZY import). If the runtime is
   unavailable, the retrieved context is returned with an honestly-labeled
   "no generator available" notice — an answer is never invented.
5. If nothing relevant is retrieved, say so plainly (the
   ``explain_belief`` discipline: treat as unsupported).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from levi.memory.retrieval import retrieve, tokenize


@dataclass
class AskResult:
    query: str
    answer: Optional[str] = None
    notice: str = ""  # honest status: generated / no-generator / no-results
    context: str = ""  # the cited context block handed to the generator
    citations: List[str] = field(default_factory=list)  # entry ids, rank order
    retrieved_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "notice": self.notice,
            "context": self.context,
            "citations": self.citations,
            "retrieved_ids": self.retrieved_ids,
        }


def _bigrams(terms: List[str]) -> List[str]:
    return ["%s %s" % (a, b) for a, b in zip(terms, terms[1:])]


def coverage_score(query: str, entry) -> Tuple[float, str]:
    """Query term/bigram coverage of the entry text, 0..1."""
    q_terms = tokenize(query)
    if not q_terms:
        return 0.0, "no query terms"
    text = ((entry.content or "") + " " + " ".join(entry.tags or "")).lower()
    hits = sum(1 for t in q_terms if t in text)
    term_cov = hits / len(q_terms)
    bigrams = _bigrams(q_terms)
    big_cov = (sum(1 for b in bigrams if b in text) / len(bigrams)) if bigrams else 0.0
    score = 0.7 * term_cov + 0.3 * big_cov
    return score, "term_cov=%.2f bigram_cov=%.2f" % (term_cov, big_cov)


def provenance_trust(entry, trusted_sources: Optional[Sequence[str]] = None) -> float:
    """Trust weight from provenance metadata.

    Entries ingested by this pipeline (``metadata["rag"]``) get full
    weight; entries from explicitly trusted sources get a small bonus;
    anything else gets a neutral weight. Nothing is silently discarded —
    trust only reorders.
    """
    meta = entry.metadata or {}
    prov = meta.get("provenance") or {}
    base = 1.0 if meta.get("rag") else 0.9
    if trusted_sources and prov.get("source_doc") in trusted_sources:
        base = min(base + 0.1, 1.2)
    return base


def rerank(
    query: str, scored: Sequence[Tuple], trusted_sources: Optional[Sequence[str]] = None
):
    """Rerank ``(entry, score, explanation)`` tuples.

    final = retrieval_score_normalized * (0.6 + 0.4*coverage) * trust.
    Returns ``[(entry, final, explanation)]`` best-first, deterministic.
    """
    if not scored:
        return []
    top = max(s for _e, s, _x in scored) or 1.0
    out = []
    for entry, score, expl in scored:
        cov, cov_expl = coverage_score(query, entry)
        trust = provenance_trust(entry, trusted_sources)
        final = (score / top) * (0.6 + 0.4 * cov) * trust
        out.append(
            (
                entry,
                final,
                "rerank final=%.4f | %s | trust=%.2f | base: %s"
                % (final, cov_expl, trust, expl),
            )
        )
    out.sort(key=lambda p: (-p[1], p[0].id))
    return out


def build_context(
    ranked: Sequence[Tuple], max_chars: int = 6000
) -> Tuple[str, List[str]]:
    """Build the cited context block; returns (block, citation_ids)."""
    lines: List[str] = []
    citations: List[str] = []
    total = 0
    for _, (entry, _score, _expl) in enumerate(ranked, 1):
        meta = entry.metadata or {}
        prov = meta.get("provenance") or {}
        section = prov.get("section") or ""
        src = prov.get("source_doc") or entry.source or "memory"
        header = "[memory:%s] (source: %s%s)" % (
            entry.id,
            src,
            (" § " + section) if section else "",
        )
        body = (entry.content or "").strip()
        block = "%s\n%s" % (header, body)
        if total + len(block) > max_chars and lines:
            break
        lines.append(block)
        citations.append(entry.id)
        total += len(block)
    return "\n\n---\n\n".join(lines), citations


# A hybrid hit counts as *relevant* when it has lexical evidence
# (bm25_rank present), strong vector evidence, or modest vector evidence
# with a clear margin over the runner-up (kills tiny-corpus noise where
# a lone chunk scores ~0.1-0.16 on pure n-gram chance).
# Calibrated: unrelated queries score ~0.05-0.16, real matches 0.15+.
_REL_RE = re.compile(r"bm25_rank=(\d+|None).*vec_sim=([0-9.]+)")
VECTOR_FLOOR = 0.12
VECTOR_STRONG_FLOOR = 0.25
VECTOR_MARGIN = 1.5


def _parse_rel_signals(explanation: str) -> Tuple[bool, float]:
    m = _REL_RE.search(explanation or "")
    if not m:
        return True, 0.0  # non-hybrid explanations: no signal to judge by
    try:
        sim = float(m.group(2))
    except ValueError:
        sim = 0.0
    return (m.group(1) != "None"), sim


def apply_relevance_gate(
    ranked,
    vector_floor: float = VECTOR_FLOOR,
    strong_floor: float = VECTOR_STRONG_FLOOR,
    margin: float = VECTOR_MARGIN,
):
    """Drop fused hits with no real evidence. Deterministic.

    Keep a hit when it has lexical evidence, strong vector similarity,
    or modest similarity with a clear margin over the runner-up.
    """
    parsed = []
    for entry, score, expl in ranked:
        lexical, sim = _parse_rel_signals(expl)
        parsed.append((entry, score, expl, lexical, sim))
    sims = sorted((p[4] for p in parsed), reverse=True)
    runner_up = sims[1] if len(sims) > 1 else 0.0
    out = []
    for entry, score, expl, lexical, sim in parsed:
        if lexical or sim >= strong_floor:
            out.append((entry, score, expl))
        elif sim >= vector_floor and runner_up > 0 and sim >= margin * runner_up:
            out.append((entry, score, expl))
        # else: no real evidence — dropped (ask reports "nothing relevant")
    return out


def _generate(
    query: str, context: str, system_prompt: Optional[str] = None
) -> Optional[str]:
    """Lazy call into the agent runtime. Returns None when unavailable."""
    try:
        from levi.agent.loop import run_subtask
    except Exception:
        return None
    prompt = (
        "Answer the user's question using ONLY the context below. "
        "Cite sources as [memory:<id>]. If the context does not contain "
        "the answer, say so plainly and do not invent one.\n\n"
        "CONTEXT:\n%s\n\nQUESTION: %s" % (context, query)
    )
    try:
        transcript = run_subtask(
            prompt,
            provider=None,
            system_prompt=system_prompt or "You are LEVI's RAG reader.",
            max_steps=4,
        )
    except Exception:
        return None
    final = (getattr(transcript, "final", "") or "").strip()
    return final or None


def ask(
    query: str,
    store,
    limit: int = 5,
    trusted_sources: Optional[Sequence[str]] = None,
    generate: bool = True,
    system_prompt: Optional[str] = None,
    vector_floor: float = VECTOR_FLOOR,
) -> AskResult:
    """Run the RAG pipeline. Never invents an answer; never raises."""
    result = AskResult(query=query if isinstance(query, str) else "")
    try:
        if not isinstance(query, str) or not query.strip():
            result.notice = "blank query — nothing to retrieve"
            return result
        retrieved = retrieve(query, store, limit=max(limit * 2, 10), method="hybrid")
        # Relevance gate: drop fused hits with neither lexical evidence
        # nor sufficient vector similarity (kills tiny-corpus noise).
        retrieved = apply_relevance_gate(retrieved, vector_floor)
        result.retrieved_ids = [e.id for e, _s, _x in retrieved]
        if not retrieved:
            result.notice = (
                "nothing relevant retrieved — treat as unsupported; no answer generated"
            )
            return result
        ranked = rerank(query, retrieved, trusted_sources)[: max(limit, 1)]
        context, citations = build_context(ranked)
        result.context = context
        result.citations = citations
        if not generate:
            result.notice = "retrieval only (generate=False)"
            return result
        answer = _generate(query, context, system_prompt)
        if answer is None:
            result.notice = (
                "no generator available (agent runtime unreachable) — "
                "returning retrieved context only, no answer invented"
            )
            return result
        result.answer = answer
        result.notice = "answer generated from retrieved context"
        return result
    except Exception as exc:
        result.notice = "pipeline error (fail-closed): %s: %s" % (
            type(exc).__name__,
            exc,
        )
        return result
