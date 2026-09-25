"""Production readiness table — prehistoric + modern + LEVI-unique engines."""

from __future__ import annotations

from typing import List, Tuple


# Engine registry: era, name, role, status
ENGINES: List[Tuple[str, str, str, str]] = [
    # Prehistoric / classical (proven primitives)
    ("prehistoric", "File-backed state", "~/.levi JSON persistence", "prod"),
    ("prehistoric", "CLI operator surface", "argparse local control plane", "prod"),
    ("prehistoric", "pytest gate", "Regression as merge authority", "prod"),
    (
        "prehistoric",
        "HITL approval cards",
        "Human on consequences (silence≠yes)",
        "prod",
    ),
    ("prehistoric", "Emergency stop", "Hard kill switch on kernel", "prod"),
    # Modern industry patterns (original implementations)
    (
        "modern",
        "Model relay chain",
        "Local model runner (reference: Ollama) → offline synth; cloud config-ready",
        "prod",
    ),
    ("modern", "Event bus / daemon cycle", "OBSERVE…OPTIMIZE operating loop", "prod"),
    ("modern", "Capability log", "Skill/automation memory of work done", "prod"),
    ("modern", "Sandbox smoke", "Post-scaffold verify without deploy", "prod"),
    ("modern", "Corpus evidence layers", "OBSERVED / INFERENCE / HYPOTHESIS", "prod"),
    ("modern", "CI fast_gate", "pytest+integrate+ladder+relay", "prod"),
    # LEVI-unique
    (
        "levi-unique",
        "L.W.P. physics",
        "Cascade, spiral, governor, Mirror coils",
        "prod",
    ),
    (
        "levi-unique",
        "L.W.P. Model Engine",
        "Offline SSA literary spine; REIM/void/ROM; UI+CLI",
        "prod",
    ),
    ("levi-unique", "Mirror Cascade", "Forward + reverse + shadow cross-check", "prod"),
    ("levi-unique", "Opportunity Rail", "SIGNAL→…→DONE HITL automation spine", "prod"),
    (
        "levi-unique",
        "Organism interpenetration",
        "One bloodstream, not side apps",
        "prod",
    ),
    (
        "levi-unique",
        "Charter (bound soul)",
        "Editable identity; cannot kill HITL/crisis",
        "prod",
    ),
    (
        "levi-unique",
        "Nervous system + tone",
        "Stress/bond persona selection, crisis mute wit",
        "prod",
    ),
    (
        "levi-unique",
        "Hardwired core logic",
        "Alchemy, life equation, life chess, radical honesty",
        "prod",
    ),
    (
        "levi-unique",
        "Symbiosis pairs",
        "Demand↔Income; every asset needs other half",
        "prod",
    ),
    (
        "levi-unique",
        "Story fabric genres",
        "Cascade beats + social_media + abridged_series",
        "prod",
    ),
    ("levi-unique", "Echo / Mandella organs", "Parallel path + stake organs", "prod"),
    (
        "levi-unique",
        "Factory under L.W.P.",
        "Software Factory as DNA not separate product",
        "prod",
    ),
    (
        "levi-unique",
        "Ugly truth / constructive discomfort",
        "Director not pleaser",
        "prod",
    ),
    ("levi-unique", "Monotropism tracker", "Tunnel depth under focus load", "prod"),
    (
        "modern",
        "Media stills (reference: Pollinations)",
        "Optional image URL generation for beats",
        "prod",
    ),
    ("modern", "E3–E6 Emergency Builder", "Scaffold→MVP under HITL", "prod"),
    ("modern", "Operational layer", "Single cockpit: pulse+kernel+rail+HITL", "prod"),
    (
        "levi-unique",
        "Continuity Shelf",
        "Cross-organ resume pointers local JSON",
        "prod",
    ),
    ("levi-unique", "Crucible", "Constrained syntax/file/literal chamber", "prod"),
    ("levi-unique", "Standing Watch", "Cron-ready local sentinel", "prod"),
    ("levi-unique", "Service Mesh", "Local capability catalog", "prod"),
    ("levi-unique", "Offline Brain Atlas", "A-Z+ seed knowledge corpus", "prod"),
    ("deferred", "Fat interactive UI", "Connector ports / organs UI", "defer"),
    ("deferred", "Live multi-cloud billing", "Paid APIs required path", "defer"),
    ("deferred", "Glyph compressed memory", "Deep hierarchy compress", "defer"),
]


def production_table() -> str:
    lines = [
        "=== LEVI PRODUCTION TABLE ===",
        "Prehistoric engines + modern patterns + LEVI-unique DNA",
        "",
        f"{'ERA':<14} {'ENGINE':<32} {'ROLE':<48} {'STATUS'}",
        "-" * 110,
    ]
    prod = defer = 0
    for era, name, role, status in ENGINES:
        lines.append(f"{era:<14} {name:<32} {role:<48} {status}")
        if status == "prod":
            prod += 1
        else:
            defer += 1
    lines.append("-" * 110)
    lines.append(f"PRODUCTION-ready engines: {prod}  |  Deferred: {defer}")
    lines.append("")
    lines.append(
        "Continuous regime: scripts/fast_gate.sh on every change · levi go daily · HITL on consequences"
    )
    lines.append(
        "Deploy regime: local-first package only — no silent cloud deploy. Private git when scopes allow."
    )
    lines.append("")
    lines.append("=== DEFERRED ENGINES (clarified) ===")
    lines.append(
        "Fat interactive UI     — not required for complete-below-enterprise; CLI+ops is the control plane"
    )
    lines.append(
        "Live multi-cloud billing — would force paid path; violates free-first / local-first for core"
    )
    lines.append(
        "Glyph compressed memory — optimization layer; corpus+brain already operable; compress later"
    )
    lines.append(
        "These are intentional non-goals for v1 complete, not abandoned architecture."
    )
    return "\n".join(lines)
