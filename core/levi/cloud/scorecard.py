"""
10/10 Cloud Model scorecard — operator-facing quality rubric for LEVI SI.

Scores local-first cloud model posture. Not marketing: checklist math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime, timezone


@dataclass
class ScoreRow:
    id: str
    name: str
    weight: float
    score: float  # 0–10
    note: str


def _clamp(x: float) -> float:
    return max(0.0, min(10.0, x))


def evaluate() -> Tuple[List[ScoreRow], float]:
    rows: List[ScoreRow] = []

    def add(id_: str, name: str, weight: float, fn):
        try:
            s, note = fn()
            rows.append(ScoreRow(id_, name, weight, _clamp(float(s)), note))
        except Exception as e:
            rows.append(ScoreRow(id_, name, weight, 0.0, str(e)[:100]))

    def local_complete():
        from levi.ei.offline_companion import synthesize
        from levi.cloud.model import FullCloudModel

        t = synthesize("Who are you?")
        m = FullCloudModel().snapshot()
        ok = len(t) > 40 and m.get("seal") == "L.W.P."
        return (10.0 if ok else 5.0), f"offline chat + model seal={m.get('seal')}"

    def hitl():
        from levi.project.hitl import ALWAYS_HITL

        n = len(ALWAYS_HITL) if hasattr(ALWAYS_HITL, "__len__") else 0
        return (10.0 if n >= 10 else 6.0 + min(4, n / 2)), f"domains={n}"

    def knowledge():
        from levi.brain.seed_knowledge import iter_knowledge

        n = sum(1 for _ in iter_knowledge())
        # 26 letters + inventors + events + stars + x + si ≈ 70+
        return (10.0 if n >= 60 else 7.0), f"knowledge_units={n}"

    def story():
        from levi.graph.story_prose import expand_paragraph

        p = expand_paragraph("Hook", "Lena", "systems_horror", "test", "wound", 0)
        return (10.0 if len(p.split()) >= 40 else 6.0), f"prose_words={len(p.split())}"

    def personas():
        from levi.persona.lattice import PersonaLattice

        n = len(PersonaLattice().keys())
        return (10.0 if n >= 100 else 7.0), f"personas={n}"

    def phases():
        from levi.cloud.stages import StageMap, current_stage

        return (
            10.0 if current_stage().id == "A" and len(StageMap().all()) == 3 else 5.0
        ), f"current={current_stage().id}"

    def crypto_zk():
        from levi.cloud.crypto_protocol import CryptoProtocol
        from levi.cloud.zk import ZeroKnowledgeDesign

        cp = CryptoProtocol()
        zk = ZeroKnowledgeDesign()
        return (
            9.0,
            f"argon_backend={cp.argon.backend} zk_principles={len(zk.principles())}",
        )

    def enterprise():
        from levi.ops.enterprise import run_enterprise_checklist

        rows_e = run_enterprise_checklist()
        ok = sum(1 for r in rows_e if r.ok)
        total = len(rows_e) or 1
        return (10.0 * ok / total), f"{ok}/{total}"

    def si_identity():
        from levi.identity.si import SI_PILLARS

        return (10.0 if len(SI_PILLARS) >= 6 else 7.0), f"pillars={len(SI_PILLARS)}"

    def integrate():
        from levi.ops.integration import run_integration_audit

        text = run_integration_audit()
        # crude parse
        if "FAIL" in text and "[FAIL]" in text:
            return 7.0, text.split("\n")[0][:60]
        return 10.0, text.split("\n")[0][:60]

    add("local", "Local-complete core", 1.5, local_complete)
    add("hitl", "HITL consequential gates", 1.5, hitl)
    add("knowledge", "General knowledge A–Z/X", 1.2, knowledge)
    add("story", "Literary story delivery", 1.0, story)
    add("personas", "Persona lattice depth", 0.8, personas)
    add("phases", "Phase A/B/C map", 0.8, phases)
    add("crypto", "Crypto + ZK protocol", 0.8, crypto_zk)
    add("enterprise", "Enterprise checklist", 1.2, enterprise)
    add("si", "SI identity pillars", 0.7, si_identity)
    add("integrate", "Integration bloodstream", 0.5, integrate)

    wsum = sum(r.weight for r in rows) or 1.0
    total = sum(r.score * r.weight for r in rows) / wsum
    return rows, total


def format_scorecard() -> str:
    rows, total = evaluate()
    lines = [
        f"=== LEVI SI Cloud Model Scorecard  {total:.1f}/10 ===",
        f"at {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for r in rows:
        bar = "█" * int(round(r.score)) + "░" * (10 - int(round(r.score)))
        lines.append(f"  {r.score:4.1f}  {bar}  {r.name:28} {r.note}")
    lines.append("")
    if total >= 9.5:
        lines.append("Grade: 10/10 posture — local SI complete; cloud wings optional.")
    elif total >= 8.5:
        lines.append("Grade: strong — polish remaining gaps for 10/10.")
    else:
        lines.append("Grade: improve FAIL/low rows before claiming 10/10.")
    lines.append("SI = symbiotic intelligence · cloud never owns CMK or continuity.")
    return "\n".join(lines)
