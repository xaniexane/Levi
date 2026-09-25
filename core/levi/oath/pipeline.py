"""Unix-pipe-style mission pipelines for LEVI Oath.

Syntax::

    cmd:disk-usage path=/tmp | ai:"summarise the usage" | reply:body="{stdin}"

* ``cmd:<name> [k=v ...]`` — a signed command definition from the registry.
* ``ai:"prompt"`` — an AI-reasoning stage.  The prompt may reference
  ``{stdin}``; if it does not, the previous stage's stdout is appended to
  the prompt automatically.
* ``reply:subject="..." body="..."`` — a mail-reply stage (executed by the
  daemon via SMTP; in ``--dry-run`` it is only previewed).

Stages run left to right; each stage's stdout becomes the next stage's
stdin.  **Permissions are checked before each stage executes** — a denial
stops the pipeline before the stage runs.

The ``ai`` stage runs through LEVI's real agent runtime
(:func:`levi.agent.loop.run_subtask`), imported lazily *inside* the stage
function so this module imports cleanly without the agent stack.  When the
agent runtime is unavailable or raises, the stage falls back to a
deterministic offline rules engine whose output is honestly labeled
``[offline-fallback]`` — it never invents a model call.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from levi.oath.commands import CommandDefinition, CommandRegistry, DefinitionError
from levi.oath.contacts import Contact
from levi.oath.policy import PolicyDecision, check_command

__all__ = [
    "Stage",
    "StageResult",
    "Pipeline",
    "PipelineError",
    "parse",
    "ai_reason",
]

#: Placeholder substituted with the previous stage's stdout.
STDIN_PLACEHOLDER = "{stdin}"


class PipelineError(Exception):
    """Raised when a pipeline cannot be parsed, authorised, or run."""


@dataclass
class Stage:
    """One parsed pipeline stage."""

    kind: str  # "cmd" | "ai" | "reply"
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "args": dict(self.args),
            "raw": self.raw,
        }


@dataclass
class StageResult:
    """Outcome of running one stage."""

    stage: Stage
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    decision: Optional[PolicyDecision] = None
    note: str = ""


@dataclass
class Pipeline:
    """A parsed pipeline plus its execution report."""

    stages: list[Stage]
    results: list[StageResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": [s.to_dict() for s in self.stages],
            "results": [
                {
                    "stage": r.stage.to_dict(),
                    "ok": r.ok,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                    "returncode": r.returncode,
                    "allowed": None if r.decision is None else r.decision.allowed,
                    "gate": None if r.decision is None else r.decision.gate,
                    "reason": "" if r.decision is None else r.decision.reason,
                    "note": r.note,
                }
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_STAGE_RE = re.compile(r"^(cmd|ai|reply)\s*:\s*(.*)$", re.DOTALL)


def _split_stages(text: str) -> list[str]:
    """Split on ``|`` while respecting single/double quotes."""
    parts: list[str] = []
    buf: list[str] = []
    quote: Optional[str] = None
    escape = False
    for ch in text:
        if escape:
            buf.append(ch)
            escape = False
        elif ch == "\\":
            buf.append(ch)
            escape = True
        elif quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            buf.append(ch)
            quote = ch
        elif ch == "|":
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def parse_stage(text: str) -> Stage:
    """Parse one stage such as ``cmd:disk-usage path=/tmp`` or ``ai:"prompt"``."""
    match = _STAGE_RE.match(text.strip())
    if not match:
        raise PipelineError(
            f"cannot parse stage {text!r}: expected cmd:… / ai:… / reply:…"
        )
    kind, rest = match.group(1), match.group(2).strip()
    if kind == "ai":
        prompt = rest
        if len(prompt) >= 2 and prompt[0] == prompt[-1] and prompt[0] in ("'", '"'):
            prompt = prompt[1:-1]
        if not prompt:
            raise PipelineError("ai stage needs a non-empty prompt")
        return Stage(kind="ai", name="ai", args={"prompt": prompt}, raw=text)
    if kind == "reply":
        argv = shlex.split(rest)
        args: dict[str, Any] = {}
        for token in argv:
            if "=" not in token:
                raise PipelineError(f"reply stage expects k=v args, got {token!r}")
            key, _, value = token.partition("=")
            args[key] = value
        return Stage(kind="reply", name="reply", args=args, raw=text)
    # kind == "cmd"
    argv = shlex.split(rest)
    if not argv:
        raise PipelineError("cmd stage needs a command name")
    name = argv[0]
    args = {}
    for token in argv[1:]:
        if "=" not in token:
            raise PipelineError(f"cmd stage expects k=v args, got {token!r}")
        key, _, value = token.partition("=")
        args[key] = value
    return Stage(kind="cmd", name=name, args=args, raw=text)


def parse(text: str) -> Pipeline:
    """Parse pipeline text into a :class:`Pipeline` (not yet executed)."""
    stages = [_split_stages(text)]
    parsed = [parse_stage(part) for part in stages[0]]
    if not parsed:
        raise PipelineError("empty pipeline")
    return Pipeline(stages=parsed)


# ---------------------------------------------------------------------------
# AI stage
# ---------------------------------------------------------------------------


def _offline_fallback_reason(prompt: str, stdin_text: str) -> str:
    """Deterministic offline rules engine for the ai stage.

    Used only when LEVI's agent runtime cannot be reached.  The output is
    explicitly labeled so nobody mistakes it for model output.
    """
    lines = [ln for ln in stdin_text.splitlines() if ln.strip()]
    words = len(stdin_text.split())
    head = "\n".join(lines[:10])
    summary = (
        "[offline-fallback] LEVI agent runtime unavailable; deterministic "
        "rules engine responded.\n"
        f"prompt: {prompt[:500]}\n"
        f"input: {len(lines)} non-empty lines, {words} words\n"
        f"first lines:\n{head[:2000]}"
    )
    return summary


def ai_reason(
    prompt: str, stdin_text: str = "", *, max_steps: int = 3
) -> tuple[str, str]:
    """Run an AI-reasoning stage.  Returns ``(output, note)``.

    Tries LEVI's real agent runtime first (lazy import — this module must
    stay importable without it).  On any failure, falls back to the honest
    offline rules engine; ``note`` records which path was taken.
    """
    full_prompt = prompt
    if STDIN_PLACEHOLDER in full_prompt:
        full_prompt = full_prompt.replace(STDIN_PLACEHOLDER, stdin_text)
    elif stdin_text.strip():
        full_prompt = f"{full_prompt}\n\n--- piped input ---\n{stdin_text}"

    try:
        from levi.agent.loop import run_subtask  # lazy: agent stack optional

        transcript = run_subtask(full_prompt, max_steps=max_steps, consent=False)
        text = _transcript_text(transcript)
        if text:
            return text, "via levi.agent.loop.run_subtask"
    except Exception as exc:  # agent runtime missing/broken -> honest fallback
        note = f"agent runtime unavailable ({type(exc).__name__}); offline fallback"
        return _offline_fallback_reason(prompt, stdin_text), note
    return _offline_fallback_reason(
        prompt, stdin_text
    ), "agent returned empty; offline fallback"


def _transcript_text(transcript: Any) -> str:
    """Best-effort extraction of final text from an AgentTranscript."""
    for attr in ("final", "text", "reply", "summary", "output"):
        value = getattr(transcript, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    # Some transcripts expose messages; take the last assistant message.
    messages = getattr(transcript, "messages", None)
    if isinstance(messages, list):
        for msg in reversed(messages):
            content = getattr(msg, "content", None) or (
                msg.get("content") if isinstance(msg, dict) else None
            )
            role = getattr(msg, "role", None) or (
                msg.get("role") if isinstance(msg, dict) else None
            )
            if isinstance(content, str) and content.strip() and role != "user":
                return content
    text = str(transcript)
    return text if text and not text.startswith("<") else ""


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

ReplySender = Callable[[str, str, str], None]
"""``(to_address, subject, body) -> None`` — supplied by the daemon.

Contract: in ``dry_run`` mode the pipeline still invokes the sender for
``reply:`` stages (so the daemon can audit exactly what *would* be sent);
senders MUST treat those invocations as previews and never transmit.
The daemon's sender honors this by emitting a ``mission.reply_preview``
audit event instead of touching SMTP."""


def _render_reply_args(stage: Stage, stdin_text: str) -> dict[str, str]:
    args = dict(stage.args)
    for key in ("subject", "body"):
        value = str(args.get(key, ""))
        args[key] = value.replace(STDIN_PLACEHOLDER, stdin_text)
    return args


def run(
    pipeline: Pipeline,
    contact: Contact,
    *,
    registry: Optional[CommandRegistry] = None,
    stdin_text: str = "",
    dry_run: bool = False,
    reply_to: str = "",
    send_reply: Optional[ReplySender] = None,
    timeout: int = 120,
) -> Pipeline:
    """Execute a pipeline left to right.

    For each stage: check policy *first*; on denial, record the denial and
    stop.  ``dry_run=True`` previews the plan (rendered argv, decisions)
    without executing anything — no subprocess is spawned and no mail is
    sent.  Returns the pipeline with ``results`` populated.
    """
    registry = registry or CommandRegistry()
    stream = stdin_text
    pipeline.results = []

    for stage in pipeline.stages:
        try:
            definition = registry.get(stage.name)
        except DefinitionError as exc:
            pipeline.results.append(
                StageResult(
                    stage, False, decision=PolicyDecision(False, "permission", str(exc))
                )
            )
            break

        decision = check_command(contact, definition)
        if not decision.allowed:
            pipeline.results.append(StageResult(stage, False, decision=decision))
            break

        if dry_run:
            if stage.kind == "reply" and send_reply is not None:
                # Dry-run still notifies the sender so the daemon can audit
                # the exact preview; senders must never transmit on dry-run
                # (see ReplySender's contract).
                rendered = _render_reply_args(stage, stream)
                send_reply(reply_to, rendered["subject"], rendered["body"])
                note = _dry_preview(stage, definition, stream)
                pipeline.results.append(
                    StageResult(stage, True, stdout="", decision=decision, note=note)
                )
                continue
            note = _dry_preview(stage, definition, stream)
            pipeline.results.append(
                StageResult(stage, True, stdout="", decision=decision, note=note)
            )
            continue

        if stage.kind == "ai":
            prompt = str(stage.args.get("prompt", ""))
            if STDIN_PLACEHOLDER in prompt:
                prompt = prompt.replace(STDIN_PLACEHOLDER, stream)
            output, note = ai_reason(prompt, stream)
            pipeline.results.append(
                StageResult(stage, True, stdout=output, decision=decision, note=note)
            )
            stream = output
        elif stage.kind == "reply":
            rendered = _render_reply_args(stage, stream)
            try:
                definition.render(
                    {"subject": rendered["subject"], "body": rendered["body"]}
                )
            except DefinitionError as exc:
                pipeline.results.append(
                    StageResult(
                        stage,
                        False,
                        decision=PolicyDecision(False, "permission", str(exc)),
                    )
                )
                break
            if send_reply is None:
                pipeline.results.append(
                    StageResult(stage, False, note="no reply sender configured")
                )
                break
            try:
                send_reply(reply_to, rendered["subject"], rendered["body"])
            except Exception as exc:
                pipeline.results.append(
                    StageResult(stage, False, stderr=str(exc), note="reply send failed")
                )
                break
            pipeline.results.append(
                StageResult(
                    stage, True, stdout=f"reply sent to {reply_to}", decision=decision
                )
            )
        else:  # cmd
            try:
                proc = registry.execute(
                    definition, dict(stage.args), stdin_text=stream, timeout=timeout
                )
            except DefinitionError as exc:
                pipeline.results.append(
                    StageResult(
                        stage,
                        False,
                        decision=PolicyDecision(False, "permission", str(exc)),
                    )
                )
                break
            except Exception as exc:
                pipeline.results.append(
                    StageResult(stage, False, stderr=f"execution failed: {exc}")
                )
                break
            out = proc.stdout.decode("utf-8", "replace")
            err = proc.stderr.decode("utf-8", "replace")
            ok = proc.returncode == 0
            pipeline.results.append(
                StageResult(
                    stage,
                    ok,
                    stdout=out,
                    stderr=err,
                    returncode=proc.returncode,
                    decision=decision,
                    note="" if ok else f"command exited {proc.returncode}",
                )
            )
            if not ok:
                break
            stream = out

    return pipeline


def _dry_preview(stage: Stage, definition: CommandDefinition, stream: str) -> str:
    """Human-readable preview of what a stage *would* do."""
    if stage.kind == "ai":
        return f"would run AI stage with prompt {str(stage.args.get('prompt'))[:80]!r}"
    if stage.kind == "reply":
        rendered = _render_reply_args(stage, stream)
        return f"would reply subject={rendered['subject']!r} ({len(rendered['body'])} chars)"
    try:
        argv = definition.render(dict(stage.args))
    except DefinitionError as exc:
        return f"arguments invalid: {exc}"
    return "would run: " + " ".join(argv)
