"""
Operational layer — complete local ops surface for LEVI × L.W.P.

Not a chatbot. Coordinates:
  brainstem (kernel) · unified cycle · pulse · opportunity rail · HITL · estop

All consequential paths remain HITL-gated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from datetime import datetime, timezone


@dataclass
class OpsSnapshot:
    estop: bool = False
    safety: str = "normal"
    cycle: int = 0
    hitl_pending: int = 0
    rail_active: int = 0
    rail_done: int = 0
    demand_signals: int = 0
    income_plans: int = 0
    corpus_units: int = 0
    relay_offline_ok: bool = False
    ollama_up: bool = False
    cost_session: float = 0.0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estop": self.estop,
            "safety": self.safety,
            "cycle": self.cycle,
            "hitl_pending": self.hitl_pending,
            "rail_active": self.rail_active,
            "rail_done": self.rail_done,
            "demand_signals": self.demand_signals,
            "income_plans": self.income_plans,
            "corpus_units": self.corpus_units,
            "relay_offline_ok": self.relay_offline_ok,
            "ollama_up": self.ollama_up,
            "cost_session": self.cost_session,
            "notes": self.notes,
            "at": datetime.now(timezone.utc).isoformat(),
        }


class OperationalLayer:
    """Single entry for operator / LEVI-voice / Cursor drivers."""

    def snapshot(self) -> OpsSnapshot:
        snap = OpsSnapshot()
        try:
            from levi.daemon.kernel import DaemonKernel

            k = DaemonKernel()
            snap.estop = bool(k.state.estop)
            snap.safety = getattr(k.state, "safety", "normal") or "normal"
            if hasattr(snap.safety, "value"):
                snap.safety = snap.safety.value
            snap.cycle = int(getattr(k.state, "cycle", 0) or 0)
            snap.cost_session = float(getattr(k.state, "cost_session", 0) or 0)
        except Exception as e:
            snap.notes.append(f"kernel: {e}")
        try:
            from levi.project.hitl import HITLGate

            snap.hitl_pending = len(HITLGate().list_pending())
        except Exception as e:
            snap.notes.append(f"hitl: {e}")
        try:
            from levi.lwp.opportunity_rail import OpportunityRail

            cars = list(OpportunityRail().cars.values())
            snap.rail_active = sum(
                1 for c in cars if c.status == "active" and c.gate != "done"
            )
            snap.rail_done = sum(
                1 for c in cars if c.gate == "done" or c.status == "done"
            )
        except Exception as e:
            snap.notes.append(f"rail: {e}")
        try:
            from levi.demand.pulse import DemandPulse

            dp = DemandPulse()
            snap.demand_signals = len(getattr(dp, "signals", []) or [])
        except Exception as e:
            snap.notes.append(f"demand: {e}")
        try:
            from levi.income.factory import IncomeFactory

            snap.income_plans = len(IncomeFactory().plans)
        except Exception as e:
            snap.notes.append(f"income: {e}")
        try:
            from levi.brain.corpus import Corpus

            snap.corpus_units = len(Corpus().list(limit=5000))
        except Exception as e:
            snap.notes.append(f"corpus: {e}")
        try:
            from levi.model.relay import ModelRelay

            r = ModelRelay()
            ol = r.probe_ollama()
            snap.ollama_up = bool(ol.get("up"))
            res = r.generate("ops ping")
            snap.relay_offline_ok = bool(res.text)
        except Exception as e:
            snap.notes.append(f"relay: {e}")

        try:
            from levi.cloud.stages import current_stage

            snap.notes.append(
                "phase=%s/%s" % (current_stage().id, current_stage().status)
            )
        except Exception as e:
            snap.notes.append(f"phase: {e}")

        return snap

    def format_status(self) -> str:
        s = self.snapshot()
        lines = [
            "=== LEVI Operational Layer ===",
            f"estop={s.estop}  safety={s.safety}  cycle={s.cycle}  cost_session={s.cost_session}",
            f"HITL pending={s.hitl_pending}  rail active={s.rail_active} done={s.rail_done}",
            f"demand signals={s.demand_signals}  income drafts={s.income_plans}  corpus={s.corpus_units}",
            f"relay_offline_ok={s.relay_offline_ok}  ollama_up={s.ollama_up}",
            "",
        ]
        if s.estop:
            lines.append(
                "⚠ EMERGENCY STOP — clear only after human review: levi ops --clear-estop"
            )
        if s.hitl_pending:
            lines.append(f"→ Review HITL: levi project hitl (pending={s.hitl_pending})")
        if s.rail_active:
            lines.append(f"→ Advance rails: levi rail (active={s.rail_active})")
        lines.append("")
        lines.append("--- Pulse ---")
        try:
            from levi.pulse.check import run_pulse

            lines.append(run_pulse())
        except Exception as e:
            lines.append(f"pulse error: {e}")
        lines.append("")
        lines.append("--- Kernel ---")
        try:
            from levi.daemon.kernel import DaemonKernel

            lines.append(DaemonKernel().status())
        except Exception as e:
            lines.append(str(e))
        if s.notes:
            lines.append("")
            lines.append("notes: " + "; ".join(s.notes))
        lines.append("")
        lines.append(
            "Ops is local coordination only — no external side effects without HITL."
        )
        return "\n".join(lines)

    def run_cycle(self, task: str, execute: bool = False) -> str:
        from levi.daemon.unified import UnifiedDaemon

        return UnifiedDaemon().run_cycle(task, execute=execute)

    def rail_dry_run(self, signal: str) -> str:
        """Start rail + advance through MIRROR and DRAFT until HITL_OFFER — no approve."""
        from levi.lwp.opportunity_rail import OpportunityRail

        rail = OpportunityRail()
        car = rail.start(signal)
        lines = [f"Started car {car.id} gate={car.gate}", ""]
        # advance mirror → draft → hits HITL
        for _ in range(3):
            out = rail.advance(car.id, hitl_approved=False)
            car = rail.cars[car.id]
            lines.append(f"gate={car.gate}")
            lines.append(out[:500])
            lines.append("")
            if car.gate in ("hitl_offer", "blocked", "done"):
                break
        lines.append(
            "Stopped at HITL (or block). Approve then: levi rail --advance <id> --approved"
        )
        return "\n".join(lines)

    def clear_estop(self) -> str:
        from levi.daemon.kernel import DaemonKernel

        k = DaemonKernel()
        k.clear_estop()
        return "E-stop cleared.\n" + k.status()

    def estop(self, reason: str = "operator") -> str:
        from levi.daemon.kernel import DaemonKernel

        k = DaemonKernel()
        k.emergency_stop(reason)
        return k.status()


def run_ops() -> str:
    return OperationalLayer().format_status()
