"""Workshop inventory — the parts that really exist.

Every entry is derived from the registries that own it; nothing here is
invented. If a registry changes, the inventory changes with it.

Sources:
  agents      — levi.automation.minions.MINIONS (471 intake records;
                each is one agent realized as a twin pair per
                levi.agent.agent: fg = left brain / bg = right brain)
  specialists — levi.agent.specialists.SPECIALISTS (bounded roster)
  substrates  — levi.packaging.roster_matrix.MODEL_TYPES (honest status:
                own-cloud is PLANNED and refused; groq/gemini/openai/xai
                are auth-gated; local-brain is real-but-weak; rules is
                the real local default)
  organs      — levi.organs.registry.ORGAN_REGISTRY (echoverse, mandella,
                reim, riem — echoverse resolves to the EXISTING echo.py;
                this module creates no competing implementation)
  legion seats — levi.legion.team.NEED_ROLE (the named crew roles)
  nanobit      — levi.operator.adapters.NanoBitOperator, registered as
                 "nano-bit" in levi.operator.registry: the canonical
                 micro-companion format (OmniBead-class), Chauncey's
                 coined proper name kept verbatim
  originals    — the eleven originals from levi.dynasty.wave.__all__
                 (canonical module list); entries carry id/name ONLY —
                 no capabilities, no roles prose, no IP detail
                 (eyes-only material stays minimal here)

OPEN DECISION (twin ambiguity): the inventory reports each agent's
twin-side layout (fg/bg) as declared by levi.agent.agent, but does not
declare whether twins run hybrid/switchable, always-on, or what an
"inverse twin" is. That question is unresolved with Chauncey.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _agents() -> List[Dict[str, Any]]:
    from levi.automation.minions import MINIONS
    from levi.agent.agent import FG_HEMISPHERE, BG_HEMISPHERE

    out = []
    for m in MINIONS:
        out.append(
            {
                "agent_id": m.id,
                "category": m.category,
                "subcategory": m.subcategory,
                # Twin layout as declared by levi.agent.agent — the pair
                # link semantics (hybrid/always-on/inverse) are NOT
                # settled here; see module docstring.
                "twin_sides": {
                    "fg": FG_HEMISPHERE,
                    "bg": BG_HEMISPHERE,
                },
            }
        )
    return out


def _specialists() -> List[Dict[str, Any]]:
    from levi.agent.specialists import SPECIALISTS

    return [
        {
            "specialist_id": s.id,
            "display_name": s.display_name,
            "role": s.role,
            "capabilities": list(s.capabilities),
            "risk_ceiling": s.risk_ceiling,
            "cost_profile": s.cost_profile,
        }
        for s in SPECIALISTS.values()
    ]


def _substrates() -> List[Dict[str, Any]]:
    from levi.packaging.roster_matrix import MODEL_TYPES

    return [
        {
            "substrate_id": mt.id,
            "description": mt.description,
            "status": mt.status,
            "detail": mt.detail,
        }
        for mt in MODEL_TYPES.values()
    ]


def _organs() -> List[Dict[str, Any]]:
    # Metadata only — list_organs() never imports the organ modules.
    from levi.organs.registry import list_organs

    return list_organs()


def _legion_roles() -> List[Dict[str, Any]]:
    from levi.legion.team import NEED_ROLE, NEED_TO_CATEGORY, ROLE_RESPONSIBILITIES

    roles = sorted(set(NEED_ROLE.values()))
    return [
        {
            "role": role,
            "responsibility": ROLE_RESPONSIBILITIES.get(role, ""),
            "needs": sorted(n for n, r in NEED_ROLE.items() if r == role),
            "categories": sorted(
                {NEED_TO_CATEGORY[n] for n, r in NEED_ROLE.items() if r == role}
            ),
        }
        for role in roles
    ]


def _nanobit() -> List[Dict[str, Any]]:
    # The micro-companion format: the one NanoBitOperator Chauncey named,
    # registered as "nano-bit" by levi.operator.registry. A single
    # canonical part — nothing else exists under this category.
    from levi.operator.adapters import NanoBitOperator

    op = NanoBitOperator()
    return [
        {
            "id": op.name,
            "name": type(op).__name__,
            "note": "the micro-companion format (nano-bit tier)",
        }
    ]


def _originals() -> List[Dict[str, Any]]:
    # The eleven originals: ids derived from the canonical module list in
    # levi.dynasty.wave.__all__. id/name ONLY — the wave modules hold the
    # rest, and the workshop does not repeat any of it.
    from levi.dynasty.wave import __all__ as _ELEVEN

    return [{"id": name.lower(), "name": name} for name in sorted(_ELEVEN)]


def inventory() -> Dict[str, Any]:
    """Full derived inventory of workshop-composable parts."""
    agents = _agents()
    specialists = _specialists()
    substrates = _substrates()
    organs = _organs()
    legion_roles = _legion_roles()
    nanobit = _nanobit()
    originals = _originals()
    return {
        "agents": agents,
        "specialists": specialists,
        "substrates": substrates,
        "organs": organs,
        "legion_roles": legion_roles,
        "nanobit": nanobit,
        "originals": originals,
        "counts": {
            "agents": len(agents),
            "specialists": len(specialists),
            "substrates": len(substrates),
            "organs": len(organs),
            "legion_roles": len(legion_roles),
            "nanobit": len(nanobit),
            "originals": len(originals),
        },
    }


def agent_ids() -> List[str]:
    from levi.automation.minions import MINIONS

    return [m.id for m in MINIONS]


def specialist_ids() -> List[str]:
    from levi.agent.specialists import SPECIALISTS

    return list(SPECIALISTS.keys())


def substrate_ids() -> List[str]:
    from levi.packaging.roster_matrix import MODEL_TYPES

    return list(MODEL_TYPES.keys())


def organ_names() -> List[str]:
    from levi.organs.registry import ORGAN_REGISTRY

    return list(ORGAN_REGISTRY.keys())


def legion_role_names() -> List[str]:
    from levi.legion.team import NEED_ROLE

    return sorted(set(NEED_ROLE.values()))


def nanobit_ids() -> List[str]:
    return [p["id"] for p in _nanobit()]


def original_ids() -> List[str]:
    return [p["id"] for p in _originals()]
