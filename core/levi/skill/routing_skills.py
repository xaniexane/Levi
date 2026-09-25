"""LEVI routing skill pack: engines exposed as invocable skills.

The engines are pure decision machines; this pack is their skill-side
handle. Every skill here is INFO risk — compute, never act. The pack
registers through the skill registry's builtin list (data-driven entry
point: ``ROUTING_SKILLS``), and the handlers call
``levi.engines.base.registry`` directly, so any new engine is one line
away from a skill wrapper.

Skills:

- ``engine.escalate`` — run the escalation router: pass confidence,
  stakes, reversibility and get the decision plus the audit trail.
- ``engine.list`` — the honest inventory: every registered engine's id,
  name, and description, in stable order.
- ``engine.canon`` — the engine law itself, as advisory text: engines
  compute, never act; same inputs → same verdict; deny-closed inputs;
  the keeper is the ceiling.

Lazy engine import keeps this module decoupled from the engines
package at registry load time. Stdlib only.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.skill.registry import Skill, SkillRisk


def _engines_registry():
    from levi.engines import registry

    return registry


def _skill_escalate(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    try:
        result = _engines_registry().run("escalate", dict(args))
    except (KeyError, ValueError) as exc:
        return f"escalate refused: {exc}"
    verdict = result.verdict["decision"]
    lines = [f"escalation verdict: {verdict}"]
    lines.append(f"engine confidence: {result.confidence:.2f}")
    lines.extend(f"  - {step}" for step in result.trace)
    return "\n".join(lines)


def _skill_list(args: Dict[str, Any] | None = None) -> str:
    registry = _engines_registry()
    engines = registry.list()
    if not engines:
        return "no engines registered."
    lines = [f"{e.id}: {e.name} — {e.description}" for e in engines]
    return "\n".join(lines)


_ENGINE_CANON = (
    "The engine law: engines compute, never act. Same inputs give the same "
    "verdict every time (the determinism law). Inputs are deny-closed — "
    "malformed input is refused with a named error, never coerced. "
    "Escalation runs confidence → stakes → reversibility: the rules handle "
    "what is safe, the brain judges what is murky, the keeper decides what "
    "is heavy, and the queue holds what cannot be decided yet. "
    "When the keeper is unreachable, nothing is guessed — it is queued with "
    "the full audit trail."
)


def _skill_canon(args: Dict[str, Any] | None = None) -> str:
    return _ENGINE_CANON


ROUTING_SKILLS: List[Skill] = [
    Skill(
        id="engine.escalate",
        name="Escalation Router",
        description=(
            "Run the confidence-based escalation router: who touches the "
            "work — the rules, the brain, the keeper, or the queue."
        ),
        category="routing",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["engines", "escalation", "routing"],
        version="1.0.0",
        handler=_skill_escalate,
    ),
    Skill(
        id="engine.list",
        name="Engine Inventory",
        description=(
            "List every registered engine: id, name, and description, in stable order."
        ),
        category="routing",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["engines", "inventory"],
        version="1.0.0",
        handler=_skill_list,
    ),
    Skill(
        id="engine.canon",
        name="Engine Canon",
        description=(
            "The engine law as advisory text: engines compute, never act; "
            "the escalation ladder; the no-guess rule."
        ),
        category="routing",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["engines", "canon", "advisory"],
        version="1.0.0",
        handler=_skill_canon,
    ),
]
