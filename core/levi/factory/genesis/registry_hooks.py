"""Factory Genesis registry hooks — mint_skill() / mint_agent() + verification.

These are the REGISTRY stage of the factory line. Each mint function performs
the registration step for one kind and then PROVES it: no proof, no mint.

- Skill: the data-driven pack (``levi.skill.<pack>_skills``) is wired into
  ``SkillRegistry.__init__``; verification instantiates the registry and
  asserts the skill id, category, and risk.
- Agent: the wave module subclasses ``DynastyAgent`` and is exported from
  ``levi.dynasty.wave``; verification imports it, constructs it against a
  throwaway home, and asserts the identity laws (agent_id, generation,
  commissioned_by).

Advisory-only: minting registers *definitions*. It never deploys live
actors, spends money, or touches accounts.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict


def verify_skill(
    skill_id: str, category: str = "factory", max_risk: int = 0
) -> Dict[str, object]:
    """Prove a factory skill is registered. Raises AssertionError on failure."""
    from levi.skill.registry import SkillRegistry

    registry = SkillRegistry()
    skill = registry.get(skill_id)
    assert skill is not None, f"skill not registered: {skill_id}"
    assert skill.category == category, (
        f"skill {skill_id} category {skill.category!r} != {category!r}"
    )
    assert int(skill.risk_level) <= max_risk, (
        f"skill {skill_id} risk {skill.risk_level} exceeds {max_risk}"
    )
    return {
        "skill_id": skill.id,
        "name": skill.name,
        "category": skill.category,
        "risk": int(skill.risk_level),
        "version": skill.version,
        "verified": True,
    }


def mint_skill(skill_id: str, **kwargs: object) -> Dict[str, object]:
    """Mint step for a skill: the pack wire-up is code; this proves it."""
    return verify_skill(skill_id, **kwargs)  # type: ignore[arg-type]


def verify_agent(
    agent_id: str = "queue-herald",
    generation: int = 2,
    commissioned_by: str = "factory-genesis",
) -> Dict[str, object]:
    """Prove a factory agent definition constructs and carries its laws."""
    from levi.dynasty.wave import QueueHerald

    assert QueueHerald.agent_id == agent_id, (
        f"agent_id {QueueHerald.agent_id!r} != {agent_id!r}"
    )
    assert QueueHerald.generation == generation, (
        f"generation {QueueHerald.generation!r} != {generation!r}"
    )
    assert QueueHerald.commissioned_by == commissioned_by, (
        f"commissioned_by {QueueHerald.commissioned_by!r} != {commissioned_by!r}"
    )
    with tempfile.TemporaryDirectory() as tmp:
        agent = QueueHerald(home=Path(tmp))
        assert agent.agent_id == agent_id
        state = agent.first_task()
        assert isinstance(state, dict) and "counts" in state
    return {
        "agent_id": agent_id,
        "display_name": QueueHerald.display_name,
        "generation": generation,
        "commissioned_by": commissioned_by,
        "first_task_ok": True,
        "verified": True,
    }


def mint_agent(**kwargs: object) -> Dict[str, object]:
    """Mint step for an agent: the wave module is code; this proves it."""
    return verify_agent(**kwargs)  # type: ignore[arg-type]
