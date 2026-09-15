"""
One organism — LEVI × L.W.P. × Factory × Daemon × Memory × Organs.

Not four apps. One interpenetrating symbiotic system.
Every subsystem is a lens on the same body.
"""

from __future__ import annotations

from typing import List, Tuple


# (id, kind_label, name, one-line role in the organism)
ORGANS: List[Tuple[str, str, str, str]] = [
    ("levi.cognition", "core", "LEVI SI", "Adaptive cognition + companion identity"),
    ("lwp.structure", "lwp", "L.W.P.", "Cascade · spiral · governor · breaker · graph"),
    (
        "lwp.mirror",
        "lwp",
        "Mirror Cascade",
        "Parallel forward/reverse/shadow cross-check",
    ),
    ("lwp.rail", "lwp", "Opportunity Rail", "HITL-gated opportunity automation"),
    (
        "factory.dna",
        "factory",
        "Software Factory",
        "Constructive will under L.W.P. stages",
    ),
    (
        "factory.sandbox",
        "factory",
        "Sandbox",
        "Constrained verify of what Factory builds",
    ),
    ("daemon.core", "daemon", "Daemon Core", "Operating layer cycle (not a chatbot)"),
    ("daemon.kernel", "daemon", "Brainstem", "E-stop · cost · bus · tool registry"),
    ("daemon.pulse", "daemon", "Pulse", "Light standing watch"),
    ("demand.pulse", "intel", "DemandPulse", "Need/gap perception"),
    ("income.factory", "intel", "Income Factory", "Offer drafts — capability only"),
    ("memory.corpus", "memory", "Corpus", "OBSERVED/INFERENCE evidence body"),
    ("memory.brain", "memory", "Indexed brain", "Table second brain"),
    ("memory.hierarchy", "memory", "Hierarchy", "Source → … → world model path"),
    ("identity.charter", "identity", "Charter", "Constitution; non-negotiables"),
    ("persona.lattice", "identity", "Persona lattice", "Relational lenses"),
    ("ei.nervous", "identity", "Nervous system", "Affect regulation"),
    ("organ.echo", "organ", "Echo", "Taken / not-taken / wild"),
    ("organ.mandella", "organ", "Mandella", "Stakes under domain pressure"),
    ("policy.hitl", "governance", "HITL", "Human on consequences"),
    (
        "policy.symbiosis",
        "governance",
        "Symbiosis map",
        "Every asset needs its other half",
    ),
    (
        "builder.emergency",
        "builder",
        "E3–E6 Builder",
        "Skeleton → MVP → product under gates",
    ),
    ("model.relay", "runtime", "Model Relay", "Local-first replaceable cognition"),
    ("vault.seal", "runtime", "Vault", "Private at rest"),
    (
        "lwp.model",
        "lwp",
        "L.W.P. Model Engine",
        "Offline SSA literary spine · REIM · void · ROM",
    ),
    (
        "ops.layer",
        "runtime",
        "Operational Layer",
        "Cockpit: pulse+kernel+rail+HITL+relay",
    ),
    ("ops.ui", "surface", "Ops Console UI", "Interactive local control plane"),
    (
        "integrations.free",
        "lattice",
        "Free Integration Lattice",
        "Prehistoric×modern×LEVI free edges",
    ),
    (
        "identity.provenance",
        "identity",
        "Provenance",
        "Closed-source DNA; not a foreign rebrand",
    ),
    (
        "media.pollinations",
        "media",
        "Media stills (reference: Pollinations)",
        "Free beat stills under narrative lock",
    ),
    (
        "runtime.continuity",
        "runtime",
        "Continuity Shelf",
        "Resume pointers across organs",
    ),
    ("runtime.crucible", "runtime", "Crucible", "Constrained trial chamber"),
    ("runtime.watch", "runtime", "Standing Watch", "Local sentinel pulse"),
    ("runtime.services", "runtime", "Service Mesh", "Local capability catalog"),
    (
        "lwp.characters",
        "lwp",
        "Character Graph",
        "Unlimited axis-combinatorial characters",
    ),
    (
        "brain.expand",
        "memory",
        "Corpus Expander",
        "Mass combinatorial offline knowledge",
    ),
]


# Explicit interpenetration edges (a, b, relation) — symbiotic bloodstream
BLOODSTREAM: List[Tuple[str, str, str]] = [
    ("levi.cognition", "lwp.structure", "structured_by"),
    ("levi.cognition", "identity.charter", "bound_by"),
    ("lwp.structure", "factory.dna", "sequences"),
    ("factory.dna", "factory.sandbox", "verified_by"),
    ("factory.dna", "policy.hitl", "gated_by"),
    ("lwp.mirror", "lwp.rail", "cross_checks"),
    ("lwp.rail", "demand.pulse", "fed_by"),
    ("lwp.rail", "income.factory", "drafts_via"),
    ("lwp.rail", "policy.hitl", "locked_by"),
    ("demand.pulse", "income.factory", "symbiosis"),
    ("daemon.core", "daemon.kernel", "rests_on"),
    ("daemon.core", "daemon.pulse", "watched_by"),
    ("daemon.core", "lwp.rail", "can_run"),
    ("daemon.core", "factory.dna", "can_run"),
    ("memory.corpus", "memory.hierarchy", "feeds"),
    ("memory.brain", "memory.hierarchy", "feeds"),
    ("lwp.mirror", "policy.symbiosis", "enforces_value"),
    ("income.factory", "policy.symbiosis", "constrained_by"),
    ("builder.emergency", "factory.dna", "symbiosis"),
    ("builder.emergency", "factory.sandbox", "verified_by"),
    ("persona.lattice", "ei.nervous", "regulated_by"),
    ("persona.lattice", "identity.charter", "cannot_override"),
    ("organ.echo", "organ.mandella", "symbiosis"),
    ("organ.echo", "lwp.mirror", "composes_with"),
    ("model.relay", "levi.cognition", "serves"),
    ("vault.seal", "memory.corpus", "can_protect"),
    ("policy.hitl", "daemon.kernel", "estop_ally"),
    ("lwp.model", "lwp.structure", "embodies"),
    ("lwp.model", "media.pollinations", "may_illustrate"),
    ("ops.layer", "daemon.kernel", "surfaces"),
    ("ops.layer", "lwp.rail", "coordinates"),
    ("ops.ui", "ops.layer", "presents"),
    ("ops.ui", "lwp.model", "links"),
    ("integrations.free", "policy.symbiosis", "enumerates"),
    ("identity.provenance", "identity.charter", "anchors"),
    ("media.pollinations", "lwp.model", "bound_to_beats"),
    ("ops.layer", "model.relay", "reports"),
    ("runtime.continuity", "ops.layer", "feeds"),
    ("runtime.watch", "daemon.pulse", "extends"),
    ("runtime.crucible", "factory.sandbox", "symbiosis"),
    ("runtime.services", "integrations.free", "catalogs"),
]


def format_organism() -> str:
    lines = [
        "=== ONE ORGANISM: LEVI × L.W.P. × Factory ===",
        "",
        "Not separate applications.",
        "Interpenetrating · intertwined · symbiotic.",
        "",
        "┌─ Companion / SI ─── how it relates ─────────────┐",
        "│  Charter · Persona · Nervous · Wit · Core logic │",
        "├─ L.W.P. ─────────── how it structures ──────────┤",
        "│  Cascade · Spiral · Governor · Mirror · Rail    │",
        "├─ Factory ────────── how it builds ──────────────┤",
        "│  Stages · Sandbox · Emergency Builder           │",
        "├─ Daemon ─────────── how it runs ────────────────┤",
        "│  Kernel · Cycle · Pulse · Cost · E-stop         │",
        "├─ Intel ──────────── how it senses value ────────┤",
        "│  DemandPulse × Income Factory (symbiosis)       │",
        "├─ Memory ─────────── how it remembers ───────────┤",
        "│  Corpus · Brain · Hierarchy · Shelf · Vault     │",
        "└─ Governance ─────── how it stays safe ──────────┘",
        "   HITL · Policy · Symbiosis value rules",
        "",
        "── Organs (lenses on the same body) ──",
    ]
    for _oid, kind, name, role in ORGANS:
        lines.append(f"  [{kind:10}] {name:20} {role}")
    lines.append("")
    lines.append("── Bloodstream (sample interpenetration) ──")
    for a, b, rel in BLOODSTREAM[:18]:
        lines.append(f"  {a}  —{rel}→  {b}")
    lines.append(f"  … {len(BLOODSTREAM)} bonds registered in organism map")
    lines.append("")
    lines.append("When you build, converse, automate, or compose — same bloodstream.")
    lines.append(
        "Factory is DNA, not a plugin bolted on. L.W.P. is physics, not a side app."
    )
    return "\n".join(lines)


def register_into_graph() -> str:
    """Push organism nodes/edges into Capability Graph if available."""
    try:
        from levi.graph.interpenetration import (
            InterpenetrationEngine,
            GraphNode,
            NodeKind,
        )

        g = InterpenetrationEngine()
        kind_map = {
            "core": NodeKind.COMPOSITE,
            "lwp": NodeKind.LWP_PRIMITIVE,
            "factory": NodeKind.COMPOSITE,
            "daemon": NodeKind.COMPOSITE,
            "intel": NodeKind.SKILL,
            "memory": NodeKind.MEMORY_TYPE,
            "identity": NodeKind.COMPANION_ROLE,
            "organ": NodeKind.COMPOSITE,
            "governance": NodeKind.SKILL,
            "builder": NodeKind.COMPOSITE,
            "runtime": NodeKind.SKILL,
        }
        for oid, kind, name, role in ORGANS:
            nk = kind_map.get(kind, NodeKind.COMPOSITE)
            if oid not in g.nodes:
                g.nodes[oid] = GraphNode(
                    id=oid,
                    kind=nk,
                    name=name,
                    description=role,
                    risk_ceiling=2,
                    tags=["organism", kind],
                )
        from levi.graph.interpenetration import GraphEdge

        added = 0
        existing = {(e.source_id, e.target_id, e.relation) for e in g.edges}
        for a, b, rel in BLOODSTREAM:
            key = (a, b, rel)
            if key in existing:
                continue
            if a in g.nodes and b in g.nodes:
                g.edges.append(GraphEdge(a, b, rel))
                added += 1
        if hasattr(g, "_persist"):
            try:
                g._persist()
            except Exception:
                pass
        return f"Organism registered: {len(ORGANS)} organs, {added} new bonds"
    except Exception as e:
        return f"Graph register partial: {e}"
