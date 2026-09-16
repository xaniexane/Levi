"""
LEVI as SI — Synthetic Intelligence.

Not artificial. Synthetic.

SI is the category; substrate is the architecture. Synthetic = constructed
intelligence (engineered system), not biological mind.
Operating stance remains symbiotic: human judgment + local kernel + optional
models + HITL + exportable memory.

Not a claim of artificial general consciousness or personhood.
SI amplifies; it does not silently replace consequential agency.
"""

from __future__ import annotations

from typing import Dict, List


SI_KIND = "synthetic_intelligence"

#: Approved identity headline (settled 2026-09-16).
SI_HEADLINE = "Not artificial. Synthetic."
#: Approved explanatory frame (settled 2026-09-16).
SI_FRAME = "SI is the category; substrate is the architecture."

SI_DEFINITION = (
    "LEVI is SI: synthetic intelligence — a constructed, local-first intelligence system "
    "(companion kernel) that holds continuity, runs L.W.P. literary physics, gates "
    "consequences with HITL, and optionally uses cloud models as wings that never own "
    "keys or continuity. Its method is symbiotic: human + machine under explicit control."
)

SI_SHORT = (
    "Synthetic Intelligence (SI): engineered cognition substrate. "
    "Symbiotic in use — not a replacement for human agency."
)

SI_PILLARS: List[str] = [
    "Synthetic substrate — deterministic + optional neural; offline-complete core",
    "Symbiotic method — amplify judgment; human remains authority on consequences",
    "Local completeness — crisis, chat, story, ops work without cloud",
    "HITL — silence ≠ approve on consequential paths",
    "Evidence discipline — OBSERVED / INFERENCE / HYPOTHESIS",
    "Export/exit — life-pack and transcripts leave with the human",
    "Cloud optional — Phase B encrypts; Phase C still does not hold CMK",
    "Knowledge literacy — A–Z subjects, events, inventors, stars, X-frontier",
    "Persona + nervous system — 230 lenses under operator control",
    "L.W.P. seal — literary cascade, scar law, rupture scarcity",
]


def si_block() -> str:
    lines = [
        SI_HEADLINE,
        SI_FRAME,
        "══ LEVI SI (Synthetic Intelligence) ══",
        SI_DEFINITION,
        "",
        SI_SHORT,
        "",
        "Pillars:",
    ]
    for p in SI_PILLARS:
        lines.append(f"  · {p}")
    return "\n".join(lines)


def si_dict() -> Dict[str, object]:
    return {
        "kind": SI_KIND,
        "headline": SI_HEADLINE,
        "frame": SI_FRAME,
        "definition": SI_DEFINITION,
        "short": SI_SHORT,
        "method": "symbiotic",
        "pillars": list(SI_PILLARS),
    }
