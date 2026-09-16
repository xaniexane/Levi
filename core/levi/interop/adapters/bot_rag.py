"""Adapter: bot ``research-brief`` service ← rag pipeline.

Runs :func:`levi.rag.pipeline.ask` over the memory store and shapes the
result into the dict shape the bot's ``research-brief`` service returns —
without editing :mod:`levi.bot.services` (see ``docs/INTEROP_FOLLOWUPS.md``
for the adoption patch).

Contract::

    research_brief_rag(topic, store) ->
        {"ok": bool, "report": str, "citations": [...],
         "notice": str, "method": "rag"}

Degradation: when the RAG pipeline is unavailable (ImportError) or raises,
``ok`` is ``False`` and the report says so explicitly — a failed research
step is reported, never papered over with invented content.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _lazy_ask():
    from levi.rag.pipeline import ask

    return ask


def research_brief_rag(topic: str, store) -> Dict[str, Any]:
    """Produce a ``research-brief``-shaped dict from the RAG pipeline.

    ``store`` is a memory store (or duck-typed stand-in with ``.list()``).
    Never invents an answer; when nothing can be retrieved or generated the
    pipeline's own honest notice becomes the report.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "report": "",
        "citations": [],
        "notice": "",
        "method": "rag",
    }
    if not isinstance(topic, str) or not topic.strip():
        result["notice"] = "blank topic — nothing to research"
        result["report"] = "RESEARCH BRIEF: refused — no topic given."
        return result
    topic = topic.strip()
    try:
        ask = _lazy_ask()
    except Exception as exc:
        result["notice"] = "rag-unavailable"
        result["report"] = (
            "RESEARCH BRIEF: RAG pipeline unavailable (%s: %s). "
            "The cited-research path cannot run; the legacy agent-runtime "
            "brief remains the fallback."
            % (type(exc).__name__, exc)
        )
        return result
    try:
        asked = ask(topic, store, limit=5, generate=False)
    except Exception as exc:  # ask() is fail-closed, but belt and braces
        result["notice"] = "rag-error"
        result["report"] = (
            "RESEARCH BRIEF failed: RAG pipeline raised %s: %s"
            % (type(exc).__name__, exc)
        )
        return result
    citations: List[str] = list(getattr(asked, "citations", []) or [])
    notice = getattr(asked, "notice", "") or ""
    context = getattr(asked, "context", "") or ""
    result["citations"] = citations
    result["notice"] = notice
    if not citations:
        result["ok"] = False
        result["report"] = (
            "RESEARCH BRIEF on '%s': %s" % (topic, notice or "no results")
        )
        return result
    body = context.strip()
    result["ok"] = True
    result["report"] = (
        "RESEARCH BRIEF on '%s' (cited, from local memory/knowledge):\n\n%s\n\n"
        "Citations: %s\nStatus: %s"
        % (topic, body, ", ".join("[memory:%s]" % c for c in citations), notice)
    )
    return result
