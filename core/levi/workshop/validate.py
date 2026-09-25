"""Fail-closed validation of blueprints against current doctrine.

Every check denies by default. A blueprint passes only when each part
resolves against the registries that own it:

  * unknown agent id            -> refuse
  * unknown specialist id       -> refuse
  * unknown substrate id        -> refuse
  * substrate ``own-cloud``     -> refuse (planned, not built — the roster
                                   matrix says so, and so do we)
  * auth-gated substrate (groq / gemini / openai / xai) without a
    recorded authorization for that substrate -> refuse
  * unknown organ               -> refuse (deny-closed, same as the
                                   organ registry)
  * unknown Legion role         -> refuse
  * unknown nanobit format      -> refuse (the one canonical format only)
  * unknown original            -> refuse (the eleven originals only)
  * capability claim not declared by the chosen specialist and not one
    of the honest-label semantics -> refuse (unsupported claim)

Honest-label semantics (allowed claims beyond specialist capabilities):
  "local-only", "paper-only", "no-live-execution", "advisory"

These describe what a dry run honestly is; they grant no power.

OPEN DECISION (twin ambiguity): ``twin_note`` is accepted as free text
and never interpreted. The workshop does not decide whether twins are
hybrid/switchable, always-on, or what "inverse twin" means.
"""

from __future__ import annotations

from typing import List, Set

from .blueprint import Blueprint
from .inventory import (
    agent_ids,
    legion_role_names,
    nanobit_ids,
    organ_names,
    original_ids,
    specialist_ids,
    substrate_ids,
)


class ValidationError(Exception):
    """A blueprint failed fail-closed validation. The message says why."""


#: Claims that are honest labels, not powers. Allowed on any blueprint.
HONEST_LABELS = frozenset({"local-only", "paper-only", "no-live-execution", "advisory"})

#: Substrates that exist only as Chauncey's direction. Never resolvable.
PLANNED_SUBSTRATES = frozenset({"own-cloud"})


def _specialist_capabilities(specialist_id: str) -> Set[str]:
    from levi.agent.specialists import SPECIALISTS

    return set(SPECIALISTS[specialist_id].capabilities)


def _substrate_status(substrate_id: str) -> str:
    from levi.packaging.roster_matrix import MODEL_TYPES

    return MODEL_TYPES[substrate_id].status


def validate_blueprint(
    bp: Blueprint, authorized_substrates: Set[str] | None = None
) -> List[str]:
    """Validate a blueprint. Returns the list of passed checks.

    Raises :class:`ValidationError` on the first failed check — fail
    closed: anything not provably allowed is denied.
    """
    authorized = set(authorized_substrates or [])
    passed: List[str] = []

    if bp.agent not in set(agent_ids()):
        raise ValidationError(f"refused: unknown agent {bp.agent!r}")
    passed.append(f"agent {bp.agent!r} resolves in the agent registry")

    if bp.specialist not in set(specialist_ids()):
        raise ValidationError(f"refused: unknown specialist {bp.specialist!r}")
    passed.append(f"specialist {bp.specialist!r} resolves in the roster")

    if bp.substrate not in set(substrate_ids()):
        raise ValidationError(f"refused: unknown substrate {bp.substrate!r}")
    if bp.substrate in PLANNED_SUBSTRATES:
        raise ValidationError(
            f"refused: substrate {bp.substrate!r} is planned, not built — "
            "the roster matrix forbids resolving it"
        )
    status = _substrate_status(bp.substrate)
    if status == "auth-gated" and bp.substrate not in authorized:
        raise ValidationError(
            f"refused: substrate {bp.substrate!r} is auth-gated and no "
            "authorization was recorded for it"
        )
    passed.append(f"substrate {bp.substrate!r} resolves (status={status})")

    if bp.organ not in set(organ_names()):
        raise ValidationError(
            f"refused: unknown organ {bp.organ!r} — deny-closed dispatch"
        )
    passed.append(f"organ {bp.organ!r} resolves in the organ registry")

    if bp.legion_role not in set(legion_role_names()):
        raise ValidationError(f"refused: unknown Legion role {bp.legion_role!r}")
    passed.append(f"Legion role {bp.legion_role!r} resolves in the crew roles")

    # Optional extras: empty means absent. When present, they must resolve
    # against their own real sources, same as every other part.
    if bp.nanobit:
        if bp.nanobit not in set(nanobit_ids()):
            raise ValidationError(f"refused: unknown nanobit format {bp.nanobit!r}")
        passed.append(f"nanobit {bp.nanobit!r} resolves as the micro-companion format")
    if bp.original:
        if bp.original not in set(original_ids()):
            raise ValidationError(f"refused: unknown original {bp.original!r}")
        passed.append(f"original {bp.original!r} resolves among the eleven originals")

    allowed_claims = _specialist_capabilities(bp.specialist) | HONEST_LABELS
    for claim in bp.claims:
        if claim not in allowed_claims:
            raise ValidationError(
                f"refused: unsupported claim {claim!r} — not a declared "
                f"capability of specialist {bp.specialist!r} and not an "
                "honest-label semantic"
            )
    passed.append(f"{len(bp.claims)} claim(s) within supported semantics")

    # twin_note: accepted, never interpreted. Open decision — see module
    # docstring. Validation records the note's presence, not a meaning.
    passed.append("twin_note carried as note (twin semantics unresolved)")

    return passed
