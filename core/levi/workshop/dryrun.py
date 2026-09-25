"""Local dry-runs — honestly labeled simulations.

A dry run resolves every part of a validated blueprint against the real
registries, reports what WOULD be assembled, and stops there. It:

  * spawns no agent and no twin pair,
  * executes no organ (only reads the organ registry's metadata),
  * calls no provider and needs no key,
  * moves no money, writes no roster state.

Every report carries the label ``LOCAL-ONLY DRY RUN`` so it can never be
mistaken for a live assembly. Auth-gated substrates are reported as
"would need authorization" and skipped, never touched.
"""

from __future__ import annotations

from typing import Any, Dict, Set

from .blueprint import Blueprint
from .validate import validate_blueprint

#: The honest label every dry-run report carries. Never remove it.
DRY_RUN_LABEL = (
    "LOCAL-ONLY DRY RUN — simulated on this machine; no agent spawned, "
    "no organ executed, no provider called, no money moved."
)


def _substrate_status(substrate_id: str) -> str:
    from levi.packaging.roster_matrix import MODEL_TYPES

    return MODEL_TYPES[substrate_id].status


def _organ_describe(organ: str) -> str:
    from levi.organs.registry import ORGAN_REGISTRY

    return ORGAN_REGISTRY[organ]["describe"]


def dry_run(
    bp: Blueprint, authorized_substrates: Set[str] | None = None
) -> Dict[str, Any]:
    """Dry-run a blueprint locally. Fails closed on invalid blueprints.

    Returns a report dict. The report is a simulation: it describes the
    assembly that a validated blueprint WOULD produce.
    """
    checks = validate_blueprint(bp, authorized_substrates)

    substrate_status = _substrate_status(bp.substrate)
    substrate_note = (
        "real and available"
        if substrate_status in ("real", "real-weak")
        else f"{substrate_status} — would need authorization at assembly time"
    )

    steps = [
        f"resolve agent {bp.agent!r} from the agent registry (twin pair "
        "recorded; twin semantics unresolved — see blueprint twin_note)",
        f"seat specialist {bp.specialist!r} (bounded roster)",
        f"back substrate {bp.substrate!r}: {substrate_note}",
        f"attach organ {bp.organ!r}: {_organ_describe(bp.organ)}",
        f"assign Legion crew role {bp.legion_role!r}",
        f"honor claims: {sorted(bp.claims) or 'none'}",
    ]
    if bp.nanobit:
        steps.append(f"package as nanobit format {bp.nanobit!r} (micro-companion)")
    if bp.original:
        steps.append(f"record original lineage: {bp.original!r}")

    return {
        "label": DRY_RUN_LABEL,
        "blueprint": bp.name,
        "fingerprint": bp.fingerprint,
        "validation_checks": checks,
        "would_assemble": {
            "agent": bp.agent,
            "specialist": bp.specialist,
            "substrate": bp.substrate,
            "substrate_status": substrate_status,
            "organ": bp.organ,
            "legion_role": bp.legion_role,
            "nanobit": bp.nanobit or None,
            "original": bp.original or None,
            "claims": sorted(bp.claims),
            "twin_note": bp.twin_note,
        },
        "simulated_steps": steps,
        "live_effects": "none — dry runs never spawn, execute, call, or move",
    }
