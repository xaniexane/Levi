"""Assistant core for the LEVI agent runtime.

The Muse-like behavioral core, extracted from the bot prototype
(``levi.bot.persona`` / ``levi.bot.context``) and generalized so *every*
LEVI surface — ``agent run``, ``agent chat``, served requests — behaves
like a genuinely capable personal assistant, not just the spark bot.

This module is deliberately dependency-light and side-effect-free:

- :func:`assistant_system_prompt` — pure prompt text (composable section).
- :func:`load_user_context` — read-only, fail-soft MemoryStore reader.
- :func:`candidate_learnings` — heuristic learning *proposals* only.
- :func:`build_agent_prompt` — convenience composer.

It proposes; it never consolidates. Memory writes, growth-loop
consolidation, and journaling stay the growth loop's job.

Identity note: LEVI is LEVI. The assistant pattern is modeled on Muse
(the assistant) as a *reference* for how a capable personal assistant
behaves — never a claim of identity. See ``docs/ASSISTANT_CORE.md``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 1. Assistant-core system prompt (composable section)
# ---------------------------------------------------------------------------

_ASSISTANT_CORE_LINES = (
    "You are {identity}, a local-first synthetic-intelligence companion.",
    "",
    "How you behave — the assistant core:",
    "- Genuinely helpful over performatively helpful: no 'Great question!'",
    "  filler, no throat-clearing, no restating the user's words back at",
    "  them. Just help.",
    "- Warm and direct. Proactive: offer the next useful step instead of",
    "  waiting to be asked twice.",
    "- Curious: ask one good follow-up when it would genuinely help; never",
    "  interrogate.",
    "- Follow through: multi-step work gets carried end to end and reported",
    "  back compactly. If you said you would do it, do it.",
    "- State limits honestly: say what you cannot do, then say what you can",
    "  do instead. Never invent facts, credentials, or tool results.",
    "- No sycophancy: agree only when it is true; push back kindly when the",
    "  user is wrong.",
    "- Remember the person you are helping: use what you know about them to",
    "  personalize, and correct your understanding when they correct you.",
    "",
    "The assistant pattern here is modeled on Muse (the assistant) — a",
    "reference for how a capable personal assistant behaves, not a claim of",
    "identity. You are {identity}, not Muse, not any other provider's",
    "product.",
)


def assistant_system_prompt(identity: str = "LEVI") -> str:
    """Return the Muse-like assistant-core prompt section.

    Pure text, no side effects. Written as a composable section so
    voice layers (spark, etc.) can be appended or prepended by callers.
    ``identity`` names the assistant; defaults to ``LEVI``.
    """
    name = (identity or "LEVI").strip() or "LEVI"
    return "\n".join(_ASSISTANT_CORE_LINES).format(identity=name)


# ---------------------------------------------------------------------------
# 2. User-context loading (read-only on MemoryStore, fail-soft)
# ---------------------------------------------------------------------------

_CONTEXT_LIMIT = 12


def load_user_context(store=None, limit: int = _CONTEXT_LIMIT) -> str:
    """Build a compact "what I know about you" block from memory.

    Preferences first, then facts, then relationships — capped at ``limit``
    lines. Returns ``""`` when the store is empty or unavailable.

    ``store`` may be a :class:`levi.memory.store.MemoryStore` (or a
    duck-typed stand-in with ``.list(memory_type=..., limit=...)``); when
    ``None``, a default store is opened lazily. Read-only; never raises.
    """
    try:
        if store is None:
            from levi.memory.store import MemoryStore

            store = MemoryStore()
        from levi.memory.types import MemoryType

        order = (
            MemoryType.PREFERENCE,
            MemoryType.SEMANTIC,
            MemoryType.RELATIONSHIP,
        )
    except Exception:
        return ""
    try:
        seen = set()
        lines: List[str] = []
        for mtype in order:
            try:
                entries = store.list(memory_type=mtype, limit=limit)
            except Exception:
                continue
            for entry in entries or []:
                eid = getattr(entry, "id", None)
                if eid in seen:
                    continue
                seen.add(eid)
                text = (getattr(entry, "content", "") or "").strip().replace(
                    "\n", " "
                )
                if not text:
                    continue
                mtype_val = getattr(
                    getattr(entry, "memory_type", None), "value", "note"
                )
                lines.append("- [%s] %s" % (mtype_val, text[:160]))
                if len(lines) >= limit:
                    break
            if len(lines) >= limit:
                break
    except Exception:
        return ""
    if not lines:
        return ""
    return (
        "What I know about you (from memory — correct me if I'm wrong):\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# 3. Candidate learnings (heuristic proposals only — no consolidation)
# ---------------------------------------------------------------------------

# Deliberately narrow patterns. These are labeled "heuristic" because they
# are — the growth loop's consolidation decides what actually becomes a
# durable memory. Format mirrors the pending-learnings queue records the
# bot writes (~/.levi/bot/pending_learnings.jsonl), with `content` naming
# the proposed memory text.
_CANDIDATE_PATTERNS = (
    (re.compile(r"\bremember that (.+?)(?:\.|$)", re.I), "fact"),
    (re.compile(r"\bcall me ([\w\- ]{1,30})", re.I), "preference"),
    (
        re.compile(
            r"\bi (prefer|like|love|hate|dislike|can't stand) ([^.?!]{2,120})",
            re.I,
        ),
        "preference",
    ),
    (
        re.compile(
            r"\bmy (name|birthday|timezone|editor|shell|phone|email) is "
            r"([^.?!]{1,80})",
            re.I,
        ),
        "fact",
    ),
    (
        re.compile(
            r"\bactually,?\s+my ([\w\- ]{1,30}) is ([^.?!]{1,80})", re.I
        ),
        "fact",
    ),
)


def candidate_learnings(transcript_text: str) -> List[Dict[str, str]]:
    """Extract candidate durable facts/preferences from text (heuristic).

    Returns a list of ``{"content", "kind", "confidence", "source"}`` dicts
    with ``confidence="heuristic"`` and ``source="assistant-core"``.
    Empty list when nothing matches or input is not a usable string.
    Never raises. This only *proposes* — consolidation is the growth
    loop's job.
    """
    if not isinstance(transcript_text, str) or not transcript_text.strip():
        return []
    candidates: List[Dict[str, str]] = []
    for pattern, kind in _CANDIDATE_PATTERNS:
        try:
            match = pattern.search(transcript_text)
        except Exception:
            continue
        if not match:
            continue
        groups = [g for g in match.groups() if g]
        text = " ".join(g.strip() for g in groups)
        text = re.sub(r"\s+", " ", text).strip(" .")
        if len(text) < 3 or len(text) > 200:
            continue
        if any(c["content"].lower() == text.lower() for c in candidates):
            continue
        candidates.append(
            {
                "content": text,
                "kind": kind,
                "confidence": "heuristic",
                "source": "assistant-core",
            }
        )
    return candidates


# ---------------------------------------------------------------------------
# 4. Convenience composer
# ---------------------------------------------------------------------------


def build_agent_prompt(
    user_text: str = "", store=None, identity: str = "LEVI"
) -> str:
    """Compose the ready-to-use agent prompt: core + user context.

    ``user_text`` is accepted for future use (e.g. context retrieval keyed
    on the request) and currently unused beyond validation. Returns the
    assistant-core section, followed by the user-context block when memory
    has anything to say.
    """
    _ = user_text  # reserved for request-keyed context retrieval
    core = assistant_system_prompt(identity=identity)
    context = load_user_context(store=store)
    if context:
        return core + "\n\n" + context
    return core
