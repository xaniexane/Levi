"""canon_registry: the canon COMPONENT registry around the 32-engine tensor.

Chauncey's order (2026-09-22): "add DemandPulse, Echo, Alpha, the platform
hub, creation lab, every other edition and new addition etc." This registry
is the answer: canon components that sit AROUND the engine tensor, never
inside it.

LAW L1: the engine tensor stays exactly 32 x 64 x 128. Components are NOT
engines; registering anything engine-like raises loudly. There is never a
33rd engine.

LAW L2: every component carries a source. No invented descriptions —
entries whose definition is not yet his are marked PENDING, and a guard
test enforces the marker.

LAW L3: DemandPulse the product and the demandpulse_engine (a canon engine
in the tensor) are recorded separately, never conflated.

Module name is provisional — his word later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .engine_map import ENGINE_TENSOR_SHAPE, ENGINE_TENSOR_TOTAL

ENGINE_SOURCE_STATUS = "historic canon per Chauncey's 2026-09-22 ruling"

# Allowed canon statuses.
HISTORIC_CANON = "historic-canon"
ESSENCE_PENDING = "essence-pending-ruling"
DEFINITION_PENDING = "definition-pending"
CANON_STATUSES = (HISTORIC_CANON, ESSENCE_PENDING, DEFINITION_PENDING)

# "engine" is deliberately absent: engines live in the tensor, never here.
COMPONENT_KINDS = (
    "engine_tensor",
    "entity",
    "platform",
    "product+engine",
    "component",
    "edition",
)


def _entry(
    *,
    id: str,
    display: str,
    kind: str,
    canon_status: str,
    description: str,
    source: str,
) -> Dict[str, Any]:
    if not id:
        raise ValueError("component id required")
    if not display:
        raise ValueError("display name required")
    if kind not in COMPONENT_KINDS:
        raise ValueError(f"unknown component kind: {kind!r}")
    if canon_status not in CANON_STATUSES:
        raise ValueError(f"unknown canon status: {canon_status!r}")
    if not description:
        raise ValueError("description required")
    if not source:
        raise ValueError(f"L2: {id!r} has no source; every component must carry one")
    if canon_status == DEFINITION_PENDING and not description.startswith("PENDING"):
        raise ValueError(
            f"L2: definition-pending component {id!r} must carry the PENDING marker"
        )
    return {
        "id": id,
        "display": display,
        "kind": kind,
        "canon_status": canon_status,
        "description": description,
        "source": source,
    }


def _base_components() -> Dict[str, Dict[str, Any]]:
    return {
        "engine_tensor": _entry(
            id="engine_tensor",
            display="Omega engine tensor",
            kind="engine_tensor",
            canon_status=HISTORIC_CANON,
            description=(
                "The 32 engines as 32x64x128 (262144 values). Historic canon "
                "per Chauncey's 2026-09-22 ruling. What the 64 and 128 axes "
                "represent is his to define (open)."
            ),
            source="screenshot batches 1+2; MEMORY.md Omega historic-canon section",
        ),
        "echo": _entry(
            id="echo",
            display="Echo",
            kind="entity",
            canon_status=HISTORIC_CANON,
            description=(
                "His words: Echo is not a separate being — it is the entity's "
                "original form/name, the same being as Omega at different "
                "times, seated before Alpha + Omega (the era before Alpha "
                "existed). The name 'Nexus' was taken, so the entity was "
                "renamed and reimagined as Omega; 'Echo' is the retired "
                "original name, same being."
            ),
            source="MEMORY.md (Chauncey, 2026-09-20)",
        ),
        "alpha": _entry(
            id="alpha",
            display="Alpha",
            kind="entity",
            canon_status=HISTORIC_CANON,
            description=(
                "His words: Alpha is the builder twin — automation workflows "
                "are its special. Alpha builds the workflows; Omega executes "
                "them as the always-on daemon. Engine as well as seat "
                "(core/levi/alpha/)."
            ),
            source="MEMORY.md (Chauncey, 2026-09-22)",
        ),
        "platform_hub": _entry(
            id="platform_hub",
            display="Platform hub",
            kind="platform",
            canon_status=HISTORIC_CANON,
            description=(
                "His words: the Alpha/Omega hub shell — core/levi/hub/. "
                "Its alpha module docstring calls it 'the creation lab INSIDE "
                "the hub': Echo (blueprint architect) designs the spec, "
                "Alpha (no-code compiler) compiles it."
            ),
            source="core/levi/hub/ (hub/alpha.py docstring); Chauncey's chat order 2026-09-22",
        ),
        "demandpulse": _entry(
            id="demandpulse",
            display="DemandPulse",
            kind="product+engine",
            canon_status=HISTORIC_CANON,
            description=(
                "His words: DemandPulse scans -> scores -> surfaces; "
                "deterministic, real signals only. The DemandPulse ENGINE "
                "(canon engine in the tensor, with a response flowchart) is "
                "distinct from the DemandPulse PRODUCT — never conflated (L3)."
            ),
            source="MEMORY.md; engine_map.py (canon engine); screenshot batch 2",
        ),
        "creation_lab": _entry(
            id="creation_lab",
            display="Creation lab",
            kind="component",
            canon_status=DEFINITION_PENDING,
            description=(
                "PENDING Chauncey's definition — his new term (2026-09-22). "
                "Related, not a definition: core/levi/hub/alpha.py docstring "
                "describes 'the creation lab INSIDE the hub' (Echo designs "
                "the blueprint, Alpha compiles it through template generators)."
            ),
            source="Chauncey's chat order 2026-09-22; core/levi/hub/alpha.py",
        ),
        "edition_enterprise": _entry(
            id="edition_enterprise",
            display="Enterprise edition",
            kind="edition",
            canon_status=ESSENCE_PENDING,
            description=(
                "PENDING his canon ruling: the Enterprise edition sheet from "
                "screenshot batch 1 (Copilot-rendered Omega material). "
                "Essence only until he rules."
            ),
            source="screenshot batch 1 (edition sheets)",
        ),
        "edition_government": _entry(
            id="edition_government",
            display="Government edition",
            kind="edition",
            canon_status=ESSENCE_PENDING,
            description=(
                "PENDING his canon ruling: the Government edition sheet from "
                "screenshot batch 1 (Copilot-rendered Omega material). "
                "Essence only until he rules."
            ),
            source="screenshot batch 1 (edition sheets)",
        ),
        "edition_personal": _entry(
            id="edition_personal",
            display="Personal edition",
            kind="edition",
            canon_status=ESSENCE_PENDING,
            description=(
                "PENDING his canon ruling: the Personal edition sheet from "
                "screenshot batch 1 (Copilot-rendered Omega material). "
                "Essence only until he rules."
            ),
            source="screenshot batch 1 (edition sheets)",
        ),
    }


CANON_COMPONENTS: Dict[str, Dict[str, Any]] = _base_components()


def _check_laws() -> None:
    # L1: tensor stays exactly 32 x 64 x 128.
    assert ENGINE_TENSOR_SHAPE == (32, 64, 128), "tensor shape drifted"
    assert ENGINE_TENSOR_TOTAL == 32 * 64 * 128, "tensor total drifted"
    # L1: no engine-kind components — there is never a 33rd engine.
    for comp_id, comp in CANON_COMPONENTS.items():
        assert comp["kind"] != "engine", f"L1 violated: {comp_id!r} is engine-kind"
    # L2: every component carries a source and valid status.
    for comp_id, comp in CANON_COMPONENTS.items():
        assert comp["source"], f"L2 violated: {comp_id!r} has no source"
        assert comp["canon_status"] in CANON_STATUSES


_check_laws()


def get_component(component_id: str) -> Dict[str, Any]:
    """Return the registry entry for ``component_id``; raise loudly if unknown."""
    try:
        return CANON_COMPONENTS[component_id]
    except KeyError:
        raise KeyError(f"unknown canon component: {component_id!r}") from None


def components(
    kind: Optional[str] = None, canon_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List registry entries, optionally filtered by kind and/or status."""
    result = list(CANON_COMPONENTS.values())
    if kind is not None:
        if kind not in COMPONENT_KINDS:
            raise ValueError(f"unknown component kind: {kind!r}")
        result = [c for c in result if c["kind"] == kind]
    if canon_status is not None:
        if canon_status not in CANON_STATUSES:
            raise ValueError(f"unknown canon status: {canon_status!r}")
        result = [c for c in result if c["canon_status"] == canon_status]
    return result


def pending_definitions() -> List[Dict[str, Any]]:
    """Everything still awaiting his word: definition-pending or essence-pending."""
    return [
        c
        for c in CANON_COMPONENTS.values()
        if c["canon_status"] in (DEFINITION_PENDING, ESSENCE_PENDING)
    ]


def register_canon_component(
    *,
    id: str,
    display: str,
    kind: str,
    canon_status: str,
    description: str,
    source: str,
) -> Dict[str, Any]:
    """Extension point for "new addition etc".

    Process: new canon material arrives (his word, screenshots, code) ->
    add via this function with the real source, display name in his words,
    and the honest status (historic-canon only on his explicit ruling;
    definition-pending with a PENDING marker until he defines it).

    Raises on duplicate ids, unknown kinds, unknown statuses, and any
    attempt to register engine-kind components (L1: never a 33rd engine).
    """
    if id in CANON_COMPONENTS:
        raise ValueError(f"canon component already registered: {id!r}")
    if kind == "engine":
        raise ValueError(
            "L1: engines live in the 32-engine tensor, never in this registry"
        )
    entry = _entry(
        id=id,
        display=display,
        kind=kind,
        canon_status=canon_status,
        description=description,
        source=source,
    )
    CANON_COMPONENTS[id] = entry
    _check_laws()
    return entry


def dump() -> Dict[str, Any]:
    """JSON-compatible snapshot of the registry."""
    return {
        "engine_tensor_shape": list(ENGINE_TENSOR_SHAPE),
        "engine_source_status": ENGINE_SOURCE_STATUS,
        "components": {k: dict(v) for k, v in CANON_COMPONENTS.items()},
    }


def load(data: Dict[str, Any]) -> None:
    """Validate and restore a registry snapshot from :func:`dump`.

    Re-registers any extra components found in the snapshot (validated
    through the same law checks); raises loudly on anything invalid.
    """
    if not isinstance(data, dict) or "components" not in data:
        raise ValueError("invalid canon registry snapshot")
    shape = tuple(data.get("engine_tensor_shape", ()))
    if shape != (32, 64, 128):
        raise ValueError(f"L1: snapshot tensor shape is not 32x64x128: {shape!r}")
    for comp_id, entry in data["components"].items():
        if comp_id not in CANON_COMPONENTS:
            register_canon_component(
                id=entry["id"],
                display=entry["display"],
                kind=entry["kind"],
                canon_status=entry["canon_status"],
                description=entry["description"],
                source=entry["source"],
            )
    _check_laws()
