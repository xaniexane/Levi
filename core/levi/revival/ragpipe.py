"""RAG staged pipeline + structure-aware chunking/parent-document retrieval.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.6)

Functional description: a retrieval-augmented generation pipeline as five
separately measurable stages — routing, query rewriting, retrieval,
reranking, generation. Every stage records wall-clock timing and an eval
hook; a stage failure is returned in the result envelope as an error, never
swallowed or silently skipped. Documents are split by recursive,
structure-aware chunking that breaks on natural boundaries (blank-line
paragraphs, headings, sentence ends) instead of blind character cuts, and
each small chunk remembers its parent document so the generator can be fed
the wider parent context while retrieval ranks the small units.

Every part is pure Python from scratch. No provider branding, no network,
no LLaMA. Not artificial — synthetic.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ORIGIN = "levi-revival/ragpipe"

# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
HEADING = re.compile(r"^\s*(#{1,6}\s+|[A-Z][A-Z0-9 \-]{3,}:?$|\d+\.\s+)")


@dataclass
class Chunk:
    """A small retrievable unit that points back at its parent document."""

    text: str
    doc_id: str
    chunk_id: int
    parent_id: str
    boundary: str  # how the splitter cut it: paragraph/sentence/forced


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_sentences(paragraph: str) -> List[str]:
    parts = [s.strip() for s in SENTENCE_END.split(paragraph) if s.strip()]
    return parts or [paragraph.strip()]


def chunk_document(
    text: str,
    doc_id: str,
    max_chars: int = 500,
    overlap_chars: int = 0,
) -> Tuple[List[Chunk], "Document"]:
    """Recursive structure-aware chunking.

    Split on blank lines (paragraphs), then on sentence ends, and only as a
    last resort on a hard character boundary. ``max_chars`` is a soft budget:
    we prefer to stop at a sentence end under the budget than to cut mid
    sentence to fill it exactly.
    """
    chunks: List[Chunk] = []
    for para in _split_paragraphs(text):
        budget = max_chars - overlap_chars
        sentences = _split_sentences(para)
        current: List[str] = []
        current_len = 0
        for sent in sentences:
            if current and current_len + len(sent) + 1 > max_chars:
                chunks.append(" ".join(current))
                current, current_len = [sent], len(sent)
            else:
                current.append(sent)
                current_len += len(sent) + 1
        if current:
            chunks.append(" ".join(current))
    # forced cut only when one sentence alone exceeds the budget
    result: List[Chunk] = []
    for c in chunks:
        if len(c) <= max_chars:
            result.append(
                Chunk(
                    text=c,
                    doc_id=doc_id,
                    chunk_id=len(result),
                    parent_id=doc_id,
                    boundary="sentence",
                )
            )
        else:
            # natural boundaries exhausted: blind cut, honestly labeled
            for j in range(0, len(c), budget):
                piece = c[j : j + budget]
                if piece.strip():
                    result.append(
                        Chunk(
                            text=piece.strip(),
                            doc_id=doc_id,
                            chunk_id=len(result),
                            parent_id=doc_id,
                            boundary="forced",
                        )
                    )
    # re-number sequentially
    for i, ch in enumerate(result):
        ch.chunk_id = i
    doc = Document(doc_id=doc_id, text=text, chunks=result)
    return result, doc


@dataclass
class Document:
    """Parent document: holds the full text; chunks point at it."""

    doc_id: str
    text: str
    chunks: List[Chunk] = field(default_factory=list)

    def context_window(self, chunk: Chunk, radius: int = 1) -> str:
        """Parent-context expansion: the chunk plus neighboring chunks."""
        idx = chunk.chunk_id
        lo = max(0, idx - radius)
        hi = min(len(self.chunks), idx + radius + 1)
        return "\n".join(c.text for c in self.chunks[lo:hi])


# --------------------------------------------------------------------------
# Staged pipeline
# --------------------------------------------------------------------------


@dataclass
class StageReport:
    stage: str
    seconds: float
    ok: bool
    detail: str = ""
    error: str = ""
    eval: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    answer: str
    stages: List[StageReport]
    retrieved: List[Chunk]
    reranked: List[Chunk]
    context: str

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.stages)

    def timing(self) -> Dict[str, float]:
        return {s.stage: s.seconds for s in self.stages}


class StageFailure(Exception):
    """Raised by a stage body; the pipeline converts it to a StageReport."""


class RAGPipeline:
    """Five measurable stages: route → rewrite → retrieve → rerank → generate."""

    def __init__(
        self,
        retrieve: Callable[[str], List[Chunk]],
        rerank: Optional[Callable[[str, List[Chunk]], List[Chunk]]] = None,
        generate: Optional[Callable[[str, str], str]] = None,
        rewrite: Optional[Callable[[str], str]] = None,
        route: Optional[Callable[[str], str]] = None,
        eval_hooks: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None,
        top_k: int = 8,
        top_n: int = 3,
    ) -> None:
        self.retrieve = retrieve
        self.rerank = rerank or (lambda q, cs: cs)
        self.generate = generate or (lambda q, ctx: ctx[:800])
        self.rewrite = rewrite or (lambda q: q)
        self.route = route or (lambda q: "default")
        self.eval_hooks = eval_hooks or {}
        self.top_k = top_k
        self.top_n = top_n

    def _run_stage(self, name: str, body: Callable[[], Any]) -> Tuple[Any, StageReport]:
        t0 = time.perf_counter()
        try:
            value = body()
        except Exception as exc:  # stage failure is reported, not hidden
            rep = StageReport(
                stage=name,
                seconds=time.perf_counter() - t0,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None, rep
        rep = StageReport(stage=name, seconds=time.perf_counter() - t0, ok=True)
        hook = self.eval_hooks.get(name)
        if hook is not None:
            try:
                rep.eval = dict(hook(value) or {})
            except Exception as exc:
                rep.eval = {"hook_error": f"{type(exc).__name__}: {exc}"}
        return value, rep

    def run(self, query: str, docs: Sequence[Document]) -> PipelineResult:
        stages: List[StageReport] = []

        route, rep = self._run_stage("routing", lambda: self.route(query))
        stages.append(rep)

        rewritten, rep = self._run_stage("rewriting", lambda: self.rewrite(query))
        stages.append(rep)
        q = rewritten if rewritten is not None else query

        hits, rep = self._run_stage(
            "retrieval", lambda: list(self.retrieve(q))[: self.top_k]
        )
        stages.append(rep)
        hits = hits or []

        ranked, rep = self._run_stage(
            "reranking", lambda: list(self.rerank(q, hits))[: self.top_n]
        )
        stages.append(rep)
        ranked = ranked or []

        by_doc = {d.doc_id: d for d in docs}
        context = (
            "\n---\n".join(
                by_doc[c.doc_id].context_window(c) for c in ranked if c.doc_id in by_doc
            )
            if ranked
            else ""
        )

        answer, rep = self._run_stage("generation", lambda: self.generate(q, context))
        stages.append(rep)

        return PipelineResult(
            answer=answer if answer is not None else "",
            stages=stages,
            retrieved=hits,
            reranked=ranked,
            context=context,
        )
