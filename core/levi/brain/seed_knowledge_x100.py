
"""×100 knowledge densification — high-signal operators pack."""
from __future__ import annotations
from typing import Iterator, List, Tuple

_RAW: List[Tuple[str, str, Tuple[str, ...]]] = []

_PACK = [
    ("Systems — leverage points: numbers, buffers, feedback, rules, goals, paradigm (Meadows literacy).", "OBSERVED", ("x100", "systems")),
    ("Systems — delay in feedback creates oscillation; slow the policy before adding gain.", "OBSERVED", ("x100", "systems")),
    ("Decision — OODA: observe, orient, decide, act; orientation quality dominates speed.", "OBSERVED", ("x100", "decision")),
    ("Decision — reversible vs irreversible: prefer options that keep future choices open.", "OBSERVED", ("x100", "decision")),
    ("Writing — scene shows pressure; summary moves time; mix on purpose.", "OBSERVED", ("x100", "writing")),
    ("Writing — specificity is a kindness; abstraction stacks hide risk.", "OBSERVED", ("x100", "writing")),
    ("Security — assume breach; minimize blast radius; rotate secrets; least privilege.", "OBSERVED", ("x100", "security")),
    ("Security — threat model before control shopping list.", "OBSERVED", ("x100", "security")),
    ("SI ops — labels over vibes: OBSERVED / INFERENCE / HYPOTHESIS on material claims.", "OBSERVED", ("x100", "si")),
    ("SI ops — HITL on consequential paths; silence is not consent.", "OBSERVED", ("x100", "si")),
    ("SI ops — export/exit is a feature; lock-in is a defect.", "OBSERVED", ("x100", "si")),
    ("Story — scar law: prior compromise still collects; do not reset for convenience.", "OBSERVED", ("x100", "story")),
    ("Story — rupture is scarce; spend it when the world model must break.", "OBSERVED", ("x100", "story")),
    ("Cognition — externalize state; working memory is narrow.", "OBSERVED", ("x100", "cognition")),
    ("Cognition — monotropism: protect deep tunnels; budget switch cost.", "OBSERVED", ("x100", "cognition")),
    ("Math — expected value needs both magnitude and probability; vividness is not probability.", "OBSERVED", ("x100", "math")),
    ("Math — base rates before case details when predicting.", "OBSERVED", ("x100", "math")),
    ("History — institutions are technologies; they have failure modes.", "OBSERVED", ("x100", "history")),
    ("History — primary sources beat slogan summaries for high-stakes claims.", "OBSERVED", ("x100", "history")),
    ("Engineering — measure twice; ship a thin vertical slice; verify.", "OBSERVED", ("x100", "engineering")),
    ("Engineering — observability is part of the product, not an afterthought.", "OBSERVED", ("x100", "engineering")),
    ("Ethics — means that corrupt the ends are not neutral tools.", "OBSERVED", ("x100", "ethics")),
    ("Ethics — dignity constraints are design inputs, not PR.", "OBSERVED", ("x100", "ethics")),
    ("KAI — registers are instruments; switch under HITL, not for entertainment under crisis.", "OBSERVED", ("x100", "kai")),
    ("KAI — Care register forbids sarcasm; Ops demands go/no-go owners.", "OBSERVED", ("x100", "kai")),
]

for text, kind, tags in _PACK:
    _RAW.append((text, kind, tags))


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus
    c = Corpus()
    n = 0
    for text, kind, tags in _RAW:
        c.add(text, kind=kind, source="seed_knowledge_x100", tags=list(tags))
        n += 1
        if limit and n >= limit:
            break
    return n


def format_index() -> str:
    return f"=== ×100 knowledge pack ===\nunits={len(_RAW)}\nRun: levi brain --seed-x100\n"
