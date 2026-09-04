"""Pulse check — surface pending HITL, project phase, shelf, mono (local only)."""
from __future__ import annotations

from typing import List


def run_pulse() -> str:
    lines: List[str] = ["=== LEVI Pulse ===", ""]
    try:
        from levi.project.hitl import HITLGate
        pending = HITLGate().list_pending()
        lines.append(f"HITL pending: {len(pending)}")
        for r in pending[:5]:
            lines.append(f"  · {r.id} {r.domain} {r.what[:50]}")
    except Exception as e:
        lines.append(f"HITL: ({e})")
    try:
        from levi.project.phases import PhaseRunner
        st = PhaseRunner().state
        lines.append(f"Project phase: {st.current_phase}  done={st.completed}")
    except Exception:
        lines.append("Project: —")
    try:
        from levi.persona.monotropism import MonotropismTracker
        m = MonotropismTracker()
        a = m.state.active
        if a:
            lines.append(f"Mono tunnel: {a.label or a.signature[:40]} depth={a.depth:.2f}")
        else:
            lines.append("Mono tunnel: —")
    except Exception:
        pass
    try:
        from levi.project.capability_log import CapabilityLog
        n = len(CapabilityLog().entries)
        lines.append(f"Capability log entries: {n}")
    except Exception:
        pass
    try:
        from levi.lwp.opportunity_rail import OpportunityRail
        cars = list(OpportunityRail().cars.values())
        active = sum(1 for c in cars if getattr(c, "status", "") == "active" and c.gate != "done")
        lines.append(f"Opportunity rail: active={active} total={len(cars)}")
    except Exception:
        pass
    try:
        from levi.daemon.kernel import DaemonKernel
        k = DaemonKernel()
        lines.append(f"Kernel: estop={k.state.estop} cycle={k.state.cycle}")
    except Exception:
        pass
    lines.append("")
    lines.append("Pulse is local self-check only — no external action without HITL.")
    return "\n".join(lines)
