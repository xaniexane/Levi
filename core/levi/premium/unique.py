"""
Unique · hard-to-replicate LEVI organs.

These are not generic chatbot features. They encode specific physics,
policy, and literary law that do not port by prompt alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class UniqueOrgan:
    id: str
    name: str
    unreplicable_because: str
    surface: str


UNIQUES: List[UniqueOrgan] = [
    UniqueOrgan(
        "lwp_scar_law",
        "Scar law (L.W.P.)",
        "Wounds persist across beats by engine rule — not optional style guide",
        "levi story / levi model",
    ),
    UniqueOrgan(
        "lwp_rupture_scarcity",
        "Rupture scarcity",
        "High-cost narrative breaks are metered; cheap resets refused",
        "levi model rupture",
    ),
    UniqueOrgan(
        "lwp_ssa_cascade",
        "SSA literary cascade",
        "Deterministic-ish story fabric organs (REIM/RIEM/ROM) as code, not vibes",
        "levi model expand|reim|crown",
    ),
    UniqueOrgan(
        "silence_neq_approve",
        "Silence ≠ approve",
        "HITL policy encoded in ALWAYS_HITL domains — cultural rule in software",
        "levi enterprise",
    ),
    UniqueOrgan(
        "crisis_wit_kill",
        "Crisis wit kill-switch",
        "Comedy spectrum hard-muted under distress — not a prompt suggestion",
        "levi wit + offline companion",
    ),
    UniqueOrgan(
        "kai9000_family",
        "KAI-9000 register family",
        "Original LEVI SI registers (concept reverse-engineered & heavily modified; not third-party source)",
        "levi kai",
    ),
    UniqueOrgan(
        "evidence_trinity",
        "OBSERVED / INFERENCE / HYPOTHESIS",
        "Epistemic labels as first-class memory discipline",
        "levi brain / forensic KAI",
    ),
    UniqueOrgan(
        "monotropism_tunnel",
        "Monotropism tunnel tracker",
        "Interest-depth + switch-cost model biasing persona/wit",
        "levi mono",
    ),
    UniqueOrgan(
        "nervous_matrix",
        "Nervous system → persona matrix",
        "Stress/anxiety/workload/bond drive routing, not random temperature",
        "persona/nervous_system.py",
    ),
    UniqueOrgan(
        "alchemy_no_pure_loss",
        "Alchemy: no pure loss",
        "Transformation framing that forbids total erase narratives",
        "levi daemon alchemy",
    ),
    UniqueOrgan(
        "life_equation",
        "Life equation x+y=z",
        "Structured trade-off algebra for personal systems",
        "levi organs / status",
    ),
    UniqueOrgan(
        "phase_abc_crypto_map",
        "Phase A/B/C + CMK never leaves device",
        "Cloud as wing architecture with explicit key ownership law",
        "levi cloud / scorecard",
    ),
    UniqueOrgan(
        "premium_25_dna",
        "Premium 25 classic×modern DNA map",
        "Retired software lineage treated as design law, not nostalgia",
        "levi premium",
    ),
    UniqueOrgan(
        "gold_path_cascade",
        "Gold-path long manuscript organ",
        "Batch literary generation under scar-aware cascade",
        "levi model manuscript",
    ),
    UniqueOrgan(
        "si_not_personhood",
        "SI identity without personhood claim",
        "Synthetic Intelligence defined with explicit non-consciousness stance",
        "levi si",
    ),
    UniqueOrgan(
        "kai_register_matrix",
        "KAI register matrix (12)",
        "Twelve original LEVI SI registers — reverse-engineered concept, heavily modified; not third-party source",
        "levi kai",
    ),
    UniqueOrgan(
        "glass_operator_face",
        "Glass operator face",
        "Premium textured interactive console as first-class local surface",
        "levi serve-ui",
    ),
    UniqueOrgan(
        "x100_upgrade_rail",
        "×100 upgrade rail",
        "Explicit aggressive improvement surface: status, gates, next slices",
        "levi x100",
    ),
    UniqueOrgan(
        "corpus_heavy_az",
        "Heavy A–Z knowledge spine",
        "Depth subjects + inventors + events + stars + X-frontier as seed law",
        "levi brain --seed-knowledge-heavy",
    ),
    UniqueOrgan(
        "enterprise_checklist_gate",
        "Enterprise checklist gate",
        "11-point readiness as runnable software, not a slide",
        "levi enterprise",
    ),
    UniqueOrgan(
        "x10_pack",
        "×10 densification wave",
        "Second corpus physics layer coupled to interpenetration drills",
        "levi brain --seed-x10",
    ),
    UniqueOrgan(
        "kai_not_third_party",
        "KAI not third-party source",
        "Explicit attribution: original LEVI, heavily modified concept",
        "levi kai",
    ),
    UniqueOrgan(
        "ui_cli_authority_split",
        "UI/CLI authority split",
        "Condensed face never owns keys or continuity",
        "levi serve-ui / interpenetrate",
    ),
    UniqueOrgan(
        "mesh_20_edges",
        "Interpenetration mesh edges",
        "Coupling graph as software, not marketing adjacency",
        "levi interpenetrate",
    ),
    UniqueOrgan(
        "max10_combined_rail",
        "MAX×10 combined rail",
        "Single operator view of densest corpus + law",
        "levi max10",
    ),
]


def format_uniques() -> str:
    lines = [
        "══ Unique · unreplicable LEVI organs ══",
        f"count={len(UNIQUES)}",
        "These do not survive as pure prompts — they are engine + policy.",
        "",
    ]
    for i, u in enumerate(UNIQUES, 1):
        lines.append(f"{i:2}. {u.name}")
        lines.append(f"    because: {u.unreplicable_because}")
        lines.append(f"    surface: {u.surface}")
        lines.append("")
    return "\n".join(lines)
