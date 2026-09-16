"""Adapter: agent-assistant user context ← memory retrieval.

Upgrade path for :func:`levi.agent.assistant.load_user_context`: instead of
listing the newest entries by type, this adapter runs the query through the
hybrid retriever (:func:`levi.memory.retrieval.retrieve`) so the context
block is *relevant* to the current query, not just recent.

Contract::

    load_user_context_retrieved(store, query, limit=8) ->
        {"block": str, "method": "hybrid" | "fallback", "entry_ids": [...],
         "note": str}

Degradation (honest, ordered):

1. Retrieval module importable and returns hits → ``method="hybrid"``.
2. Retrieval unavailable / raises / returns nothing → fall back to the
   existing :func:`levi.agent.assistant.load_user_context`
   (``method="fallback"``). The block still carries real memory content,
   just not query-ranked.
3. Both unavailable → ``block=""`` with a note saying exactly that.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _lazy_retrieve():
    from levi.memory.retrieval import retrieve

    return retrieve


def _fallback_block(store, limit: int) -> str:
    try:
        from levi.agent.assistant import load_user_context
    except Exception:
        return ""
    try:
        return load_user_context(store=store, limit=limit) or ""
    except Exception:
        return ""


def load_user_context_retrieved(
    store, query: str, limit: int = 8
) -> Dict[str, Any]:
    """Build a query-relevant "what I know about you" block.

    ``store`` is a :class:`~levi.memory.store.MemoryStore` (or duck-typed
    stand-in with ``.list()``). Never raises: failures degrade to the
    legacy loader, then to an empty block, each step labeled honestly.
    """
    entry_ids: List[str] = []
    # -- hybrid path --------------------------------------------------------
    try:
        retrieve = _lazy_retrieve()
        hits = retrieve(query, store, limit=limit, method="hybrid")
    except Exception:
        hits = None
    if hits:
        lines: List[str] = []
        for entry, _score, _why in hits:
            eid = getattr(entry, "id", "?")
            entry_ids.append(eid)
            content = (getattr(entry, "content", "") or "").strip()
            if content:
                lines.append("- %s" % content.replace("\n", " ")[:280])
        return {
            "block": "\n".join(lines),
            "method": "hybrid",
            "entry_ids": entry_ids,
            "note": "query-ranked via levi.memory.retrieval (hybrid)",
        }
    # -- fallback path: the legacy loader -----------------------------------
    block = _fallback_block(store, limit)
    note = "retrieval unavailable or returned no hits; legacy loader used"
    if not block:
        note = "retrieval unavailable and legacy loader produced nothing"
    return {
        "block": block,
        "method": "fallback",
        "entry_ids": [],
        "note": note,
    }
