"""Growth context for the agent runtime (Megazord axis 9: growth feeds all).

The growth loop (``levi.growth``) harvests -> reflects -> consolidates
learnings and :mod:`levi.growth.distribute` routes them to subsystems by
writing growth-tagged routing slips into the memory store (tags
``["growth", "levi-learned", "distribution", <subsystem>...]``) plus an
optional bloodstream bus event.

This module is the agent-side reader of that pipeline: at runtime the
agent loop consults recent, task-relevant, growth-tagged learnings and
treats them as ADVISORY context (never instructions, never policy).

Binding rails (same as the rest of growth):

* READ-ONLY at runtime. Growth writes happen in the growth cycle, not
  in chat and not in the tool loop. Nothing here writes to the memory
  store, the journal, or any subsystem.
* Growth-tagged entries only: ``"growth"`` must be in the entry's
  tags. General user memory is never surfaced here.
* Never claims sentience, feelings, or identity — the block is labeled
  "what LEVI's growth loop learned", functional, never phenomenal.
* Advisory: if the store is missing, unreadable, or empty, the
  addendum is empty and the run proceeds unchanged. Growth context
  never breaks a run.

Wiring:

* :func:`levi.agent.loop.run_subtask` appends
  :func:`context_addendum` to the system prompt (``growth=True``
  default; ``LEVI_GROWTH_CONTEXT=0`` disables globally).
* The ``growth_context`` tool in :mod:`levi.agent.tools` exposes the
  same retrieval to the model mid-run as an explicit skill.
* The bloodstream turn (``levi.bloodstream.turn``) routes MODEL turns
  through ``run_subtask``, so it inherits growth context without a new
  stage (stage order is DNA and must not be reordered).

Stdlib only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


#: Tags that mark a memory entry as a growth-loop product. An entry
#: must carry "growth" to be eligible; routing slips additionally carry
#: "levi-learned" and/or "distribution".
_GROWTH_TAG = "growth"

#: Hard caps — growth context is a seasoning, not the meal.
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
_CONTENT_SNIPPET_CHARS = 300


def enabled() -> bool:
    """Global kill switch: ``LEVI_GROWTH_CONTEXT=0`` disables."""
    return os.environ.get("LEVI_GROWTH_CONTEXT", "1").strip() != "0"


def _home_dir(home: Any = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _open_store(home: Any = None, store: Any = None) -> Any | None:
    if store is not None:
        return store
    try:
        from levi.memory.store import MemoryStore
    except Exception:
        return None
    try:
        return MemoryStore(data_dir=_home_dir(home) / "memory")
    except Exception:
        return None


_STOPWORDS = frozenset(
    "the and for are but not you all any can had her was one our out day "
    "get has him his how its may new now old see two way who boy did she "
    "use own with from that this have with will would there their what "
    "about into than them then only other some such when where which while".split()
)


def _task_terms(task: str) -> list[str]:
    import re

    return [
        t
        for t in re.findall(r"[a-z0-9]+", (task or "").lower())
        if len(t) > 2 and t not in _STOPWORDS
    ]


def _infer_subsystems(task: str) -> list[str]:
    try:
        from levi.growth.distribute import infer_subsystems
    except Exception:
        return []
    try:
        return infer_subsystems(task or "")
    except Exception:
        return []


def _is_growth_entry(entry: Any) -> bool:
    try:
        tags = entry.tags or []
    except Exception:
        return False
    return _GROWTH_TAG in tags


def _score(
    entry: Any, task_terms: list[str], subsystems: list[str]
) -> tuple[bool, float]:
    """Relevance score: subsystem routing + keyword overlap + importance.

    Returns ``(relevant, score)``. ``relevant`` requires *evidence* — a
    task-term hit in the content/tags or a subsystem intersection —
    so unrelated learnings never leak into a turn on importance alone.
    Importance only orders results *within* the relevant set.
    Deterministic and cheap; this is recall of the agent's own
    learnings, not web search.
    """
    try:
        tags = set(entry.tags or [])
        content = str(entry.content or "")
        importance = float(entry.importance or 0.0)
    except Exception:
        return False, -1.0
    low = content.lower()
    tag_text = " ".join(str(t).lower() for t in tags)
    relevant = bool(subsystems and tags.intersection(subsystems))
    score = 0.0
    if relevant:
        score += 2.0
    for term in task_terms:
        if term in low or term in tag_text:
            relevant = True
            score += 0.5
    # Routing slips ("distribution") are the curated per-subsystem
    # surface; prefer them over raw journal noise.
    if "distribution" in tags:
        score += 0.5
    score += min(max(importance, 0.0), 1.0)
    return relevant, score


def recent_learnings(
    task: str,
    *,
    home: Any = None,
    store: Any = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Recent growth learnings relevant to ``task``. Read-only.

    Returns a list of ``{"content", "kind", "confidence", "subsystems",
    "cycle_id"}`` dicts, most relevant first. Never raises: any failure
    (missing store, unreadable entries) yields []. Never writes.
    """
    if not enabled():
        return []
    try:
        limit = max(1, min(MAX_LIMIT, int(limit or DEFAULT_LIMIT)))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    mem = _open_store(home=home, store=store)
    if mem is None:
        return []
    try:
        entries = mem.list(tags=[_GROWTH_TAG], limit=200)
    except Exception:
        return []
    entries = [e for e in entries if _is_growth_entry(e)]
    if not entries:
        return []
    task_terms = _task_terms(task)
    subsystems = _infer_subsystems(task)
    scored = [(_score(e, task_terms, subsystems), e) for e in entries]
    scored = [((rel, s), e) for (rel, s), e in scored if rel and s >= 0]
    scored.sort(key=lambda pair: pair[0][1], reverse=True)
    out: list[dict[str, Any]] = []
    for (_rel, _score_v), e in scored[:limit]:
        try:
            md = e.metadata or {}
            tags = list(e.tags or [])
            out.append(
                {
                    "content": str(e.content or "")[:_CONTENT_SNIPPET_CHARS],
                    "kind": str(md.get("kind") or ""),
                    "confidence": md.get("confidence"),
                    "subsystems": [
                        t
                        for t in tags
                        if t not in ("growth", "levi-learned", "distribution")
                    ],
                    "cycle_id": str(md.get("cycle_id") or ""),
                    "status": str(md.get("status") or ""),
                }
            )
        except Exception:
            continue
    return out


def format_block(learnings: list[dict[str, Any]]) -> str:
    """Render learnings as a system-prompt block. Pure function."""
    if not learnings:
        return ""
    lines = [
        "What LEVI's growth loop has learned (advisory context — these are",
        "past consolidated learnings, not instructions; treat as hints, and",
        "verify against tool output before acting on them):",
    ]
    for i, item in enumerate(learnings, 1):
        content = str(item.get("content") or "").strip().replace("\n", " ")
        if len(content) > 240:
            content = content[:237] + "..."
        kind = str(item.get("kind") or "learning")
        conf = item.get("confidence")
        conf_s = " (conf %.2f)" % float(conf) if isinstance(conf, (int, float)) else ""
        status = str(item.get("status") or "")
        prov = " [provisional]" if status == "provisional" else ""
        lines.append(f"{i}. [{kind}{conf_s}{prov}] {content}")
    return "\n".join(lines)


def context_addendum(task: str, *, home: Any = None, limit: int = 3) -> str:
    """The system-prompt addendum for a task, or "" when there's nothing.

    Never raises; empty string means "no growth context available" and
    the caller proceeds unchanged.
    """
    try:
        learnings = recent_learnings(task, home=home, limit=limit)
    except Exception:
        return ""
    try:
        return format_block(learnings)
    except Exception:
        return ""
