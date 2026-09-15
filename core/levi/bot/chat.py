"""Conversational engine for the LEVI bot.

One-shot :func:`say` and a readline-friendly :func:`repl` loop. Replies are
produced through the real agent runtime (:func:`levi.agent.loop.run_subtask`)
with the spark persona as the system prompt; when the runtime is unavailable
— or ``LEVI_BOT_OFFLINE=1`` is set — a deterministic, stdlib-only rules
engine answers instead and *honestly labels itself as the offline fallback*.
No model call is ever invented.

Conversation history is appended to ``~/.levi/bot/history.jsonl`` (JSONL,
append-only, rotated when oversized). The state directory can be overridden
with ``LEVI_BOT_HOME`` for hermetic tests.

All imports of ``core.levi.agent`` are lazy (inside functions) so this
module imports clean standalone.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

from levi.bot.persona import (
    answer_identity_question,
    kindness_guardrail,
    render_system_prompt,
)

# History rotation: rewrite the file when it grows past this many bytes,
# keeping the most recent entries.
_HISTORY_MAX_BYTES = 1_000_000
_HISTORY_KEEP_LINES = 400
_PERSONA_ID = "spark"

_GREETINGS = (
    "hey, look who decided to show up",
    "well well well, back for more",
    "hey! pull up a chair",
)
_HELP_TEXT = (
    "Here's the deal: I'm LEVI running the spark card — bold, witty, direct, "
    "with a warm core. Ask me stuff, and I'll answer straight, jokes included. "
    "I can think through problems step by step, call LEVI tools when the "
    "runtime is up, and I'm honest when I don't know something. Try 'who are "
    "you', or just throw a question at me."
)

# Deterministic pool of fallback one-liners, keyed by a stable hash of the
# input so replies are repeatable across runs.
_FALLBACK_LINES = (
    "Fair question. I'm chewing on it with pure local brainpower — no cloud, "
    "no model, just me and my rules engine. What angle are you after?",
    "Noted! My offline brain is doing its best here. Give me a nudge on what "
    "a good answer looks like and I'll take another swing.",
    "Okay, real talk: I'm running the honest offline fallback right now, so "
    "I won't pretend I looked anything up. But I'm listening — say more.",
    "Interesting. My local rules engine doesn't have a hot take preloaded "
    "for that one, but I'm game to work through it with you.",
)


def _state_dir() -> str:
    """Return the bot state directory (override via ``LEVI_BOT_HOME``)."""
    override = os.environ.get("LEVI_BOT_HOME")
    if override:
        return os.path.join(override, "bot")
    return os.path.join(os.path.expanduser("~"), ".levi", "bot")


def _history_path() -> str:
    """Path to the append-only JSONL history file."""
    return os.path.join(_state_dir(), "history.jsonl")


def record(role: str, text: str, mode: str) -> None:
    """Append one turn to the JSONL history, rotating if oversized.

    ``role`` is ``"user"`` or ``"bot"``; ``mode`` is ``"agent"`` or
    ``"offline"``. Failures to write history never break a reply.
    """
    try:
        path = _history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "persona": _PERSONA_ID,
            "mode": mode,
            "text": text,
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if os.path.getsize(path) > _HISTORY_MAX_BYTES:
            _rotate_history(path)
    except OSError:
        pass  # history is best-effort; the reply still stands


def _rotate_history(path: str) -> None:
    """Rewrite the history file keeping only the most recent entries."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        keep = lines[-_HISTORY_KEEP_LINES:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(tmp, path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Offline fallback: deterministic rules engine, spark voice, honest label
# ---------------------------------------------------------------------------

_OFFLINE_TAG = " — [offline mode: local rules engine, no model]"


def _offline_reply(text: str) -> str:
    """Build a reply without any model or network.

    Deterministic for a given input. Always carries the offline label so
    the user can tell this is the fallback, not the agent runtime.
    """
    lowered = text.strip().lower()

    identity = answer_identity_question(text)
    if identity is not None:
        return identity + _OFFLINE_TAG

    if lowered in {"hi", "hello", "hey", "yo", "sup", "howdy"} or lowered.startswith(
        ("hi ", "hello ", "hey ")
    ):
        pick = _GREETINGS[
            hashlib.sha256(lowered.encode()).digest()[0] % len(_GREETINGS)
        ]
        return (
            f"{pick.capitalize()}! I'm LEVI on the spark card — running "
            f"offline today, all local, zero cloud. What's on your mind?" + _OFFLINE_TAG
        )

    if any(k in lowered for k in ("help", "what can you do", "commands")):
        return _HELP_TEXT + _OFFLINE_TAG

    if "thank" in lowered:
        return "Anytime. This is what I'm here for — no cloud required." + _OFFLINE_TAG

    if any(k in lowered for k in ("weather", "news", "stock price", "score")):
        return (
            "I'd love to, but I'm offline — no network from here, and I won't "
            "fake live data. Hook me up to the agent runtime (or just tell me "
            "what you already know) and I'll work with that." + _OFFLINE_TAG
        )

    idx = int.from_bytes(hashlib.sha256(lowered.encode()).digest()[:2], "big")
    return _FALLBACK_LINES[idx % len(_FALLBACK_LINES)] + _OFFLINE_TAG


# ---------------------------------------------------------------------------
# Agent-runtime path (lazy)
# ---------------------------------------------------------------------------


def _agent_reply(text: str) -> Optional[str]:
    """Try the real agent runtime; return ``None`` on any failure.

    Uses :func:`levi.agent.loop.run_subtask` with the spark system prompt.
    ``LEVI_BOT_OFFLINE=1`` forces the fallback (used by tests and by users
    who want the deterministic engine). ``LEVI_BOT_PROVIDER`` (falling back
    to ``LEVI_PROVIDER``) selects the provider; never invents a call.
    """
    if os.environ.get("LEVI_BOT_OFFLINE", "").strip().lower() in {"1", "true", "yes"}:
        return None
    try:
        from levi.agent.loop import run_subtask
    except Exception:
        return None
    provider = os.environ.get("LEVI_BOT_PROVIDER") or os.environ.get("LEVI_PROVIDER")
    try:
        transcript = run_subtask(
            text,
            provider=provider or "local",
            system_prompt=render_system_prompt(),
            max_steps=6,
        )
    except Exception:
        return None
    final = getattr(transcript, "final", "") or ""
    final = final.strip()
    return final or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def say(text: str) -> str:
    """One-shot reply to *text*.

    Pipeline: kindness guardrail → agent runtime (spark system prompt) →
    honest offline fallback. The turn is recorded to history. Raises
    :class:`ValueError` for empty input.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("say: 'text' must be a non-empty string")
    text = text.strip()

    refusal = kindness_guardrail(text)
    if refusal is not None:
        record("user", text, "guardrail")
        record("bot", refusal, "guardrail")
        return refusal

    reply = _agent_reply(text)
    mode = "agent"
    if reply is None:
        reply = _offline_reply(text)
        mode = "offline"
    record("user", text, mode)
    record("bot", reply, mode)
    return reply


def repl() -> None:
    """Run the interactive REPL. ``quit``/``exit`` (or Ctrl-D) leaves."""
    try:
        import readline  # noqa: F401  -- nicer editing when available
    except ImportError:
        pass
    print("LEVI · spark — type 'quit' to leave.")
    while True:
        try:
            line = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in {"quit", "exit", ":q"}:
            break
        print("levi> " + say(line))
    print("Later! 👋")
