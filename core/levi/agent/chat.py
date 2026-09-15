"""Long conversations for the agent runtime: sessions, context management.

``levi agent chat`` is an interactive REPL where every turn runs the full
agentic loop — tools are available on every turn, not just the first.
Conversation history persists per session as JSONL under
``~/.levi/agent/sessions/<name>.jsonl`` (override with
``LEVI_AGENT_SESSIONS_DIR``); re-running with the same ``--session``
resumes the dialogue.

Context management: the working context is bounded by the provider's
context window (``levi-local``: ``LEVI_LOCAL_CTX_SIZE``, default 32768,
clamped to the model's native size; other providers: a conservative
documented default). When the estimated context crosses 80% of the
window, the oldest turns are compressed before the next turn runs:

1. The provider itself writes a rolling summary (``SUMMARY:`` / ``FACTS:``
   format). With the rule-based ``local`` planner — which cannot
   summarize — an extractive fallback is used and labeled as such.
2. Durable facts are persisted to the agent scratch memory via the
   ``memory_write`` tool (one file per session), so they survive even
   session-file rotation.
3. A ``note`` record is appended to the session log naming what was
   compressed. History is never silently truncated: the JSONL log keeps
   every original message, and the summary travels forward in the
   working context.

Stdlib only. No network except what the provider itself uses.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from levi.agent.loop import AgentTranscript, run_subtask
from levi.agent.providers import ChatMessage, ChatProvider, select_provider
from levi.agent.tools import build_default_registry

SESSIONS_ENV = "LEVI_AGENT_SESSIONS_DIR"
DEFAULT_SESSION = "default"
COMPRESSION_THRESHOLD = 0.80  # compress when estimate >= 80% of the window
KEEP_RECENT_USER_TURNS = 6  # user turns kept verbatim when compressing
# Heuristic allowance for the loop's system prompt (15 tool schemas) when
# estimating context before a turn. After a turn, real usage numbers from
# the provider replace the estimate.
SYSTEM_PROMPT_ALLOWANCE_TOKENS = 1200
# Context window assumed when the provider does not report one. Deliberately
# conservative: under-claiming only triggers earlier summarization.
CONSERVATIVE_CTX_SIZE = 16384

_SESSION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def sessions_dir() -> Path:
    """Session storage dir: ``LEVI_AGENT_SESSIONS_DIR`` or
    ``~/.levi/agent/sessions``."""
    override = os.environ.get(SESSIONS_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi" / "agent" / "sessions"


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Used only to *trigger*
    compression; per-turn reporting prefers the provider's real usage."""
    return max(1, len(text or "") // 4)


def sanitize_session_name(name: str) -> str:
    """Validate a session id for safe use as a filename. Raises ValueError."""
    name = (name or "").strip()
    if not _SESSION_NAME_RE.match(name):
        raise ValueError(
            "invalid session id %r: use 1-64 chars of A-Za-z0-9_-, "
            "starting with a letter or digit" % (name or "",)
        )
    return name


# ---------------------------------------------------------------------------
# Session log (append-only JSONL)
# ---------------------------------------------------------------------------


class ChatSession:
    """One persistent conversation. Records are append-only; compression
    never deletes — a ``summary`` record marks how many leading messages
    it covers, and the working context starts after it."""

    def __init__(self, name: str = DEFAULT_SESSION):
        self.name = sanitize_session_name(name)
        self.path = sessions_dir() / (self.name + ".jsonl")
        self.records: list[dict] = []
        self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> None:
        self.records = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(rec, dict) and rec.get("kind"):
                        self.records.append(rec)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _append(self, record: dict) -> None:
        record = dict(record)
        record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.records.append(record)

    # -- writers ----------------------------------------------------------

    def append_message(
        self,
        role: str,
        content: str,
        *,
        name: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        rec: dict[str, Any] = {
            "kind": "message",
            "role": role,
            "content": content or "",
        }
        if name:
            rec["name"] = name
        if tool_call_id:
            rec["tool_call_id"] = tool_call_id
        self._append(rec)

    def append_summary(self, text: str, covers_messages: int) -> None:
        self._append(
            {"kind": "summary", "content": text, "covers_messages": covers_messages}
        )

    def append_note(self, text: str) -> None:
        self._append({"kind": "note", "content": text})

    def append_turn_meta(self, *, provider: str, ok: bool, steps: int) -> None:
        """Machine-readable provenance for one completed turn.

        Recorded so later analysis (e.g. the growth loop) can attribute
        a turn to the provider/source that served it. Ignored by the
        dialogue readers (``messages()`` / ``notes()``) and by the
        local session harvester.
        """
        self._append(
            {
                "kind": "turn-meta",
                "provider": provider or "?",
                "ok": bool(ok),
                "steps": int(steps),
            }
        )

    # -- readers ----------------------------------------------------------

    def message_records(self) -> list[dict]:
        return [r for r in self.records if r.get("kind") == "message"]

    def messages(self) -> list[ChatMessage]:
        """All message records as ChatMessage (the full dialogue)."""
        out = []
        for r in self.message_records():
            out.append(
                ChatMessage(
                    role=r.get("role", "user"),
                    content=r.get("content", ""),
                    name=r.get("name"),
                    tool_call_id=r.get("tool_call_id"),
                )
            )
        return out

    def summary(self) -> tuple[str, int] | tuple[None, int]:
        """(text, covers_messages) of the latest summary, or (None, 0)."""
        for r in reversed(self.records):
            if r.get("kind") == "summary":
                return r.get("content", ""), int(r.get("covers_messages") or 0)
        return None, 0

    def notes(self) -> list[str]:
        return [r.get("content", "") for r in self.records if r.get("kind") == "note"]


# ---------------------------------------------------------------------------
# Conversation manager: turns, compression, memory
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    transcript: AgentTranscript
    context_pct: float  # 0.0-1.0+ of the window used by this turn
    compressed: bool  # whether compression ran before this turn
    summary: str | None  # rolling summary after this turn (if any)


class ConversationManager:
    """Runs chat turns for one session with context management.

    ``ctx_size`` overrides the window; otherwise ``levi-local`` uses its
    configured size and other providers get the conservative default.
    """

    def __init__(
        self,
        session_name: str = DEFAULT_SESSION,
        *,
        provider: ChatProvider | str | None = None,
        registry: Any = None,
        ctx_size: int | None = None,
        max_steps: int = 10,
        consent: bool = False,
        confirm: Any = None,
        workspace_root: Any = None,
        system_prompt: str | None = None,
        affect: bool = False,
        affect_session: Any = None,
    ):
        self.session = ChatSession(session_name)
        if isinstance(provider, ChatProvider):
            self.provider = provider
        else:
            self.provider = select_provider(provider)
        self.provider_name = getattr(self.provider, "name", None) or "?"
        self.registry = registry
        self.max_steps = max(1, int(max_steps or 10))
        self.consent = bool(consent)
        self.confirm = confirm
        self.workspace_root = workspace_root
        self.system_prompt = system_prompt
        self.affect = bool(affect)
        if affect_session is not None:
            self.affect_session = affect_session
        else:
            self.affect_session = None
            if self.affect:
                try:
                    from levi.affect import SessionEI

                    self.affect_session = SessionEI()
                except Exception:
                    self.affect_session = None
        if ctx_size:
            self.ctx_size = max(1, int(ctx_size))
        elif self.provider_name == "levi-local":
            from levi.agent.local_model import ctx_size as _local_ctx

            self.ctx_size = _local_ctx()
        else:
            self.ctx_size = CONSERVATIVE_CTX_SIZE
        self._memory_key = "chat-%s" % self.session.name

    # -- public -----------------------------------------------------------

    def turn(
        self,
        user_text: str,
        *,
        max_steps: int | None = None,
        consent: bool | None = None,
        confirm: Any = "UNCHANGED",
    ) -> TurnResult:
        """Run one user turn: compress if needed, run the agentic loop,
        persist everything, report context usage."""
        text = (user_text or "").strip()
        if not text:
            raise ValueError("turn() requires a non-empty message")
        self.session.append_message("user", text)

        compressed = self._maybe_compress()
        history = self._context_messages()
        # The new user message is already the tail of the context (it was
        # appended to the session above); run_subtask() appends `task`
        # itself, so drop the duplicate instead of sending it twice.
        if history and history[-1].role == "user" and history[-1].content == text:
            history = history[:-1]

        use_consent = self.consent if consent is None else bool(consent)
        use_confirm = self.confirm if confirm == "UNCHANGED" else confirm
        registry = self.registry or build_default_registry(
            workspace_root=self.workspace_root,
            consent=use_consent,
            confirm=use_confirm,
        )
        transcript = run_subtask(
            text,
            provider=self.provider,
            registry=registry,
            history=history,
            max_steps=self.max_steps if max_steps is None else max(1, max_steps),
            consent=use_consent,
            confirm=use_confirm,
            workspace_root=self.workspace_root,
            system_prompt=self.system_prompt,
            affect=self.affect,
            affect_session=self.affect_session,
        )

        # Persist the turn's dialogue (assistant texts, tool exchanges,
        # final answer) so a resumed session sees the whole dialogue.
        for step in transcript.steps:
            if step.provider_text:
                self.session.append_message("assistant", step.provider_text)
            for call, result in zip(step.tool_calls, step.results, strict=False):
                content = (result.get("output") or result.get("error") or "").strip()
                self.session.append_message("tool", content, name=call.get("name"))
        if transcript.final:
            self.session.append_message("assistant", transcript.final)

        # Provenance for later analysis (growth loop, audits): which
        # provider served this turn and whether the loop succeeded.
        self.session.append_turn_meta(
            provider=self.provider_name,
            ok=transcript.ok,
            steps=len(transcript.steps),
        )

        pct = self._context_pct(transcript, history, text)
        summary, _ = self.session.summary()
        return TurnResult(
            transcript=transcript,
            context_pct=pct,
            compressed=compressed,
            summary=summary,
        )

    # -- context ----------------------------------------------------------

    def _context_messages(self) -> list[ChatMessage]:
        """Working context: rolling summary (if any) + unsummarized tail."""
        summary_text, covers = self.session.summary()
        msgs: list[ChatMessage] = []
        if summary_text:
            msgs.append(
                ChatMessage(
                    role="user",
                    content=(
                        "[Rolling summary of earlier conversation — compressed "
                        "context, not a new message. Treat it as background and "
                        "continue the dialogue.]\n" + summary_text
                    ),
                )
            )
        msgs.extend(self.session.messages()[covers:])
        return msgs

    def _estimate_context_tokens(self) -> int:
        total = SYSTEM_PROMPT_ALLOWANCE_TOKENS
        for m in self._context_messages():
            total += estimate_tokens(m.content)
        return total

    def _context_pct(
        self, transcript: AgentTranscript, history: list[ChatMessage], user_text: str
    ) -> float:
        """Fraction of the window used. Prefers the provider's real
        prompt-token total from the transcript; falls back to the
        character heuristic when the provider reports nothing."""
        used = transcript.prompt_tokens or 0
        if not used:
            used = SYSTEM_PROMPT_ALLOWANCE_TOKENS + estimate_tokens(user_text)
            for m in history:
                used += estimate_tokens(m.content)
        return used / max(1, self.ctx_size)

    # -- compression ------------------------------------------------------

    def _maybe_compress(self) -> bool:
        """Compress the oldest turns when the estimate crosses the
        threshold. Returns True when compression ran."""
        if self._estimate_context_tokens() < COMPRESSION_THRESHOLD * self.ctx_size:
            return False
        records = self.session.message_records()
        if not records:
            return False
        _, already_covered = self.session.summary()
        # Find the split: keep the last KEEP_RECENT_USER_TURNS user turns
        # (and everything after the KEEP-th newest user message) verbatim.
        user_idx = [
            i
            for i, r in enumerate(records)
            if r.get("role") == "user"
            and not (r.get("content") or "").startswith("[Rolling summary")
        ]
        if len(user_idx) <= KEEP_RECENT_USER_TURNS:
            return False  # nothing old enough to compress; one huge turn
        split = user_idx[-KEEP_RECENT_USER_TURNS]
        if split <= already_covered:
            return False
        older_recs = records[already_covered:split]
        if not older_recs:
            return False
        older = [
            ChatMessage(
                role=r.get("role", "user"),
                content=r.get("content", ""),
                name=r.get("name"),
                tool_call_id=r.get("tool_call_id"),
            )
            for r in older_recs
        ]
        summary_text, facts = self._summarize(older)
        self.session.append_summary(summary_text, covers_messages=split)
        for fact in facts:
            self._remember_fact(fact)
        self.session.append_note(
            "Context management: compressed %d older message(s) into the "
            "rolling summary above; kept the last %d user turn(s) verbatim. "
            "The original messages remain in this log — nothing was deleted."
            % (len(older_recs), KEEP_RECENT_USER_TURNS)
        )
        return True

    def _summarize(self, older: list[ChatMessage]) -> tuple[str, list[str]]:
        """Return (rolling_summary, durable_facts) for the older turns."""
        convo = "\n".join("%s: %s" % (m.role, (m.content or "")[:2000]) for m in older)
        prev, _ = self.session.summary()
        if self.provider_name == "local":
            # The rule-based planner cannot write summaries: extractive
            # fallback, labeled honestly.
            first = next((m.content for m in older if m.role == "user"), "")
            text = (
                "(extractive summary — the rule-based planner cannot "
                "summarize; showing the oldest turn verbatim) "
                + (first[:400] or "(no user text)")
                + (" …[%d earlier messages]" % len(older) if len(older) > 1 else "")
            )
            return text, []
        prompt = (
            "You are compressing a long conversation for a local AI "
            "assistant with a limited context window. "
        )
        if prev:
            prompt += (
                "A previous summary exists — fold it in and update it:\n"
                + prev
                + "\n\n"
            )
        prompt += (
            "Write a compact rolling summary (3-6 sentences) of the "
            "conversation below: keep decisions, names, numbers, preferences, "
            "and open tasks. Then list durable facts worth remembering "
            "long-term (user preferences, project facts), one per line.\n\n"
            "Respond in EXACTLY this format:\n"
            "SUMMARY: <summary>\n"
            "FACTS:\n"
            "- <fact>\n"
            "- <fact>\n\n"
            "Conversation:\n" + convo
        )
        try:
            resp = self.provider.chat([ChatMessage(role="user", content=prompt)], [])
        except Exception as exc:
            resp = None
            error = "%s: %s" % (type(exc).__name__, exc)
        else:
            error = resp.error
        if resp is None or error or not (resp.text or "").strip():
            # Never drop history: keep a stub summary and the note
            # records why compression is degraded.
            return (
                "(automatic summarization failed%s; older turns are kept "
                "in the log and the summary will be retried next time)"
                % (": " + error if error else ""),
                [],
            )
        return self._parse_summary_response(resp.text)

    @staticmethod
    def _parse_summary_response(text: str) -> tuple[str, list[str]]:
        """Split a SUMMARY:/FACTS: response. Tolerant of sloppy models."""
        summary, facts_block = text, ""
        if "FACTS:" in text:
            summary, facts_block = text.split("FACTS:", 1)
        summary = summary.strip()
        for prefix in ("SUMMARY:", "Summary:"):
            if summary.startswith(prefix):
                summary = summary[len(prefix) :].strip()
                break
        facts = []
        for line in facts_block.splitlines():
            line = line.strip()
            if line.startswith("-"):
                line = line[1:].strip()
            if line and len(line) > 2:
                facts.append(line)
        return summary or text.strip(), facts

    def _remember_fact(self, fact: str) -> None:
        """Persist one durable fact to the agent scratch memory."""
        registry = self.registry or build_default_registry(
            workspace_root=self.workspace_root
        )
        try:
            existing = ""
            res = registry.execute("memory_read", {"name": self._memory_key})
            if res.ok and res.output:
                existing = res.output
        except Exception:
            existing = ""
        entry = "[%s] %s" % (time.strftime("%Y-%m-%d"), fact.strip())
        if entry not in existing:
            combined = (existing.rstrip() + "\n" + entry).strip()
            try:
                registry.execute(
                    "memory_write", {"name": self._memory_key, "content": combined}
                )
            except Exception:
                pass

    def read_facts(self) -> str:
        """Durable facts remembered for this session (may be empty)."""
        registry = self.registry or build_default_registry(
            workspace_root=self.workspace_root
        )
        try:
            res = registry.execute("memory_read", {"name": self._memory_key})
            return res.output if res.ok else ""
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------

_REPL_HELP = """\
Commands:
  /help     show this help
  /summary  show the current rolling summary (if compression has run)
  /facts    show durable facts remembered for this session
  /context  show estimated context usage for the next turn
  /quit     save and exit (Ctrl-D also exits)
Every other line is sent as your message; each turn runs the full
agentic loop with tools. History is saved per session automatically.\
"""


def run_chat_repl(
    session_name: str = DEFAULT_SESSION,
    *,
    provider: Any = None,
    registry: Any = None,
    max_steps: int = 10,
    consent: bool = False,
    confirm: Any = None,
    workspace_root: Any = None,
    system_prompt: str | None = None,
    affect: bool = False,
    affect_session: Any = None,
) -> None:
    """Interactive long-conversation REPL. Returns on /quit / EOF."""
    mgr = ConversationManager(
        session_name,
        provider=provider,
        registry=registry,
        max_steps=max_steps,
        consent=consent,
        confirm=confirm,
        workspace_root=workspace_root,
        system_prompt=system_prompt,
        affect=affect,
        affect_session=affect_session,
    )
    resumed = len(mgr.session.message_records())
    print(
        "levi agent chat — session %r (provider=%s, ctx=%d tokens%s)"
        % (
            mgr.session.name,
            mgr.provider_name,
            mgr.ctx_size,
            ", resumed %d message(s)" % resumed if resumed else ", new session",
        )
    )
    print("Type /help for commands, /quit to exit.\n")

    def _confirm(preview: str) -> bool:
        import sys as _sys

        if not _sys.stdin.isatty():
            return False
        try:
            answer = input(f"{preview}\nApprove? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes")

    while True:
        try:
            line = input("you> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break
        line = line.strip()
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line == "/help":
            print(_REPL_HELP)
            continue
        if line == "/summary":
            summary, _ = mgr.session.summary()
            print(summary or "(no summary yet — compression has not run)")
            continue
        if line == "/facts":
            print(mgr.read_facts() or "(no durable facts stored yet)")
            continue
        if line == "/context":
            est = mgr._estimate_context_tokens()
            print(
                "estimated next-turn context: ~%d tokens (%.0f%% of %d)"
                % (est, 100.0 * est / max(1, mgr.ctx_size), mgr.ctx_size)
            )
            continue
        try:
            result = mgr.turn(
                line,
                consent=consent,
                confirm=None if consent else (_confirm if confirm is None else confirm),
            )
        except Exception as exc:
            print("turn failed: %s: %s" % (type(exc).__name__, exc))
            continue
        t = result.transcript
        for step in t.steps:
            if step.provider_text:
                print(f"  [step {step.index + 1}] {step.provider_text[:300]}")
            for call, res in zip(step.tool_calls, step.results, strict=False):
                verdict = "ok" if res.get("ok") else "FAILED"
                print(f"  tool {call.get('name')} → {verdict}")
                if res.get("output"):
                    print(f"    {res['output'][:300]}")
                if res.get("error"):
                    print(f"    error: {res['error'][:300]}")
        status = "ok" if t.ok else "FAILED"
        print(f"\nlevi [{status}] {t.final}")
        if result.compressed:
            print("(context was compressed this turn — see /summary)")
        print(
            "context ~%.0f%% of %d tokens\n"
            % (100.0 * result.context_pct, mgr.ctx_size)
        )
    print(
        "session %r saved (%d messages)."
        % (mgr.session.name, len(mgr.session.message_records()))
    )
