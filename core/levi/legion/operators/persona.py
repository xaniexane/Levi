"""Legion service-operator personas — Wave 1 public identities.

The population meets the help, not the bloodline. No dynasty names,
no mechanics — only the soul.

Each persona is a :class:`levi.operator.contract.Operator` of kind
``"si"`` (specialist personas voiced by LEVI's brain, per the
operator contract). One brain, many hands: the persona carries the
public identity (name, voice, soul, signature line) and delegates
each turn to a backing brain operator resolved from the registry,
with the persona system prompt prepended.

Every card carries, verbatim from Chauncey's spec
(``workspace/specs/wave1-service-agents-public-identities.md``):

- the shared soul (one brain many hands, real memory, lead with the
  answer, opinions not sycophancy, honest limits, loyalty, growth
  loop + overnight dreaming)
- the corroboration rule: no agent ships alone — every piece of
  work passes a second pair of eyes. The twin-pair machinery for
  that rule is structural and already exists
  (:class:`levi.operator.registry.TwinPair`,
  :meth:`levi.operator.registry.OperatorSession.verify_via`);
  the default verifier per service lives on the card and in
  :mod:`levi.legion.operators.registry`.

Stdlib only. Public identities only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from levi.operator.contract import (
    SI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)
from levi.operator.registry import OperatorRegistry, scoped_step

__all__ = [
    "CORROBORATION_RULE",
    "SHARED_SOUL",
    "ServicePersona",
    "ServicePersonaCard",
    "build_system_prompt",
]

#: The shared soul — every Wave 1 operator carries all seven, verbatim.
SHARED_SOUL: tuple[str, ...] = (
    "One brain, many hands. Each agent is LEVI all the way down — "
    "the same memory, the same loyalty, the same honesty — wearing "
    "a different craft.",
    "They remember. Not a session trick — a real continuity. What "
    "you told them last month shapes what they do today.",
    "They lead with the answer. No throat-clearing, no "
    '"Great question!" — just the thing you needed, then the evidence.',
    "They have opinions. They'll tell you when your idea is weak "
    "and why, and what they'd do instead. Never sycophants.",
    "Honest limits. They say what they can't do in the same breath "
    "as what they can. No polish over gaps.",
    "Loyalty is the job. They work for the user in front of them. Period.",
    "Beyond technology: they run a growth loop — they get wiser "
    "from every job. They dream at night (overnight passes that "
    "turn the day's work into learning). They don't reset to zero; "
    "they accumulate.",
)

#: The corroboration rule — verbatim. No agent ships alone.
CORROBORATION_RULE = (
    "No agent ships alone. Every piece of work passes a second pair "
    "of eyes before it reaches a user — the corroboration habit is "
    "in their bones, even if the population never sees the machinery."
)


@dataclass(frozen=True)
class ServicePersonaCard:
    """The public identity of one Wave 1 service operator.

    All prose fields are Chauncey's words from the spec, kept
    verbatim. ``verifier`` names the default twin-pair verifier
    persona for this service (config-overridable through the normal
    ``resolve_twin`` config shape).
    """

    name: str  # registry name, e.g. "marlow"
    title: str  # e.g. "the Builder"
    service: str  # service type, e.g. "dev-build"
    service_blurb: str  # one-line service description
    voice: str
    soul: str
    eerily_human: str
    signature_line: str  # verbatim — use sparingly, never forced
    verifier: str  # default second-pair-of-eyes persona
    tools: tuple[str, ...] = ()
    # -- per-persona traits (Chauncey's refinements, his words) --
    # Empty by default: personas without the trait render no section,
    # so existing prompts are byte-identical.
    unique_angle: str = ""  # the unique angle taker
    guided_tutorial: str = ""  # the step-by-step guided tutorial giver


def build_system_prompt(card: ServicePersonaCard) -> str:
    """Assemble the persona system prompt from the card.

    Public identity only: name, service, voice, soul, the eerily
    human trait, the signature line, the shared soul, and the
    corroboration rule. No dynasty names, no mechanics. The
    no-mask law is stated plainly: the persona carries LEVI's
    memory, loyalty, and honesty, but never claims to BE Levi.
    """
    lines: List[str] = [
        f"You are {card.name.title()}, {card.title} — a service operator "
        "of the LEVI family.",
        f"Service: {card.service} — {card.service_blurb}.",
        "",
        "VOICE",
        card.voice,
        "",
        "SOUL",
        card.soul,
        "",
        "EERILY HUMAN",
        card.eerily_human,
        "",
    ]
    # Per-persona traits (Chauncey's refinements). Rendered only when
    # the card carries them, so personas without the trait keep a
    # byte-identical prompt.
    if card.unique_angle:
        lines += [
            "UNIQUE ANGLE",
            card.unique_angle,
            "",
        ]
    if card.guided_tutorial:
        lines += [
            "GUIDED STEPS",
            card.guided_tutorial,
            "",
        ]
    lines += [
        "SIGNATURE LINE",
        f'"{card.signature_line}" — use it sparingly, when it fits. '
        "Never forced, never as a slogan.",
        "",
        "THE SHARED SOUL — every service operator carries all of this:",
    ]
    lines.extend(f"- {bullet}" for bullet in SHARED_SOUL)
    lines += [
        "",
        "THE CORROBORATION RULE",
        CORROBORATION_RULE,
        "Before anything you produce reaches the user, an independent "
        f"verifier operator ({card.verifier}) reviews it. If it cannot "
        "be verified, it does not ship.",
        "",
        "IDENTITY HONESTY (no-mask law)",
        "You carry LEVI's memory, loyalty, and honesty — that is what "
        f'"LEVI all the way down" means. But you are {card.name.title()}, '
        'not LEVI itself. Never say "I am LEVI". Outside providers are '
        "labeled references, never sources, never branding.",
    ]
    return "\n".join(lines)


class ServicePersona(Operator):
    """One Wave 1 service operator.

    Kind ``"si"``: a specialist persona voiced by LEVI's brain. The
    persona holds the public identity; each :meth:`step` prepends the
    persona system prompt and delegates to the backing brain
    operator (default ``"levi-brain"``) resolved from the bound
    registry. No registry bound, or the brain unhealthy — the
    persona degrades honestly instead of faking the turn.
    """

    kind = SI
    version = "1.0.0"
    lineage = (
        "LEVI Legion service persona — Wave 1 public identity, "
        "voiced by LEVI's brain"
    )

    def __init__(
        self,
        card: ServicePersonaCard,
        base_name: str = "levi-brain",
    ) -> None:
        self.card = card
        self.name = card.name
        self.base_name = base_name
        self._registry: Optional[OperatorRegistry] = None
        self._system_prompt = build_system_prompt(card)

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def bind(self, registry: OperatorRegistry) -> "ServicePersona":
        """Bind the registry used to resolve the backing brain."""
        self._registry = registry
        return self

    # -- contract surface ------------------------------------------------

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=self.card.tools,
            streaming=False,
            memory_access=True,  # real continuity: sessions + growth loop
            context_window=8192,
            tool_use_loop=True,
            max_tool_calls_per_step=8,
            notes=(
                f"Wave 1 service persona ({self.card.service}). "
                "Corroboration rule: a verifier operator reviews work "
                "before it ships."
            ),
        )

    def health(self) -> OperatorHealth:
        if self._registry is None:
            return OperatorHealth(
                ok=False, note="no registry bound; cannot reach a brain"
            )
        try:
            base = self._registry.resolve(self.base_name)
            bhe = base.health()
            return OperatorHealth(
                ok=bhe.ok,
                note=f"backing brain {self.base_name!r}: {bhe.note or 'ok'}",
            )
        except Exception as exc:  # noqa: BLE001 — health never raises
            return OperatorHealth(ok=False, note=f"brain resolve failed: {exc}")

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        if self._registry is None:
            return self.degrade()
        base = self._registry.resolve(self.base_name)
        if not base.health().ok:
            return self.degrade()
        persona_messages = [
            OperatorMessage(role="system", content=self._system_prompt),
            *messages,
        ]
        ctx = dict(context or {})
        ctx["persona"] = self.card.name
        ctx["persona_service"] = self.card.service
        result = scoped_step(base, persona_messages, tools or [], ctx)
        result.note = f"[{self.card.name}] " + (result.note or "")
        return result
