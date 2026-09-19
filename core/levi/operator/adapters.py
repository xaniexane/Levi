"""Adapters: wrap the existing surfaces behind the Operator contract.

Nothing here is rewritten — each adapter holds an existing object and
translates the contract surface onto it:

- :class:`ChatProviderAdapter` — wraps
  :class:`~levi.agent.providers.ChatProvider` subclasses
  (``LocalProvider``, ``OpenAICompatibleProvider``,
  ``AnthropicProvider``, ``NativeBrainProvider``,
  ``LocalModelProvider``). Carries a ``chat()`` compatibility shim so
  existing callers (agent loop, chat session) work unchanged behind
  the contract.
- :class:`NanoBitOperator` — the reference Xi **nano-bit** tier
  operator (Chauncey's coined proper name, kept verbatim):
  nano-scale minimal, smallest/fastest/cheapest, deterministic,
  for trivial turns at near-zero cost. Non-trivial work is refused
  with an escalation hint, not faked.
- :class:`MindAdapter` — wraps council minds
  (``NativeBrainMind``, ``RulesEngineMind``, ``SpecialistsMind``).
- :class:`AutomationRunnerAdapter` — wraps the automation flows
  engine (``run_flow``) in dry-run by default; the flows package is
  NEVER edited.

All cross-package imports are lazy so ``levi.operator`` stays
importable (and stdlib-only) on its own. ``levi.agent.providers``
is imported at module level — it is stdlib-only with no torch.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from levi.agent.providers import ChatMessage, ChatProvider

from .contract import (
    NATIVE,
    SI,
    XI,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)

__all__ = [
    "AutomationRunnerAdapter",
    "ChatProviderAdapter",
    "MindAdapter",
    "NanoBitOperator",
    "as_operator",
    "chat_provider_operator",
    "mind_operator",
]

# Near-zero cost of one nano-bit turn (USD). Honest metering for the
# volume tier of the dollar-scale-entry doctrine.
NANO_BIT_COST_USD = 0.000001


def _to_chat_messages(messages: List[OperatorMessage]) -> List[ChatMessage]:
    return [
        ChatMessage(
            role=m.role,
            content=m.content or "",
            name=m.name,
            tool_call_id=m.tool_call_id,
        )
        for m in messages
    ]


# ---------------------------------------------------------------------------
# ChatProviderAdapter
# ---------------------------------------------------------------------------


class ChatProviderAdapter(Operator):
    """An existing ChatProvider behind the Operator contract."""

    def __init__(
        self,
        provider: ChatProvider,
        *,
        kind: str = SI,
        lineage: str = "",
        context_window: int = 8192,
        tools: tuple[str, ...] = (),
        tool_use_loop: bool = True,
    ) -> None:
        if not isinstance(provider, ChatProvider):
            raise OperatorContractError(
                "ChatProviderAdapter needs a ChatProvider, got "
                f"{type(provider).__name__}"
            )
        self._provider = provider
        self.name = getattr(provider, "name", None) or provider.__class__.__name__
        self.kind = kind
        self.lineage = lineage or f"levi:chat-provider:{self.name}"
        self._context_window = int(context_window)
        self._tools = tuple(tools)
        self._tool_use_loop = bool(tool_use_loop)

    @property
    def provider(self) -> ChatProvider:
        return self._provider

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=self._tools,
            streaming=False,
            memory_access=False,
            context_window=self._context_window,
            tool_use_loop=self._tool_use_loop,
            notes=f"adapter over ChatProvider {self.name!r}",
        )

    def health(self) -> OperatorHealth:
        try:
            ok = bool(self._provider.is_available())
        except Exception as exc:
            return OperatorHealth(ok=False, note=f"is_available() raised: {exc}")
        return OperatorHealth(
            ok=ok,
            note=f"provider {self.name!r} available"
            if ok
            else f"provider {self.name!r} unavailable",
        )

    def cost(self) -> Dict[str, Any]:
        return {"metered": False, "note": "provider cost not metered by LEVI"}

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        try:
            resp = self._provider.chat(_to_chat_messages(messages), tools or [])
        except Exception as exc:  # contract: never raise
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                finish_reason="error",
                error=f"provider {self.name!r} raised {type(exc).__name__}: {exc}",
            )
        from .contract import OperatorToolCall

        calls = [
            OperatorToolCall(id=c.id, name=c.name, arguments=dict(c.arguments or {}))
            for c in (resp.tool_calls or [])
        ]
        return OperatorResult(
            text=resp.text or "",
            tool_calls=calls,
            model=resp.model or self.name,
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            finish_reason="tool_calls" if calls else "stop",
            error=resp.error,
        )

    # -- compatibility shim -------------------------------------------------
    # Existing callers (agent/loop.py, agent/chat.py) call
    # ``provider.chat(messages, tools)`` and read ``ChatResponse``.
    # The shim lets them sit behind the contract with a one-line
    # change; ``step()`` remains the canonical surface.

    def chat(self, messages: List[ChatMessage], tools: List[Dict[str, Any]]):  # noqa: ANN201
        """ChatProvider-compatible entry point over :meth:`step`."""
        op_messages = [
            OperatorMessage(
                role=m.role,
                content=m.content or "",
                name=m.name,
                tool_call_id=m.tool_call_id,
            )
            for m in messages
        ]
        result = self.step(op_messages, tools or [], {})
        from levi.agent.providers import ChatResponse, ProviderToolCall

        return ChatResponse(
            text=result.text,
            tool_calls=[
                ProviderToolCall(id=c.id, name=c.name, arguments=dict(c.arguments))
                for c in result.tool_calls
            ],
            model=result.model,
            provider=self.name,
            latency_ms=result.latency_ms,
            error=result.error,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )


def chat_provider_operator(
    provider: ChatProvider, *, kind: str = SI
) -> ChatProviderAdapter:
    """Wrap a ChatProvider as an Operator."""
    return ChatProviderAdapter(provider, kind=kind)


def as_operator(obj: Any) -> Operator:
    """Coerce to an Operator: Operators pass through, ChatProviders
    get wrapped, anything else raises."""
    if isinstance(obj, Operator):
        return obj
    if isinstance(obj, ChatProvider):
        return ChatProviderAdapter(obj)
    raise OperatorContractError(
        f"cannot use {type(obj).__name__} as an operator "
        "(need an Operator or a ChatProvider)"
    )


# ---------------------------------------------------------------------------
# NanoBitOperator — the reference Xi nano-bit tier operator
# ---------------------------------------------------------------------------

_TRIVIAL_REPLIES: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), r)
    for p, r in (
        (
            r"^(hi|hey|hello|yo|sup)\b",
            "Hey. I'm here — what do you need?",
        ),
        (
            r"^(good (morning|afternoon|evening))\b",
            "Good to see you. What's on the list?",
        ),
        (
            r"^(thanks?|thank you|thx|ty)\b",
            "Anytime.",
        ),
        (
            r"^(ok|okay|k|sure|got it|cool|nice)\b",
            "Got it.",
        ),
        (
            r"^(bye|goodbye|see you|later)\b",
            "Later.",
        ),
    )
)

_ESCALATION_HINT = (
    "That's beyond a nano-bit turn — I'm the tiny tier, built for "
    "trivial exchanges at near-zero cost. Escalate me to a full "
    "operator (si/ai) for this one."
)


class NanoBitOperator(Operator):
    """The Xi **nano-bit** tier: nano-scale minimal operator.

    Chauncey's coined proper name — kept verbatim (``NanoBitOperator``
    in code, ``nano_bit`` in config, "nano-bit" in prose). The
    smallest, fastest, cheapest operators: deterministic, no tools,
    no memory, 1k context. Trivial turns (greetings, thanks, acks)
    are answered directly; anything else is REFUSED with an
    escalation hint — never faked, never guessed.

    First-class LEVI operator (``is_foreign=False``); the default
    bulk tier. Cost is metered honestly at near-zero per turn.
    """

    name = "nano-bit"
    kind = XI
    version = "0.1.0"
    lineage = "levi:nano-bit"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=1024,
            tool_use_loop=False,
            notes=(
                "Xi nano-bit tier: deterministic trivial-turn handler; "
                "no tools, no memory, refuses non-trivial work with an "
                "escalation hint"
            ),
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="nano-bit ready (deterministic)")

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": True,
            "unit": "usd",
            "per_step_usd": NANO_BIT_COST_USD,
            "tier": "nano-bit",
            "note": "near-zero bulk tier (dollar-scale-entry doctrine)",
        }

    def _handle(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return "I'm here — what do you need?"
        for pattern, reply in _TRIVIAL_REPLIES:
            if pattern.match(text):
                return reply
        return None

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        user_texts = [m.content or "" for m in messages if m.role == "user"]
        text = user_texts[-1] if user_texts else ""
        reply = self._handle(text)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if reply is None:
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=latency_ms,
                cost_usd=NANO_BIT_COST_USD,
                finish_reason="refused",
                error="non-trivial turn: outside the nano-bit tier",
                note=_ESCALATION_HINT,
            )
        return OperatorResult(
            text=reply,
            operator=self.name,
            kind=self.kind,
            latency_ms=latency_ms,
            cost_usd=NANO_BIT_COST_USD,
            finish_reason="stop",
            note="nano-bit trivial turn",
        )


# ---------------------------------------------------------------------------
# MindAdapter — council minds behind the contract
# ---------------------------------------------------------------------------


class MindAdapter(Operator):
    """A council mind (generate/review) behind the Operator contract.

    ``step()`` runs the mind's ``generate(task, tests_hint)``: the
    task is the last user message; ``context["tests_hint"]`` (or the
    system message) supplies the tests hint. The mind's honesty notes
    ride on ``OperatorResult.note``.
    """

    def __init__(self, seat_id: str, *, kind: str = NATIVE) -> None:
        from levi.council import minds as _minds

        self._mind = _minds.mind_for(seat_id)
        self.name = seat_id
        self.kind = kind
        self.version = "0.1.0"
        self.lineage = f"levi:council-mind:{seat_id}"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=8192,
            tool_use_loop=False,
            notes=f"adapter over council mind {self.name!r} (generate path)",
        )

    def health(self) -> OperatorHealth:
        try:
            ok = bool(self._mind.is_available())
            note = self._mind.availability_note()
        except Exception as exc:
            return OperatorHealth(ok=False, note=f"availability check raised: {exc}")
        return OperatorHealth(ok=ok, note=note)

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        user_texts = [m.content or "" for m in messages if m.role == "user"]
        task = user_texts[-1] if user_texts else ""
        system_texts = [m.content or "" for m in messages if m.role == "system"]
        tests_hint = str((context or {}).get("tests_hint") or " ".join(system_texts))
        try:
            res = self._mind.generate(task, tests_hint)
        except Exception as exc:  # contract: never raise
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                finish_reason="error",
                error=f"mind {self.name!r} raised {type(exc).__name__}: {exc}",
            )
        if not res.ok:
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                finish_reason="error",
                error=res.error or f"mind {self.name!r} failed",
                note=res.note,
            )
        return OperatorResult(
            text=res.text or "",
            model=res.model or self.name,
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note=res.note,
        )


def mind_operator(seat_id: str, *, kind: str = NATIVE) -> MindAdapter:
    """Wrap a council seat's mind as an Operator."""
    return MindAdapter(seat_id, kind=kind)


# ---------------------------------------------------------------------------
# AutomationRunnerAdapter — flows engine behind the contract (wrap only)
# ---------------------------------------------------------------------------


class AutomationRunnerAdapter(Operator):
    """The automation flows engine behind the Operator contract.

    The automation package is NEVER edited here. ``step()`` runs the
    flow definition from ``context["flow"]`` via ``run_flow`` —
    DRY-RUN by default (nothing executes, everything is recorded);
    set ``context["dry_run"] = False`` only with explicit approval.
    The last user message becomes the trigger payload.
    """

    name = "automation-runner"
    kind = NATIVE
    version = "0.1.0"
    lineage = "levi:automation:flows"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=4096,
            tool_use_loop=False,
            notes="adapter over automation run_flow (dry-run default)",
        )

    def health(self) -> OperatorHealth:
        try:
            from levi.automation import flows as _flows

            _flows.ensure_builtin_nodes()
        except Exception as exc:
            return OperatorHealth(ok=False, note=f"flows engine unavailable: {exc}")
        return OperatorHealth(ok=True, note="flows engine ready (dry-run default)")

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        context = context or {}
        flow = context.get("flow")
        if not isinstance(flow, dict):
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                finish_reason="refused",
                error="no flow definition in context['flow']",
                note="pass a validated flow definition to run it",
            )
        user_texts = [m.content or "" for m in messages if m.role == "user"]
        trigger_text = user_texts[-1] if user_texts else ""
        try:
            from levi.automation import flows as _flows

            receipt = _flows.run_flow(
                flow,
                context={"trigger_text": trigger_text},
                dry_run=bool(context.get("dry_run", True)),
            )
        except Exception as exc:  # contract: never raise
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                finish_reason="error",
                error=f"run_flow raised {type(exc).__name__}: {exc}",
            )
        return OperatorResult(
            text=str(receipt),
            model=self.name,
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="flow run (dry_run=%s)" % bool(context.get("dry_run", True)),
        )
