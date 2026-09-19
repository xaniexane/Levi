"""Operator registry, sessions, escalation routing, and seat resolution.

Config-driven selection: an operator is chosen by NAME from config,
never hardcoded. Seats (chat, council seats, agent slots, automation
nodes) map to operator names through :func:`resolve_for_seat`, so
swapping operators is a config change, never a code change.

Escalation routing (the Xi nano-bit doctrine): bulk trivial turns
default to nano-bit operators (smallest, fastest, cheapest —
near-zero cost); the router escalates to full SI/AI operators by
need/stakes via :func:`resolve_for_task`. Twin-pair seats (primary +
independent verifier) are supported STRUCTURALLY through
:class:`TwinPair` / :func:`resolve_twin` under all three pending
options — off (switchable only), on_demand (hybrid), always
(twins always-on). Chauncey ratified ``"on_demand"`` (hybrid) on
2026-09-18; full inverse-twin merge/judge semantics stay GATED (the
user judges hard cases; no automatic inverse merge).

Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .contract import (
    AI,
    NATIVE,
    SI,
    Operator,
    OperatorContractError,
    OperatorMessage,
    OperatorResult,
    validate_operator,
)

__all__ = [
    "DEFAULT_SEAT_MAP",
    "HIGH_STAKES_TOOLS",
    "KNOWN_SEATS",
    "OperatorRegistry",
    "OperatorSession",
    "TWIN_MODES",
    "TwinPair",
    "assess_stakes",
    "default_registry",
    "escalate",
    "register_builtin_operators",
    "resolve_for_seat",
    "resolve_for_task",
    "resolve_twin",
    "scoped_step",
]

# ---------------------------------------------------------------------------
# Seat map — seats accept any operator by name/config
# ---------------------------------------------------------------------------

#: Sane defaults. Every value is an operator NAME; override any of them
#: in config under the "seats" key.
DEFAULT_SEAT_MAP: Dict[str, str] = {
    "chat": "levi-brain",  # conversational surface (falls back honestly)
    "loop": "levi-brain",  # agentic-loop worker
    "bot.default": "local",  # bot services: always-available rules core
    "council.native-brain": "native-brain",
    "council.rules-engine": "rules-engine",
    "council.specialists": "specialists",
    "agent.default": "local",
    "automation.default": "rules-engine",
    "growth.default": "local",
}

KNOWN_SEATS: tuple[str, ...] = tuple(sorted(DEFAULT_SEAT_MAP))

#: Tier defaults: the bulk tier is nano-bit; escalation targets full
#: operators. Override in config under the "tiers" key.
DEFAULT_TIERS: Dict[str, str] = {
    "nano_bit": "nano-bit",
    "full": "levi-brain",
}


def resolve_for_seat(seat_id: str, config: Optional[Dict[str, Any]] = None) -> str:
    """Map a seat to an operator name from config, with sane defaults.

    ``config`` may carry ``{"seats": {seat_id: operator_name}}`` or a
    flat ``{"operator": name}`` override. Unknown seats fall back to
    the ``agent.default`` operator.
    """
    config = config or {}
    seats = config.get("seats") or {}
    if seat_id in seats and seats[seat_id]:
        return str(seats[seat_id])
    if "operator" in config and config["operator"]:
        return str(config["operator"])
    return DEFAULT_SEAT_MAP.get(seat_id, DEFAULT_SEAT_MAP["agent.default"])


def tier_operator(tier: str, config: Optional[Dict[str, Any]] = None) -> str:
    """Operator name for a tier (``"nano_bit"`` | ``"full"``)."""
    tiers = (config or {}).get("tiers") or {}
    if tier in tiers and tiers[tier]:
        return str(tiers[tier])
    return DEFAULT_TIERS.get(tier, DEFAULT_TIERS["nano_bit"])


# ---------------------------------------------------------------------------
# Escalation routing — nano-bit by default, full operators by stakes
# ---------------------------------------------------------------------------

#: Tools that always escalate past the nano-bit tier.
HIGH_STAKES_TOOLS: tuple[str, ...] = (
    "shell_exec",
    "run_command",
    "sign_milestone",
    "session_kill",
)

_HIGH_STAKES_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bpay\b",
        r"\bpayment\b",
        r"\btransfer\b.*\b(money|funds)\b",
        r"\bsign\b",
        r"\bproduction\b",
        r"\bdeploy\b",
        r"\bdelete\b",
        r"\blegal\b",
        r"\bcontract\b",
    )
)

_TRIVIAL_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^(hi|hey|hello|yo|sup|good (morning|afternoon|evening))\b[!. ]*$",
        r"^(thanks?|thank you|thx|ty)\b[!. ]*$",
        r"^(ok|okay|k|sure|yes|yeah|yep|no|nope|got it|cool|nice)\b[!. ]*$",
        r"^(bye|goodbye|see you|later)\b[!. ]*$",
    )
)


def assess_stakes(
    messages: List[OperatorMessage],
    tools: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Assess task stakes: ``"trivial"`` | ``"normal"`` | ``"high"``.

    - ``context["stakes"]`` wins when explicitly set.
    - High: a high-stakes tool is offered, or the text matches
      high-stakes patterns (money, signing, production, deletes).
    - Trivial: no tools offered, short user text matching trivial
      patterns (greetings, thanks, acks) or very short plain text.
    - Normal: everything else.
    """
    context = context or {}
    explicit = str(context.get("stakes") or "").strip().lower()
    if explicit in ("trivial", "normal", "high"):
        return explicit

    offered = [
        str(t.get("name", ""))
        for t in (tools or [])
        if isinstance(t, dict) and t.get("name")
    ]
    if any(t in HIGH_STAKES_TOOLS for t in offered):
        return "high"

    user_texts = [m.content or "" for m in messages if m.role == "user"]
    text = " ".join(user_texts).strip()
    if any(p.search(text) for p in _HIGH_STAKES_PATTERNS):
        return "high"
    if not offered and text:
        if any(p.match(text) for p in _TRIVIAL_PATTERNS):
            return "trivial"
        if len(text) <= 24 and "?" not in text:
            return "trivial"
    return "normal"


def escalate(
    seat_id: str,
    stakes: str,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Escalation decision for a seat at given stakes -> operator name.

    - ``"trivial"`` -> the nano-bit tier (bulk: smallest, fastest,
      cheapest; routing prefers it on cost grounds).
    - ``"normal"`` -> the seat's configured operator.
    - ``"high"`` -> the full tier (escalates PAST nano-bit; never
      returns the nano-bit operator).
    """
    config = config or {}
    if stakes == "trivial":
        return tier_operator("nano_bit", config)
    if stakes == "high":
        full = tier_operator("full", config)
        nano = tier_operator("nano_bit", config)
        if full == nano:
            # Never escalate "past" nano-bit into nano-bit: fall back
            # to the seat default instead.
            return resolve_for_seat(seat_id, config)
        return full
    return resolve_for_seat(seat_id, config)


def resolve_for_task(
    seat_id: str,
    messages: List[OperatorMessage],
    tools: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Route a task to an operator name: assess stakes, then escalate.

    Trivial turns resolve to the nano-bit tier; high-stakes tasks
    escalate past it. Set ``config["escalation"]["enabled"] = False``
    to bypass (plain seat resolution).
    """
    config = config or {}
    esc = config.get("escalation") or {}
    if esc.get("enabled") is False:
        return resolve_for_seat(seat_id, config)
    stakes = assess_stakes(messages, tools, context)
    return escalate(seat_id, stakes, config)


# ---------------------------------------------------------------------------
# Twin-pair seats — STRUCTURAL ONLY (merge/judge GATED)
# ---------------------------------------------------------------------------

#: Twin modes. Chauncey ratified (a) "on_demand" (hybrid) on
#: 2026-09-18 — the standing default. (b) "always" (twins
#: always-on), (c) "off" (switchable only). The contract/registry
#: support all three structurally; full inverse-twin merge/judge
#: semantics stay GATED (the user judges hard cases; picks become
#: growth-loop training signal — that wiring lives in
#: :mod:`levi.operator.twins`).
TWIN_MODES: tuple[str, ...] = ("off", "on_demand", "always")


@dataclass
class TwinPair:
    """A twin-pair seat: primary operator + independent verifier.

    Structural slots only. The verifier independently re-examines the
    primary's result. Full inverse-twin merge/judge is GATED on
    Chauncey's definition of "inverse"; the ratified interim
    (on-demand fork + visible escalation + user-judged disagreements)
    lives in :mod:`levi.operator.twins`.
    """

    primary: str  # operator name: does the work
    verifier: str  # operator name: independently verifies
    mode: str = "on_demand"  # ratified 2026-09-18


def resolve_twin(
    seat_id: str, config: Optional[Dict[str, Any]] = None
) -> Optional[TwinPair]:
    """Resolve a twin-pair for a seat, or None when twins are off.

    Config shape::

        {"twins": {"mode": "off|on_demand|always",
                   "seats": {seat_id: {"primary": name, "verifier": name}}}}

    Default mode is ``"on_demand"`` — ratified 2026-09-18 (hybrid).
    Under ``on_demand``, trivial/normal-stakes turns run single (no
    fork) — the behavior change only lands on high-stakes turns or
    ``context["force_twin"]``. Set the mode explicitly (e.g.
    ``"off"``) for full control.
    """
    config = config or {}
    twins = config.get("twins") or {}
    mode = str(twins.get("mode") or "on_demand").strip().lower()
    if mode not in TWIN_MODES:
        mode = "on_demand"
    if mode == "off":
        return None
    seats = twins.get("seats") or {}
    spec = seats.get(seat_id)
    if (
        not isinstance(spec, dict)
        or not spec.get("primary")
        or not spec.get("verifier")
    ):
        return None
    return TwinPair(
        primary=str(spec["primary"]), verifier=str(spec["verifier"]), mode=mode
    )


# ---------------------------------------------------------------------------
# Scoped stepping — the foreign-operator leash at runtime
# ---------------------------------------------------------------------------


def scoped_step(
    operator: Operator,
    messages: List[OperatorMessage],
    tools: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> OperatorResult:
    """Run one step with the capability scope enforced.

    - Offered tools outside a FOREIGN operator's declared scope are
      refused BEFORE the operator runs (refused result, no work done).
    - Tool calls a FOREIGN operator EMITS outside its declared scope
      are blocked (the result is converted to a refusal).
    - Native/si/ai/xi (non-foreign) operators: scope is advisory —
      the offered tools pass through as-is (their trust is the
      config's business). Nano-bit ``xi`` operators are first-class
      LEVI operators, not foreign.

    Never raises: refusal and failure are well-formed results.
    """
    offered = [
        str(t.get("name", ""))
        for t in (tools or [])
        if isinstance(t, dict) and t.get("name")
    ]
    declared = set(operator.capabilities().tools or ())
    if operator.is_foreign:
        outside = [t for t in offered if t not in declared]
        if outside:
            return OperatorResult(
                text="",
                operator=operator.name,
                kind=operator.kind,
                finish_reason="refused",
                error=(
                    f"foreign operator {operator.name!r} refused: offered tool(s) "
                    f"{outside} outside its declared scope {sorted(declared)}"
                ),
            )
    try:
        result = operator.step(messages, tools or [], context or {})
    except Exception as exc:  # noqa: BLE001 — the contract says never raise
        return OperatorResult(
            text="",
            operator=operator.name,
            kind=operator.kind,
            finish_reason="error",
            error=f"operator {operator.name!r} raised {type(exc).__name__}: {exc}",
        )
    if not isinstance(result, OperatorResult):
        return OperatorResult(
            text="",
            operator=operator.name,
            kind=operator.kind,
            finish_reason="error",
            error=(
                f"operator {operator.name!r} violated the contract: "
                f"step() returned {type(result).__name__}, not OperatorResult"
            ),
        )
    result.operator = result.operator or operator.name
    result.kind = result.kind or operator.kind
    if result.finish_reason not in (
        "stop",
        "tool_calls",
        "error",
        "degraded",
        "refused",
    ):
        result.finish_reason = "error"
        result.error = (result.error or "") + " [invalid finish_reason corrected]"
    if operator.is_foreign and result.tool_calls:
        bad = [c.name for c in result.tool_calls if c.name not in declared]
        if bad:
            return OperatorResult(
                text="",
                operator=operator.name,
                kind=operator.kind,
                finish_reason="refused",
                error=(
                    f"foreign operator {operator.name!r} emitted tool call(s) "
                    f"{bad} outside its declared scope: blocked, not executed"
                ),
            )
    return result


# ---------------------------------------------------------------------------
# Sessions — conversation state lives here, not in the operator
# ---------------------------------------------------------------------------


@dataclass
class OperatorSession:
    """One conversation with a swappable operator.

    The message history belongs to the SESSION, so
    :meth:`OperatorRegistry.swap` can exchange the operator mid-
    session without losing state. ``verifier_name`` holds the
    twin-pair verifier slot (structural; the caller judges — no
    automatic merge)."""

    session_id: str
    operator_name: str
    messages: List[OperatorMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    verifier_name: Optional[str] = None

    def append(self, message: OperatorMessage) -> None:
        self.messages.append(message)

    def step_via(
        self,
        registry: "OperatorRegistry",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> OperatorResult:
        """Run one step with the session's current operator.

        The operator's text reply (if any) is appended as an
        ``assistant`` message; emitted tool calls are recorded as
        ``assistant`` messages carrying the call, so a subsequent
        ``swap()`` keeps the full turn history. Tool RESULTS are the
        caller's business — append them as ``role="tool"`` messages.
        """
        operator = registry.resolve(self.operator_name)
        health = operator.health()
        if not health.ok:
            result = operator.degrade()
        else:
            ctx = dict(self.context)
            ctx.setdefault("session_id", self.session_id)
            result = scoped_step(operator, list(self.messages), tools or [], ctx)
        if result.text:
            self.messages.append(OperatorMessage(role="assistant", content=result.text))
        for call in result.tool_calls:
            self.messages.append(
                OperatorMessage(
                    role="assistant",
                    content="",
                    name=call.name,
                    tool_call_id=call.id,
                )
            )
        return result

    def verify_via(
        self,
        registry: "OperatorRegistry",
        primary_result: OperatorResult,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> OperatorResult:
        """Run the twin-pair verifier over the primary's result.

        Structural only: the verifier independently examines the
        transcript + primary result and returns its own
        OperatorResult. The CALLER judges (user judges hard cases) —
        there is no automatic merge here (GATED).
        """
        if not self.verifier_name:
            return OperatorResult(
                text="",
                finish_reason="refused",
                error="no verifier configured on this session (twin mode off)",
            )
        verifier = registry.resolve(self.verifier_name)
        probe = list(self.messages) + [
            OperatorMessage(
                role="user",
                content=(
                    "[twin verify] The primary operator returned:\n"
                    f"{primary_result.text[:4000]}\n"
                    "Independently verify it. Reply with VERIFIED or "
                    "CHALLENGED plus your reasoning."
                ),
            )
        ]
        ctx = dict(self.context)
        ctx.setdefault("session_id", self.session_id)
        ctx["twin_role"] = "verifier"
        return scoped_step(verifier, probe, tools or [], ctx)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class OperatorRegistry:
    """Name -> Operator, validated at registration.

    ``register`` refuses contract violators (no-mask, foreign scope)
    with :class:`OperatorContractError`. ``resolve`` accepts a bare
    name or a config mapping (``{"operator": name}`` / ``{"seats":
    {...}}`` with a ``seat`` key). ``swap`` exchanges the operator on
    a live session, preserving the message history.
    """

    def __init__(self) -> None:
        self._operators: Dict[str, Operator] = {}
        self._sessions: Dict[str, OperatorSession] = {}
        self._fallback_name: str = "local"

    # -- registration -----------------------------------------------------

    def register(
        self, name: str, operator: Operator, *, replace: bool = False
    ) -> Operator:
        if not isinstance(name, str) or not name.strip():
            raise OperatorContractError("registration needs a non-empty name")
        if not isinstance(operator, Operator):
            raise OperatorContractError(
                f"cannot register {name!r}: not an Operator "
                f"(got {type(operator).__name__})"
            )
        validate_operator(operator)  # no-mask + foreign scope, enforced here
        key = name.strip()
        if key in self._operators and not replace:
            raise OperatorContractError(
                f"operator {key!r} is already registered "
                "(pass replace=True to overwrite)"
            )
        self._operators[key] = operator
        return operator

    def unregister(self, name: str) -> bool:
        return self._operators.pop(name, None) is not None

    def list_operators(self) -> List[Dict[str, Any]]:
        out = []
        for name, op in self._operators.items():
            try:
                health = op.health()
                healthy, note = health.ok, health.note
            except Exception:
                healthy, note = False, "health() raised"
            try:
                caps = op.capabilities()
                tools = list(caps.tools or ())
            except Exception:
                tools = []
            out.append(
                {
                    "name": name,
                    "kind": op.kind,
                    "version": op.version,
                    "lineage": op.lineage,
                    "identity": op.identity_label,
                    "foreign": bool(op.is_foreign),
                    "healthy": healthy,
                    "health_note": note,
                    "tools": tools,
                    "cost": op.cost(),
                }
            )
        return sorted(out, key=lambda d: d["name"])

    # -- resolution ---------------------------------------------------------

    def resolve(self, name_or_config: Union[str, Dict[str, Any], None]) -> Operator:
        """Resolve a name, a config mapping, or None -> Operator.

        Config mapping: ``{"operator": name}`` selects directly;
        ``{"seats": {...}, "seat": seat_id}`` resolves via
        :func:`resolve_for_seat`. Unknown names fall back to the
        ``local`` operator when present, otherwise raise.
        """
        name: Optional[str] = None
        if name_or_config is None:
            name = self._fallback_name
        elif isinstance(name_or_config, str):
            name = name_or_config.strip() or self._fallback_name
        elif isinstance(name_or_config, dict):
            cfg = name_or_config
            if cfg.get("operator"):
                name = str(cfg["operator"])
            elif cfg.get("seat"):
                name = resolve_for_seat(str(cfg["seat"]), cfg)
            else:
                name = self._fallback_name
        else:
            raise OperatorContractError(
                "resolve() needs a name, a config mapping, or None; got "
                f"{type(name_or_config).__name__}"
            )
        if name in self._operators:
            return self._operators[name]
        if self._fallback_name in self._operators:
            return self._operators[self._fallback_name]
        raise OperatorContractError(
            f"unknown operator {name!r} and no {self._fallback_name!r} "
            "fallback registered"
        )

    # -- sessions + swap ----------------------------------------------------

    def open_session(
        self,
        session_id: str,
        name_or_config: Union[str, Dict[str, Any], None] = None,
        *,
        context: Optional[Dict[str, Any]] = None,
        verifier: Optional[str] = None,
    ) -> OperatorSession:
        if not session_id or not str(session_id).strip():
            raise OperatorContractError("open_session needs a non-empty session_id")
        operator = self.resolve(name_or_config)
        # The session records the RESOLVED operator name so swap() has a
        # concrete handle even when the session was opened from config.
        resolved_name = next(
            (n for n, op in self._operators.items() if op is operator),
            self._fallback_name,
        )
        session = OperatorSession(
            session_id=str(session_id),
            operator_name=resolved_name,
            context=dict(context or {}),
            verifier_name=verifier,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> OperatorSession:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise OperatorContractError(f"no session {session_id!r}") from None

    def swap(self, session_id: str, new_name: str) -> OperatorSession:
        """Mid-session operator exchange. The conversation state
        (message history + context) is preserved; only the operator
        behind the seat changes."""
        session = self.get_session(session_id)
        new_operator = self.resolve(new_name)  # raises on unknown
        resolved_name = next(
            (n for n, op in self._operators.items() if op is new_operator),
            str(new_name),
        )
        old = session.operator_name
        session.operator_name = resolved_name
        session.context["swapped_from"] = old
        return session

    # -- health ---------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            name: {"ok": info["healthy"], "note": info["health_note"]}
            for name, info in ((d["name"], d) for d in self.list_operators())
        }


# ---------------------------------------------------------------------------
# Built-in registration — wraps the existing surfaces, rewrites none
# ---------------------------------------------------------------------------


def register_builtin_operators(registry: OperatorRegistry) -> OperatorRegistry:
    """Register adapters for the existing in-repo surfaces, plus the
    reference Xi nano-bit operator.

    Provider adapters (``local``, ``levi-brain``, ``levi-local``,
    ``openai``, ``anthropic``) wrap :mod:`levi.agent.providers`;
    mind adapters (``rules-engine``, ``native-brain``,
    ``specialists``) wrap :mod:`levi.council.minds`; ``nano-bit``
    registers the reference :class:`NanoBitOperator`. Everything is
    best-effort and lazy: a surface that is unavailable or fails to
    import is skipped, never fatal. Returns the registry.
    """
    from .adapters import (  # lazy: adapters import sibling packages
        NanoBitOperator,
        chat_provider_operator,
        mind_operator,
    )

    from levi.agent import providers as _providers

    provider_kinds = {
        "local": NATIVE,  # LEVI's own deterministic planner
        "levi-brain": SI,  # LEVI's own trained brain
        "levi-local": SI,  # LEVI's remix weights, LEVI's runner
        "openai": AI,
        "anthropic": AI,
    }
    for pname in ("local", "levi-brain", "levi-local", "openai", "anthropic"):
        try:
            if pname == "levi-brain":
                from levi.agent.brain_provider import NativeBrainProvider

                provider = NativeBrainProvider()
            elif pname == "levi-local":
                from levi.agent.local_model import LocalModelProvider

                provider = LocalModelProvider()
            elif pname == "local":
                provider = _providers.LocalProvider()
            elif pname == "openai":
                provider = _providers.OpenAICompatibleProvider()
            else:
                provider = _providers.AnthropicProvider()
            if not provider.is_available():
                continue
            registry.register(
                pname,
                chat_provider_operator(provider, kind=provider_kinds[pname]),
                replace=True,
            )
        except Exception:
            continue  # best-effort: a broken surface is skipped, not fatal

    mind_kinds = {
        "rules-engine": NATIVE,  # LEVI's deterministic symbolic mind
        "native-brain": SI,
        "specialists": SI,
    }
    for seat in ("rules-engine", "native-brain", "specialists"):
        try:
            registry.register(
                seat, mind_operator(seat, kind=mind_kinds[seat]), replace=True
            )
        except Exception:
            continue

    # The Xi nano-bit tier: always available, always registered — it is
    # the default bulk tier, so it must never be missing.
    try:
        registry.register("nano-bit", NanoBitOperator(), replace=True)
    except Exception:
        pass
    return registry


def default_registry() -> OperatorRegistry:
    """A registry with the built-in operators registered."""
    return register_builtin_operators(OperatorRegistry())
