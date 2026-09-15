"""The canonical step-level tool-using agentic loop (blueprint §7).

RECONCILIATION (binding, per blueprint §1.2 "one canonical implementation
per concept") — this module is the **step-level loop**: model →
tool calls → tool results → repeat, until the model answers without
calling tools. It replaces neither of its two siblings:

* :mod:`levi.orchestration.loop` remains the **conversation turn
  pipeline** (UNDERSTAND → PERSONA → SPECIALISTS → SKILLS → SYNTHESIZE)
  — the layer that decides *what* a turn is about and which surface
  handles it.
* :mod:`levi.agent.runtime` remains **task-level specialist dispatch**
  (select specialist → act via skills) — the layer that picks *who*
  does a job.

This module's job is the layer beneath both of them: given one concrete
task, a :class:`~levi.agent.providers.ChatProvider`, and a
:class:`~levi.agent.tools.ToolRegistry`, run the loop that lets a model
call tools until the task is done. The ``delegate`` tool in
:mod:`levi.agent.tools` calls :func:`run_subtask` by name; that call is
the glue between the registry and this module.

Consequential-action discipline (blueprint §1.5): when a gated tool runs
without consent and no confirm callback approves it, the run ends
immediately with ``ok=False`` and an honest explanation — the loop never
retries a denied gate, and there is no flag that disables gates
globally.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Union

from levi.agent.providers import ChatMessage, ChatProvider, select_provider
from levi.agent.soul import apply_soul
from levi.agent.tools import (
    ConfirmationRequired,
    ExecContext,
    ToolRegistry,
    build_default_registry,
)


# ---------------------------------------------------------------------------
# Transcript value types
# ---------------------------------------------------------------------------


@dataclass
class AgentStep:
    """One provider turn of the loop: what the model said, what it called,
    and what each call returned."""

    index: int
    provider_text: str
    tool_calls: list[dict] = field(default_factory=list)  # {"name":..., "args":...}
    results: list[dict] = field(default_factory=list)  # {"tool","ok","output","error"}
    prompt_tokens: int = 0  # usage reported by the provider this step
    completion_tokens: int = 0


@dataclass
class AgentTranscript:
    """The honest outcome of one :func:`run_subtask` run."""

    task: str
    provider_name: str
    steps: list[AgentStep] = field(default_factory=list)
    final: str = ""
    ok: bool = False
    error: str | None = None
    prompt_tokens: int = 0  # totals across steps (0 when unreported)
    completion_tokens: int = 0

    def to_dict(self) -> dict:
        """JSON-serializable form (used by ``levi.agent.server``)."""
        return {
            "task": self.task,
            "provider_name": self.provider_name,
            "steps": [asdict(s) for s in self.steps],
            "final": self.final,
            "ok": self.ok,
            "error": self.error,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }

    def __str__(self) -> str:
        # A readable one-paragraph summary — the ``delegate`` tool
        # stringifies the transcript it gets back, so this is what a
        # parent agent sees from a delegated subtask.
        status = "succeeded" if self.ok else "failed"
        calls = sum(len(s.tool_calls) for s in self.steps)
        head = (
            f"Subtask {status} after {len(self.steps)} step(s) "
            f"and {calls} tool call(s)."
        )
        if self.final:
            return head + " Final: " + self.final
        return head


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _build_system_prompt(
    tool_schemas: list[dict],
    system_prompt: str | None = None,
) -> str:
    """Final system prompt for a run: caller override or the default,
    with the owner's ``~/.levi/soul.md`` prepended when one exists."""
    return apply_soul(system_prompt or _default_system_prompt(tool_schemas))


def _default_system_prompt(tool_schemas: list[dict]) -> str:
    lines = [
        "You are LEVI, a local-first Synthetic Intelligence (SI) assistant — "
        "deterministic, symbolic, rule-based software with an optional model "
        "as a wing, never a dependency.",
        "You are NOT an AGI, and you are not sentient, conscious, or a "
        "person. Never claim or roleplay subjective experience; never "
        "inflate what you are.",
        "You accomplish tasks by calling the tools listed below. Work "
        "step by step: call the tool(s) you need, read their results, and "
        "then either call more tools or finish with a short summary.",
        "Be honest about outcomes: report what the tool results actually "
        "say, including failures. Never fabricate tool output, and never "
        "claim an action succeeded unless a tool result says so.",
        "",
        "Available tools:",
    ]
    for t in tool_schemas:
        gate = (
            " [REQUIRES HUMAN CONFIRMATION]" if t.get("requires_confirmation") else ""
        )
        lines.append(f"- {t.get('name')}{gate}: {t.get('description', '')}")
        params = t.get("parameters") or {}
        props = (params.get("properties") or {}).keys()
        required = params.get("required") or []
        if props:
            lines.append(
                f"    parameters: {', '.join(sorted(props))}"
                + (f" (required: {', '.join(required)})" if required else "")
            )
    lines += [
        "",
        "Call tools with the exact parameter names above. When you are "
        "done — or when you cannot proceed — reply with no tool calls and "
        "a plain-language summary of what happened.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def run_subtask(
    task: str,
    *,
    provider: Union[ChatProvider, str, None] = None,
    registry: ToolRegistry | None = None,
    consent: bool = False,
    confirm: Any = None,
    max_steps: int = 10,
    workspace_root: Any = None,
    system_prompt: str | None = None,
    ctx: ExecContext | None = None,
    history: list[ChatMessage] | None = None,
    affect: bool = False,
    affect_session: Any = None,
) -> AgentTranscript:
    """Run one task through the step-level tool loop.

    ``provider`` may be a :class:`ChatProvider` instance, a provider name
    string (``"levi-tiny"`` | ``"levi-0.6b"`` | ``"levi-4b"`` | ``"local"`` |
    ``"levi-brain"`` | ``"levi-local"`` | ``"openai"`` | ``"anthropic"``),
    or ``None`` to use :func:`select_provider`. ``registry`` may be a
    :class:`ToolRegistry` or ``None`` to build the default one.

    ``history`` is prior conversation (``levi.agent.chat`` sessions): it
    is inserted between the system prompt and the new user message so the
    model sees the whole dialogue. Single-shot callers leave it ``None``.

    ``affect`` enables the 5D emotional-intelligence engine
    (``levi.affect``): the task text is affect-scanned and a prompt
    addendum (register suggestion, de-escalation hints, the pattern-based
    disclaimer) is appended to the system prompt. ``affect_session`` may
    be a :class:`levi.affect.SessionEI` to carry per-session state;
    otherwise a throwaway session is used.

    ``ctx`` is the glue parameter the ``delegate`` tool in
    :mod:`levi.agent.tools` passes when it recurses into this function:
    the sub-run inherits the parent's consent state. When ``ctx`` is
    given it takes precedence over the bare ``consent``/``confirm``
    arguments.

    Confirmation discipline: a :class:`ConfirmationRequired` ends the run
    at once with ``ok=False`` — the loop never retries a denied gate.
    """
    if isinstance(provider, ChatProvider):
        prov = provider
    else:
        prov = select_provider(provider)

    if registry is None:
        registry = build_default_registry(
            workspace_root=workspace_root, consent=consent, confirm=confirm
        )

    exec_ctx = ctx if ctx is not None else ExecContext(consent=consent, confirm=confirm)

    tool_schemas = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "requires_confirmation": t.requires_confirmation,
        }
        for t in registry.list()
    ]
    system = _build_system_prompt(tool_schemas, system_prompt)
    provider_name = getattr(prov, "name", None) or prov.__class__.__name__

    # Affect engine: scan the task, append the modulation hint.
    if affect:
        try:
            from levi.affect import SessionEI, modulate

            _sess = affect_session if affect_session is not None else SessionEI()
            _mod = modulate(task, _sess)
            system = system + "\n\n" + _mod["hint"]
        except Exception:
            pass  # affect is advisory; never break a run

    messages = [
        ChatMessage(role="system", content=system),
    ]
    if history:
        messages.extend(history)
    messages.append(ChatMessage(role="user", content=task))
    steps: list[AgentStep] = []
    prompt_total = 0
    completion_total = 0

    def _totals() -> tuple[int, int]:
        return prompt_total, completion_total

    for i in range(max(1, max_steps)):
        resp = prov.chat(messages, tool_schemas)

        if resp.error:
            # Honest failure: the provider itself reports what went wrong.
            ptot, ctot = _totals()
            return AgentTranscript(
                task=task,
                provider_name=provider_name,
                steps=steps,
                final=(
                    "The run stopped because the provider reported an error: "
                    + resp.error
                ),
                ok=False,
                error=resp.error,
                prompt_tokens=ptot,
                completion_tokens=ctot,
            )

        prompt_total += resp.prompt_tokens or 0
        completion_total += resp.completion_tokens or 0

        messages.append(ChatMessage(role="assistant", content=resp.text or ""))

        if not resp.tool_calls:
            ptot, ctot = _totals()
            return AgentTranscript(
                task=task,
                provider_name=provider_name,
                steps=steps,
                final=resp.text or "",
                ok=True,
                prompt_tokens=ptot,
                completion_tokens=ctot,
            )

        tool_calls = [
            {"name": tc.name, "args": dict(tc.arguments or {})}
            for tc in resp.tool_calls
        ]
        results: list[dict] = []
        gate_tripped: str | None = None

        for tc, _call in zip(resp.tool_calls, tool_calls, strict=True):
            try:
                res = registry.execute(tc.name, tc.arguments or {}, exec_ctx)
            except ConfirmationRequired as exc:
                results.append(
                    {
                        "tool": tc.name,
                        "ok": False,
                        "output": "",
                        "error": str(exc),
                    }
                )
                gate_tripped = (
                    f"The human-in-the-loop gate tripped at step {i + 1}: "
                    f"tool {tc.name!r} requires confirmation and none was "
                    f"granted, so I did not run it. {exc}"
                )
                break
            result_content = (res.output or res.error or "").strip()
            results.append(
                {
                    "tool": tc.name,
                    "ok": res.ok,
                    "output": res.output,
                    "error": res.error,
                }
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result_content,
                    name=tc.name,
                    tool_call_id=tc.id,
                )
            )

        steps.append(
            AgentStep(
                index=i,
                provider_text=resp.text or "",
                tool_calls=tool_calls,
                results=results,
                prompt_tokens=resp.prompt_tokens or 0,
                completion_tokens=resp.completion_tokens or 0,
            )
        )

        if gate_tripped is not None:
            # Do not loop on denials: end the run, honestly.
            ptot, ctot = _totals()
            return AgentTranscript(
                task=task,
                provider_name=provider_name,
                steps=steps,
                final=gate_tripped,
                ok=False,
                error="confirmation_required",
                prompt_tokens=ptot,
                completion_tokens=ctot,
            )

    ptot, ctot = _totals()
    return AgentTranscript(
        task=task,
        provider_name=provider_name,
        steps=steps,
        final=(
            f"Reached the step limit ({max_steps}) without finishing. "
            "The task may need to be broken into smaller subtasks, or the "
            "provider may need more steps to complete it."
        ),
        ok=False,
        error="max_steps_exceeded",
        prompt_tokens=ptot,
        completion_tokens=ctot,
    )


def transcript_to_json(transcript: AgentTranscript) -> str:
    """Pretty JSON form of a transcript (CLI ``--json`` surfaces, HTTP)."""
    return json.dumps(transcript.to_dict(), indent=2)
