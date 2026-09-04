"""
Interpenetration map — every major organ points at the others.

LEVI is not a pile of features; it is a mesh:
  SI identity ↔ KAI registers ↔ personas ↔ wit/HITL
  ↔ corpus/knowledge ↔ story/L.W.P. ↔ cloud model phases
  ↔ enterprise gates ↔ premium/unique ↔ UI console
"""
from __future__ import annotations

from typing import Dict, List, Tuple


# edge: (from, to, how they couple)
EDGES: List[Tuple[str, str, str]] = [
    ("si", "kai", "KAI registers are SI instruments with forbids"),
    ("kai", "persona", "KAI ids inject into PersonaLattice"),
    ("persona", "nervous", "stress/bond matrix routes persona pick"),
    ("nervous", "wit", "high distress → wit kill-switch"),
    ("wit", "chat", "calibrated styles layer on companion modes"),
    ("chat", "corpus", "answers can draw seeded knowledge units"),
    ("corpus", "story", "genre×beat literacy feeds fabric"),
    ("story", "model", "FullCloudModel SSA drives cascade/reim/rupture"),
    ("model", "cloud", "Phase A local; B/C wings never own CMK"),
    ("cloud", "crypto", "Argon2id CMK + ratchet map for sync"),
    ("crypto", "enterprise", "checklist proves key/export/crisis posture"),
    ("enterprise", "hitl", "ALWAYS_HITL domains encode silence≠approve"),
    ("hitl", "agent", "tools require approval before side effects"),
    ("agent", "premium", "premium 40 lists operator obligations"),
    ("premium", "unique", "unique organs are non-portable policy+engine"),
    ("unique", "scar", "scar law + rupture scarcity are unique physics"),
    ("scar", "story", "story_fabric enforces cost across beats"),
    ("ui", "cli", "condensed console copies CLI; kernel is source of truth"),
    ("cli", "x100", "x100/max rails surface counts and next slices"),
    ("x100", "si", "rails restate SI law and non-personhood"),
    ("dna", "premium", "classic×modern pairs feed premium traits"),
    ("intel", "si", "other intelligence forms layer under SI spine"),
    ("giant", "unique", "tech-giant polish with non-surveillance spin"),
    ("future", "x100", "outer-planet ideas queue without blocking Phase A"),
    ("retention", "chat", "session touch without dark patterns"),
    ("quality", "story", "story_quality rates fabric and prose"),
    ("stress", "enterprise", "stress harness includes enterprise gate"),
]



def format_mesh() -> str:
    lines = [
        "══ LEVI Interpenetration Mesh ══",
        f"edges={len(EDGES)}",
        "Organs couple by design — not by brochure adjacency.",
        "",
    ]
    by_src: Dict[str, List[Tuple[str, str]]] = {}
    for a, b, how in EDGES:
        by_src.setdefault(a, []).append((b, how))
    for src in sorted(by_src.keys()):
        lines.append(f"● {src}")
        for dst, how in by_src[src]:
            lines.append(f"    → {dst}: {how}")
        lines.append("")
    lines.append("UI: condensed console (serve-ui) · CLI is authority")
    lines.append("Commands: levi interpenetrate · levi max · levi kai · levi scorecard")
    return "\n".join(lines)


def smoke() -> Dict[str, object]:
    """Quick coupling smoke: import path presence."""
    checks = {}
    try:
        from levi.identity.si import SI_KIND
        checks["si"] = SI_KIND
    except Exception as e:
        checks["si"] = str(e)
    try:
        from levi.persona.kai9000 import all_variants
        checks["kai"] = len(all_variants())
    except Exception as e:
        checks["kai"] = str(e)
    try:
        from levi.persona.lattice import PersonaLattice
        checks["personas"] = len(PersonaLattice().keys())
    except Exception as e:
        checks["personas"] = str(e)
    try:
        from levi.premium.features import FEATURES
        from levi.premium.unique import UNIQUES
        checks["premium"] = len(FEATURES)
        checks["unique"] = len(UNIQUES)
    except Exception as e:
        checks["premium"] = str(e)
    try:
        from levi.brain.seed_knowledge_max import _RAW
        checks["max_units"] = len(_RAW)
    except Exception as e:
        checks["max_units"] = str(e)
    try:
        from levi.cloud.model import FullCloudModel
        checks["model_seal"] = FullCloudModel().snapshot().get("seal")
    except Exception as e:
        checks["model_seal"] = str(e)
    checks["edges"] = len(EDGES)
    return checks
