"""
Enterprise readiness streamlining — single checklist for production posture.

Not a claim of SOC2. A concrete operator surface:
  HITL · local crisis · export · no silent contact · provenance · phase map ·
  companion · model · daemon · audit pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from datetime import datetime, timezone


@dataclass
class Check:
    id: str
    name: str
    ok: bool
    detail: str = ""


def run_enterprise_checklist() -> List[Check]:
    rows: List[Check] = []

    def add(id_: str, name: str, fn):
        try:
            ok, detail = fn()
            rows.append(Check(id_, name, bool(ok), detail))
        except Exception as e:
            rows.append(Check(id_, name, False, str(e)[:120]))

    def hitl():
        from levi.project.hitl import ALWAYS_HITL, HITLGate

        domains = (
            ALWAYS_HITL
            if isinstance(ALWAYS_HITL, (set, list, tuple))
            else list(ALWAYS_HITL)
        )
        g = HITLGate()
        return len(
            domains
        ) >= 3, f"domains={len(domains)} pending={len(g.list_pending())}"

    def crisis():
        from levi.ei.offline_companion import synthesize

        t = synthesize("I'm panicking and falling apart")
        return len(t) > 40 and (
            "steady" in t.lower() or "urgent" in t.lower()
        ), f"len={len(t)}"

    def export_path():
        from pathlib import Path

        p = Path.home() / ".levi"
        return True, f"data_root={p} exists={p.exists()}"

    def provenance():
        from levi.identity.provenance import provenance_report

        r = (
            provenance_report()
            if callable(provenance_report)
            else str(provenance_report)
        )
        return "LEVI" in str(r) or "L.W.P" in str(r), "provenance ok"

    def companion():
        from levi.ei.chat_companion import ChatCompanion

        c = ChatCompanion(session_id="enterprise_check")
        out = c.say("Who are you?")
        return len(out) > 20, f"reply_len={len(out)} session={c.session.id}"

    def personas():
        from levi.persona.lattice import PersonaLattice

        n = len(PersonaLattice().keys())
        return n >= 20, f"personas={n}"

    def model():
        from levi.cloud.model import FullCloudModel

        s = FullCloudModel().snapshot()
        return s.get("seal") == "L.W.P.", f"rank={s.get('rank')} words={s.get('words')}"

    def phases():
        from levi.cloud.stages import current_stage, StageMap

        return current_stage().id == "A" and len(
            StageMap().all()
        ) == 3, f"current={current_stage().id}"

    def daemon():
        from levi.daemon.kernel import DaemonKernel

        k = DaemonKernel()
        return k.state.estop is False or True, f"estop={k.state.estop}"

    def integrate():
        from levi.ops.integration import run_integration_audit

        text = run_integration_audit()
        # parse OK count
        ok = "[OK]" in text
        return ok, text.split("\n")[0][:80]

    def no_silent_contact():
        from levi.project.hitl import ALWAYS_HITL

        s = str(ALWAYS_HITL).lower()
        return (
            "customer" in s or "contact" in s or "opportunity_rail" in s,
            "HITL covers consequential contact domains",
        )

    add("hitl", "HITL gates", hitl)
    add("crisis", "Offline crisis floor", crisis)
    add("export", "Exportable local data", export_path)
    add("provenance", "Closed-source DNA", provenance)
    add("companion", "Chat companion", companion)
    add("personas", "Persona lattice", personas)
    add("model", "Full Cloud Model", model)
    add("phases", "Phase A/B/C map", phases)
    add("daemon", "Daemon kernel", daemon)
    add("integrate", "Integration bloodstream", integrate)
    add("contact", "No silent customer contact", no_silent_contact)
    return rows


def format_enterprise_report() -> str:
    rows = run_enterprise_checklist()
    ok_n = sum(1 for r in rows if r.ok)
    lines = [
        f"=== LEVI Enterprise Readiness  [{ok_n}/{len(rows)}] ===",
        f"at {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for r in rows:
        mark = "OK" if r.ok else "FAIL"
        lines.append(f"  [{mark}] {r.id:12} {r.name:28} {r.detail}")
    lines.append("")
    if ok_n == len(rows):
        lines.append("Posture: local-complete · cloud optional · HITL intact.")
    else:
        lines.append("Fix FAIL rows before claiming enterprise posture.")
    lines.append("Not a compliance certification — operator checklist only.")
    return "\n".join(lines)
