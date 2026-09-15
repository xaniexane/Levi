"""User context loading and learning write-back for the LEVI bot.

Two jobs, both fail-soft:

1. **Context loading (read-only).** At session start the bot pulls
   user-relevant entries (preferences, facts) from the existing
   :class:`levi.memory.store.MemoryStore` and renders them as a compact
   "what I know about you" block for the system prompt — the way a personal
   assistant carries user knowledge between turns. Empty or unavailable
   store → empty string, never an error.

2. **Learning write-back (queue, not consolidate).** After substantive
   turns the bot extracts *candidate* durable facts/preferences with simple
   heuristics (documented below — no fake NLP claims) and appends them to
   ``~/.levi/bot/pending_learnings.jsonl``. It then flags the queue in the
   growth journal via :func:`levi.growth.journal.append_entry` so the
   existing growth loop can see it. The bot never duplicates
   growth/consolidation logic; consolidation stays the growth loop's job.

Handoff format (one JSON object per line in ``pending_learnings.jsonl``)::

    {"ts": "...", "kind": "preference|fact", "text": "...",
     "confidence": "heuristic", "source": "levi-bot", "status": "pending"}

``core/levi/memory/*`` is never modified here — only read.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from levi.bot.persona import render_system_prompt


def _state_dir() -> str:
    override = os.environ.get("LEVI_BOT_HOME")
    if override:
        return os.path.join(override, "bot")
    return os.path.join(os.path.expanduser("~"), ".levi", "bot")


def _pending_path() -> str:
    return os.path.join(_state_dir(), "pending_learnings.jsonl")


# ---------------------------------------------------------------------------
# 1. Context loading (read-only on MemoryStore)
# ---------------------------------------------------------------------------

_CONTEXT_LIMIT = 15


def load_user_context(limit: int = _CONTEXT_LIMIT) -> str:
    """Render a compact "what I know about you" block from memory.

    Preferences first, then other high-importance entries. Returns ``""``
    when the store is empty or unavailable. Read-only; never raises.
    """
    try:
        from levi.memory.store import MemoryStore
        from levi.memory.types import MemoryType
    except Exception:
        return ""
    try:
        store = MemoryStore()
        prefs = store.list(memory_type=MemoryType.PREFERENCE, limit=limit)
        rest = store.list(limit=limit)
    except Exception:
        return ""
    seen = set()
    lines: List[str] = []
    for entry in list(prefs) + list(rest):
        if entry.id in seen:
            continue
        seen.add(entry.id)
        text = (entry.content or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append("- [%s] %s" % (entry.memory_type.value, text[:160]))
        if len(lines) >= limit:
            break
    if not lines:
        return ""
    return (
        "What I know about you (from memory — correct me if I'm wrong):\n"
        + "\n".join(lines)
    )


def build_system_prompt() -> str:
    """Full system prompt: spark voice + assistant core + user context."""
    base = render_system_prompt()
    context = load_user_context()
    if context:
        return base + "\n\n" + context
    return base


# ---------------------------------------------------------------------------
# 2. Learning write-back (heuristic candidates → pending queue)
# ---------------------------------------------------------------------------

# Heuristic patterns for candidate durable facts/preferences. These are
# deliberately narrow and labeled "heuristic" — the growth loop's
# consolidation decides what actually becomes a memory.
_CANDIDATE_PATTERNS: List[tuple] = [
    (re.compile(r"\bremember that (.+?)(?:\.|$)", re.I), "fact"),
    (re.compile(r"\bcall me ([\w\- ]{1,30})", re.I), "preference"),
    (
        re.compile(
            r"\bi (prefer|like|love|hate|dislike|can't stand) ([^.?!]{2,120})", re.I
        ),
        "preference",
    ),
    (
        re.compile(
            r"\bmy (name|birthday|timezone|editor|shell|phone|email) is ([^.?!]{1,80})",
            re.I,
        ),
        "fact",
    ),
]


def extract_candidates(user_text: str) -> List[Dict[str, str]]:
    """Extract candidate durable facts/preferences (heuristic, labeled).

    Returns a list of ``{"kind", "text", "confidence", "source"}`` dicts.
    Empty list when nothing matches. Never raises.
    """
    if not isinstance(user_text, str) or not user_text.strip():
        return []
    candidates: List[Dict[str, str]] = []
    for pattern, kind in _CANDIDATE_PATTERNS:
        try:
            match = pattern.search(user_text)
        except Exception:
            continue
        if not match:
            continue
        groups = [g for g in match.groups() if g]
        text = " ".join(g.strip() for g in groups)
        text = re.sub(r"\s+", " ", text).strip(" .")
        if len(text) < 3 or len(text) > 200:
            continue
        # Deduplicate identical candidates.
        if any(c["text"].lower() == text.lower() for c in candidates):
            continue
        candidates.append(
            {
                "kind": kind,
                "text": text,
                "confidence": "heuristic",
                "source": "levi-bot",
            }
        )
    return candidates


def queue_learnings(candidates: List[Dict[str, str]]) -> int:
    """Append candidates to the pending-learnings queue.

    Also flags the queue in the growth journal (fail-soft) so the existing
    growth loop can discover it. Returns the number queued. Never raises.
    """
    if not candidates:
        return 0
    try:
        path = _pending_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with open(path, "a", encoding="utf-8") as fh:
            for cand in candidates:
                record = {
                    "ts": ts,
                    "kind": cand.get("kind", "fact"),
                    "text": cand.get("text", ""),
                    "confidence": cand.get("confidence", "heuristic"),
                    "source": cand.get("source", "levi-bot"),
                    "status": "pending",
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return 0
    # Flag it for the growth loop via its own journal hook (best-effort).
    try:
        from levi.growth.journal import append_entry

        append_entry(
            {
                "kind": "bot-learnings",
                "pending_file": path,
                "count": len(candidates),
                "note": (
                    "levi-bot queued heuristic learning candidates; "
                    "consolidation is the growth loop's job"
                ),
            }
        )
    except Exception:
        pass
    return len(candidates)


def maybe_learn(user_text: str) -> int:
    """Extract + queue learning candidates from one user turn.

    Best-effort wrapper for the chat loop: never raises, never blocks.
    Returns the number of candidates queued.
    """
    try:
        return queue_learnings(extract_candidates(user_text))
    except Exception:
        return 0


def read_pending(limit: int = 50) -> List[Dict[str, object]]:
    """Read pending learning candidates (newest last). Tolerates corruption."""
    path = _pending_path()
    if not os.path.exists(path):
        return []
    records: List[Dict[str, object]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    except OSError:
        return []
    return records[-limit:]


def pending_count() -> int:
    """Number of queued (pending-status) learning candidates."""
    return sum(1 for r in read_pending(10000) if r.get("status") == "pending")
