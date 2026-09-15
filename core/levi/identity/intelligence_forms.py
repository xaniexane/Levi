"""
Intelligence forms that can integrate with LEVI SI (Synthetic Intelligence).

SI remains the core identity: constructed substrate, non-personhood, HITL.
Other forms are *layers or partners*, not replacements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class IntelForm:
    id: str
    name: str
    role_with_si: str
    already_in_levi: str
    caution: str


FORMS: List[IntelForm] = [
    IntelForm(
        "synthetic",
        "Synthetic Intelligence (SI)",
        "Core identity — engineered cognition substrate",
        "si pillars, LEVI registers, offline core",
        "Do not claim consciousness or personhood",
    ),
    IntelForm(
        "symbolic",
        "Symbolic / classical AI",
        "Rules, planners, checklists, deterministic organs",
        "HITL domains, enterprise checklist, story cascade rules, scorecard",
        "Brittle if treated as complete world model",
    ),
    IntelForm(
        "neural_optional",
        "Neural / statistical models",
        "Optional boost when local LLM (Ollama etc.) present",
        "ask path, optional enhance in story_fabric",
        "Never required for core usefulness",
    ),
    IntelForm(
        "narrative",
        "Narrative intelligence",
        "Story structure, scar law, genre contracts",
        "L.W.P. SSA, story_prose, rupture scarcity",
        "Do not aestheticize real harm",
    ),
    IntelForm(
        "affective_routing",
        "Affective routing (not fake emotion)",
        "Stress/anxiety/bond → register and wit intensity",
        "nervous_system, monotropism, Care register",
        "No claimed feelings; no manipulation",
    ),
    IntelForm(
        "collective_hitl",
        "Collective intelligence under HITL",
        "Teams, shared projects, multi-approver gates",
        "Phase C map, enterprise seats (design)",
        "No silent swarm actions on consequential paths",
    ),
    IntelForm(
        "institutional",
        "Institutional intelligence",
        "Runbooks, audits, compliance-as-code",
        "enterprise checklist, stress harness, retention logs",
        "Process without dignity becomes bureaucracy theater",
    ),
    IntelForm(
        "embodied_optional",
        "Embodied / sensor intelligence",
        "Future: local device sensors, robotics hooks",
        "roadmap only — not required",
        "Privacy + HITL on any actuator",
    ),
    IntelForm(
        "augmented_human",
        "Augmented human intelligence",
        "Symbiotic method — human remains authority",
        "HITL, export, crisis floor, morning/continue",
        "SI amplifies; does not replace judgment",
    ),
    IntelForm(
        "systems_ecological",
        "Systems / ecological intelligence",
        "Feedback, leverage, second-order effects",
        "corpus systems pack, LEVI Oracle/Architect",
        "Models are maps; label uncertainty",
    ),
]


def format_forms() -> str:
    lines = [
        "══ Intelligence forms × LEVI SI ══",
        "Core stays Synthetic Intelligence. Others integrate as layers/partners.",
        "",
    ]
    for f in FORMS:
        lines.append(f"● {f.name}  [{f.id}]")
        lines.append(f"  role:     {f.role_with_si}")
        lines.append(f"  in LEVI:  {f.already_in_levi}")
        lines.append(f"  caution:  {f.caution}")
        lines.append("")
    lines.append("SI is the spine. Neural is optional muscle. Human is the authority.")
    return "\n".join(lines)
