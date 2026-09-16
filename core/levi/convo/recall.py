"""Semantic recall over the conversation's own history.

The signature move of thread-sense: when the current turn arrives, LEVI asks
its own memory — not "what were the last N turns" but "which earlier turns
are *relevant to this one*?" A 200-turn conversation where turn 184 matters
right now surfaces turn 184.

Built on ``levi.memory.retrieval`` (BM25 + sparse-vector hybrid). Turns
become lightweight memory entries so the existing ranker is reused, not
reimplemented. If the retrieval module is unavailable, a documented
keyword-overlap fallback keeps recall working.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

_FALLBACK_NOTE = "fallback: keyword overlap (levi.memory.retrieval unavailable)"


def _fallback_recall(
    query: str, turns: List[Dict], limit: int, exclude_last: int
) -> List[Tuple[int, float, str]]:
    import re

    qwords = set(re.findall(r"[a-z]{3,}", query.lower()))
    scored = []
    for i, t in enumerate(turns[: max(0, len(turns) - exclude_last)]):
        twords = set(re.findall(r"[a-z]{3,}", t["text"].lower()))
        overlap = len(qwords & twords)
        if overlap:
            scored.append((i, float(overlap), _FALLBACK_NOTE))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def recall_turns(
    query: str,
    turns: List[Dict],
    limit: int = 3,
    exclude_last: int = 2,
) -> List[Tuple[int, float, str]]:
    """Return ``[(turn_index, score, explanation)]`` for earlier turns.

    *turns* is a list of ``{"speaker": str, "text": str}``. The most recent
    ``exclude_last`` turns are skipped — they are in-context already.
    Deterministic.
    """
    if not query or not query.strip() or not turns:
        return []
    if not isinstance(limit, int) or limit < 1:
        return []
    cutoff = max(0, len(turns) - exclude_last)
    if cutoff <= 0:
        return []

    try:
        from levi.memory.retrieval import retrieve  # type: ignore
        from levi.memory.types import MemoryType, new_entry  # type: ignore
    except Exception:
        return _fallback_recall(query, turns, limit, exclude_last)

    entries = []
    for i in range(cutoff):
        t = turns[i]
        entries.append(
            new_entry(
                memory_type=MemoryType.WORKING,
                content="%s: %s" % (t.get("speaker", "?"), t.get("text", "")),
                importance=0.5,
                source="convo-recall",
                tags=[],
                metadata={"turn": i},
            )
        )

    class _TurnStore:
        def __init__(self, ents):
            self._ents = ents

        def list(self, limit=None):  # signature-compatible with MemoryStore
            return self._ents if limit is None else self._ents[:limit]

    try:
        results = retrieve(query, _TurnStore(entries), limit=limit, method="hybrid")
    except Exception:
        return _fallback_recall(query, turns, limit, exclude_last)

    out = []
    for entry, score, explanation in results:
        idx = (entry.metadata or {}).get("turn")
        if isinstance(idx, int):
            out.append((idx, round(float(score), 4), explanation))
    return out
