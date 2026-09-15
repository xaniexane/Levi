"""
LEVI provenance — closed-source original design.

Explicitly NOT a rebrand of Kai 9000 or any third-party agent shell.
Patterns may resemble industry practice; implementations, names, DNA,
and governance (HITL, L.W.P., organism, Mirror, Rail, Charter) are LEVI-original.
"""

from __future__ import annotations

PROVENANCE = {
    "product": "LEVI × L.W.P.",
    "license": "proprietary",
    "closed_source": True,
    "not_a_fork_of": [
        "Kai 9000",
        "OpenAI Assistants API product",
        "generic multi-agent frameworks as drop-in clones",
    ],
    "unique_dna": [
        "L.W.P. physics (cascade, spiral, governor, Mirror coils)",
        "Opportunity Rail HITL spine",
        "Organism interpenetration graph",
        "Charter bound soul (cannot disable HITL/crisis)",
        "Hardwired core logic (alchemy, life equation, life chess)",
        "Symbiosis value rules (no manufactured need)",
        "L.W.P. Model offline SSA literary engine",
        "Nervous system + monotropism interaction physics",
        "Continuity Shelf / Crucible / Standing Watch / Service Mesh",
    ],
    "allowed_inspiration": "Industry patterns only — original code and names under LEVI copyright.",
}


def provenance_report() -> str:
    lines = [
        "=== LEVI Provenance (closed source) ===",
        f"Product: {PROVENANCE['product']}",
        f"License: {PROVENANCE['license']} · closed_source={PROVENANCE['closed_source']}",
        "",
        "NOT a fork/rebrand of:",
    ]
    for x in PROVENANCE["not_a_fork_of"]:
        lines.append(f"  ✗ {x}")
    lines.append("")
    lines.append("Unique DNA:")
    for x in PROVENANCE["unique_dna"]:
        lines.append(f"  · {x}")
    lines.append("")
    lines.append(PROVENANCE["allowed_inspiration"])
    return "\n".join(lines)


def scan_tree_for_foreign_branding(root: str = ".") -> str:
    """Soft audit: flag accidental Kai/OpenDevin drop-in strings in source (not docs)."""
    from pathlib import Path

    hits = []
    banned = ("kai 9000", "kai9000", "opendevin", "devin ai")
    base = Path(root)
    for p in base.rglob("*.py"):
        if any(x in p.parts for x in ("__pycache__", ".git", "tests")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for b in banned:
            if (
                b in text
                and "not_a_fork" not in text
                and "provenance" not in str(p).lower()
            ):
                # allow provenance module itself
                if "provenance" in p.name:
                    continue
                hits.append(f"{p}: mentions '{b}'")
    if not hits:
        return "Foreign-brand scan: clean (no accidental Kai/clone branding in source)."
    return "Foreign-brand scan FLAGS:\n  " + "\n  ".join(hits[:20])
