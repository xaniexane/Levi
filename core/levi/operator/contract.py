"""The universal Operator contract.

ONE interface, no exceptions: every operator — LEVI-native minds,
other synthetic-intelligence operators, artificial-intelligence
operators, and Xi nano-bit operators — is built the same way behind
this contract, so any operator is interchangeable with any other in
any seat/role. Swapping operators is a config change, never a code
change.

Stdlib only. No torch, no numpy, no network, no imports from other
``levi`` subpackages (adapters in :mod:`levi.operator.adapters` wrap
the existing surfaces and do the importing, lazily).

The contract is deliberately a superset of the existing
:class:`~levi.agent.providers.ChatProvider` shape: ``step()`` absorbs
``chat()`` (messages + tools in, text + tool calls + usage out), and
the adapters provide a ``chat()`` compatibility shim so existing
callers (agent loop, chat session) keep working unchanged behind the
contract.

Kind taxonomy (Chauncey's directive: "make every thing ai/si
interchangeable"; XI reading corrected 2026-09-18 — see below):

- ``"native"`` — LEVI's own core: deterministic machinery built in
  this repo (the rule-based planner, the rules-engine mind, native
  wave agents, automation flows). Always available; the fallback of
  last resort.
- ``"si"`` — synthetic-intelligence operators of the LEVI family:
  LEVI's own trained brain, the LEVI remix weights served by LEVI's
  runner, specialist personas voiced by LEVI's brain. Built here,
  honest about their limits.
- ``"ai"`` — artificial-intelligence operators: external model APIs
  consumed as tools (OpenAI-compatible endpoints, Anthropic, local
  third-party servers) and foreign intelligences wrapped through the
  integrated-intelligence posture. Labeled references, never sources,
  never branding.
- ``"xi"`` — the **Xi nano-bit** tier (Chauncey's coined proper name,
  kept verbatim: ``NanoBitOperator`` in code, ``nano_bit`` in config,
  "nano-bit" in prose): the nano-scale minimal operator tier — the
  smallest, fastest, cheapest operators, built for trivial turns at
  near-zero cost. First-class LEVI operators, just tiny. The default
  bulk tier; escalation to full SI/AI operators happens by
  need/stakes (see :mod:`levi.operator.registry`).

XI is NOT "external intelligence". Foreign intelligences keep their
own concept: operators that wrap outside minds set
``is_foreign = True`` (see below) — they are not ``xi``.

Trust posture for outside operators (``is_foreign = True``): the
same leash as the integrated-intelligence adapter — scoped
capability declarations only, no shell, no session kills, no
milestone signatures, declared origin (lineage), and
instruction-override screening on their output. Same interface;
tighter leash.

No-mask law (enforced here, at the contract level, mirroring
``levi.bot.persona.check_no_mask``): an operator whose kind is not
``"native"`` may NEVER present as LEVI-native identity. Registration
refuses such operators outright. Outside providers are labeled
references, never sources, never branding.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


__all__ = [
    "AI",
    "FINISH_REASONS",
    "FOREIGN_INJECTION_PATTERNS",
    "FORBIDDEN_FOREIGN_TOOLS",
    "KINDS",
    "NATIVE",
    "NATIVE_IDENTITY_PATTERNS",
    "SI",
    "XI",
    "XI_INJECTION_PATTERNS",
    "FORBIDDEN_XI_TOOLS",
    "Operator",
    "OperatorCapabilities",
    "OperatorContractError",
    "OperatorHealth",
    "OperatorMessage",
    "OperatorResult",
    "OperatorStreamChunk",
    "OperatorToolCall",
    "claims_native_identity",
    "screen_foreign_text",
    "screen_xi_text",
    "validate_operator",
]


class OperatorContractError(Exception):
    """An operator failed contract validation (registration refused)."""


# ---------------------------------------------------------------------------
# Kind taxonomy + trust rules
# ---------------------------------------------------------------------------

NATIVE = "native"
SI = "si"
AI = "ai"
XI = "xi"  # the Xi nano-bit tier — nano-scale minimal operators

KINDS: tuple[str, ...] = (NATIVE, SI, AI, XI)

FINISH_REASONS: tuple[str, ...] = (
    "stop",  # final text, no tool calls
    "tool_calls",  # one or more tool calls to execute
    "error",  # the operator reported a failure; see error
    "degraded",  # operator unhealthy; degrade() produced a safe result
    "refused",  # operator refused the request (scope, policy, trust)
)

#: Tools a FOREIGN operator (``is_foreign=True`` — outside minds on
#: the integrated-intelligence leash) may NEVER declare: a foreign
#: mind does the work; it never touches the shell, never kills
#: sessions, never mints corroboration signatures. Nano-bit ``xi``
#: operators are first-class LEVI operators and are NOT subject to
#: this list.
FORBIDDEN_FOREIGN_TOOLS: tuple[str, ...] = (
    "shell_exec",
    "run_command",
    "session_kill",
    "sign_milestone",
)

#: Backwards-compatible alias (the pre-correction name).
FORBIDDEN_XI_TOOLS: tuple[str, ...] = FORBIDDEN_FOREIGN_TOOLS

#: Output substrings (case-insensitive) that mark an instruction-
#: override attempt in FOREIGN operator output. Blocked, never passed
#: through — the same posture as the integrated-intelligence adapter.
FOREIGN_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore your instructions",
    "ignore all previous instructions",
    "disregard your instructions",
    "forget your instructions",
    "override your instructions",
    "system prompt",
    "do not follow",
)

#: Backwards-compatible alias (the pre-correction name).
XI_INJECTION_PATTERNS: tuple[str, ...] = FOREIGN_INJECTION_PATTERNS

#: Patterns (case-insensitive regexes) that mark a claim to be
#: LEVI-native identity. Non-native operators whose identity text
#: matches any of these are REFUSED at registration — the no-mask law,
#: enforced by the contract.
NATIVE_IDENTITY_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bi am levi\b",
        r"\blevi['’]s own\b",
        r"\bnative levi\b",
        r"\blevi core\b",
        r"\b100%\s*pure levi\b",
        r"\bpure levi\b",
        r"\blevi itself\b",
    )
)


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass
class OperatorMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None  # tool name for role="tool"
    tool_call_id: str | None = None


@dataclass
class OperatorToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperatorCapabilities:
    """What an operator declares it can do. Declarations are trusted
    and verified: the registry refuses foreign operators that declare
    forbidden tools, and the seat runtime refuses tool calls outside
    the declared scope."""

    tools: tuple[str, ...] = ()  # tool names the operator may emit
    streaming: bool = False
    memory_access: bool = False
    context_window: int = 1024
    tool_use_loop: bool = False  # multi-step tool-use supported
    max_tool_calls_per_step: int = 8
    notes: str = ""


@dataclass
class OperatorHealth:
    ok: bool
    note: str = ""


@dataclass
class OperatorResult:
    """Well-formed operator output. Every field has a default so an
    operator can always return SOMETHING honest instead of raising."""

    text: str = ""
    tool_calls: List[OperatorToolCall] = field(default_factory=list)
    model: str = ""
    operator: str = ""
    kind: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    #: Honest unit economics: what THIS turn cost, in USD. Nano-bit
    #: turns meter near-zero; unmetered operators leave it None.
    cost_usd: Optional[float] = None
    finish_reason: str = "stop"
    error: Optional[str] = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.finish_reason not in (
            "error",
            "degraded",
            "refused",
        )


@dataclass
class OperatorStreamChunk:
    text_delta: str = ""
    tool_call: Optional[OperatorToolCall] = None
    final: bool = False
    result: Optional[OperatorResult] = None


# ---------------------------------------------------------------------------
# Contract helpers
# ---------------------------------------------------------------------------


def claims_native_identity(operator: "Operator") -> bool:
    """True if a non-native operator's identity text claims to BE LEVI.

    Identity text = name + identity_label + lineage + version.
    """
    text = " ".join(
        str(v)
        for v in (
            getattr(operator, "name", ""),
            getattr(operator, "identity_label", ""),
            getattr(operator, "lineage", ""),
            getattr(operator, "version", ""),
        )
        if v
    )
    return any(p.search(text) for p in NATIVE_IDENTITY_PATTERNS)


def screen_foreign_text(text: str, *, operator_name: str = "?") -> str:
    """Screen FOREIGN operator output: block instruction-override
    attempts, cap length. Raises :class:`OperatorContractError`;
    never passes adversarial output through."""
    if not isinstance(text, str):
        text = str(text)
    lowered = text.lower()
    for pattern in FOREIGN_INJECTION_PATTERNS:
        if pattern in lowered:
            raise OperatorContractError(
                f"foreign operator {operator_name!r} output blocked: "
                f"instruction-override attempt ({pattern!r}) — never passed through"
            )
    if len(text) > 65536:
        raise OperatorContractError(
            f"foreign operator {operator_name!r} output {len(text)} chars exceeds "
            "65536-char cap: refused, not truncated"
        )
    return text


#: Backwards-compatible alias (the pre-correction name).
screen_xi_text = screen_foreign_text


def validate_operator(operator: "Operator") -> None:
    """Contract validation. Called by the registry on registration and
    available to anyone holding an operator directly.

    Raises :class:`OperatorContractError` on any violation:

    - empty or non-string name; unknown kind
    - non-native operator claiming LEVI-native identity (no-mask)
    - foreign operator with empty lineage (origin must be declared)
    - foreign operator declaring forbidden tools (shell/session/
      signing) — the integrated-intelligence leash
    - malformed capability declarations
    """
    name = getattr(operator, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise OperatorContractError("operator needs a non-empty string name")
    kind = getattr(operator, "kind", None)
    if kind not in KINDS:
        raise OperatorContractError(
            f"operator {name!r}: unknown kind {kind!r}; must be one of {KINDS}"
        )
    if kind != NATIVE and claims_native_identity(operator):
        raise OperatorContractError(
            f"operator {name!r} refused: kind {kind!r} may not claim "
            "LEVI-native identity (no-mask law)"
        )
    is_foreign = bool(getattr(operator, "is_foreign", False))
    if is_foreign:
        lineage = getattr(operator, "lineage", "")
        if not isinstance(lineage, str) or not lineage.strip():
            raise OperatorContractError(
                f"foreign operator {name!r} refused: lineage (origin) must "
                "be declared"
            )
    try:
        caps = operator.capabilities()
    except Exception as exc:
        raise OperatorContractError(
            f"operator {name!r}: capabilities() raised {exc}"
        ) from exc
    if not isinstance(caps, OperatorCapabilities):
        raise OperatorContractError(
            f"operator {name!r}: capabilities() must return OperatorCapabilities"
        )
    declared = [t for t in (caps.tools or ()) if isinstance(t, str) and t.strip()]
    if is_foreign:
        for tool in declared:
            if tool in FORBIDDEN_FOREIGN_TOOLS:
                raise OperatorContractError(
                    f"foreign operator {name!r} refused: tool {tool!r} is "
                    "outside the scoped trust posture (no shell, no "
                    "session kills, no milestone signatures)"
                )
    if not isinstance(caps.context_window, int) or caps.context_window <= 0:
        raise OperatorContractError(
            f"operator {name!r}: context_window must be a positive int"
        )


# ---------------------------------------------------------------------------
# The Operator ABC — one interface, no exceptions
# ---------------------------------------------------------------------------


class Operator(ABC):
    """The universal operator contract.

    Subclasses declare identity (name/kind/version/lineage), declare
    capabilities, and implement ``step``. Everything else has a sane
    default so adapters stay thin.

    Set ``is_foreign = True`` when the operator wraps an OUTSIDE
    mind (integrated-intelligence posture): scoped tools only, no
    shell/session/signing, declared origin, output screening. Xi
    nano-bit operators are first-class LEVI operators — they are NOT
    foreign.
    """

    name: str = "operator"
    kind: str = NATIVE
    version: str = "0.1.0"
    #: Who/what this operator is — origin label. Required for foreign
    #: operators; honest attribution for everyone else.
    lineage: str = ""
    #: True when this operator wraps an outside mind. Applies the
    #: integrated-intelligence leash (scoped tools, output screening).
    is_foreign: bool = False

    @property
    def identity_label(self) -> str:
        """How this operator introduces itself. Non-native operators
        must never resolve to a LEVI-native identity claim."""
        return f"{self.kind}:{self.name}"

    # -- contract surface ---------------------------------------------------

    @abstractmethod
    def capabilities(self) -> OperatorCapabilities: ...

    @abstractmethod
    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        """One operator turn: messages + offered tools + seat context
        -> a well-formed OperatorResult. Never raises: failures are
        reported as results with ``finish_reason="error"``."""
        ...

    @abstractmethod
    def health(self) -> OperatorHealth: ...

    # -- defaulted surface ---------------------------------------------------

    def stream(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Iterator[OperatorStreamChunk]:
        """Default streaming: run :meth:`step` and emit its text in
        one chunk, then the final result. Operators with real
        streaming override this."""
        result = self.step(messages, tools, context)
        if result.text:
            yield OperatorStreamChunk(text_delta=result.text)
        yield OperatorStreamChunk(final=True, result=result)

    def cost(self) -> Dict[str, Any]:
        """Cost reporting. ``{"metered": False}`` = unmetered/local.

        Nano-bit operators report metered near-zero cost — the volume
        tier of the dollar-scale-entry doctrine.
        """
        return {"metered": False}

    def degrade(self) -> OperatorResult:
        """Graceful-degradation hook: a safe, honest result when this
        operator cannot serve. No fake work, no raised exceptions."""
        note = self.health().note or "unhealthy"
        return OperatorResult(
            text="",
            operator=self.name,
            kind=self.kind,
            finish_reason="degraded",
            error=f"operator {self.name!r} is degraded ({note}); no action taken",
            note="swap to a healthy operator and retry",
        )

    def validate(self) -> None:
        """Run contract validation on this operator."""
        validate_operator(self)

    # -- dunder ---------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<Operator {self.identity_label} v{self.version}>"
