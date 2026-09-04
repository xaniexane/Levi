"""
Standing Watch — LEVI-original light sentinel (pulse evolved).

Aggregates estop, HITL queue, rail pressure, continuity, relay offline health.
Designed for cron: `levi watch` — not a cloud monitoring SaaS.
"""
from __future__ import annotations

from typing import List, Tuple


def run_watch() -> str:
    rows: List[Tuple[str, str]] = []
    alerts: List[str] = []

    try:
        from levi.daemon.kernel import DaemonKernel
        k = DaemonKernel()
        rows.append(("estop", "ON" if k.state.estop else "off"))
        if k.state.estop:
            alerts.append("Emergency stop is engaged")
    except Exception as e:
        rows.append(("kernel", str(e)[:40]))

    try:
        from levi.project.hitl import HITLGate
        n = sum(1 for r in HITLGate().list_pending() if getattr(r, "status", "") == "pending")
        rows.append(("hitl_pending", str(n)))
        if n:
            alerts.append(f"{n} HITL card(s) waiting — silence is not approval")
    except Exception as e:
        rows.append(("hitl", str(e)[:40]))

    try:
        from levi.lwp.opportunity_rail import OpportunityRail
        active = sum(1 for c in OpportunityRail().cars.values() if getattr(c, "status", "") == "active")
        rows.append(("rails_active", str(active)))
    except Exception as e:
        rows.append(("rail", str(e)[:40]))

    try:
        from levi.model.relay import ModelRelay
        res = ModelRelay().generate("watch ping")
        rows.append(("relay_offline", "ok" if res.text else "empty"))
    except Exception as e:
        rows.append(("relay", str(e)[:40]))

    try:
        from levi.runtime.continuity import ContinuityShelf
        ContinuityShelf().snapshot()
        rows.append(("continuity", "snapshotted"))
    except Exception as e:
        rows.append(("continuity", str(e)[:40]))

    lines = ["=== Standing Watch (LEVI) ===", ""]
    for k, v in rows:
        lines.append(f"  {k:16} {v}")
    lines.append("")
    if alerts:
        lines.append("Alerts:")
        for a in alerts:
            lines.append(f"  ! {a}")
    else:
        lines.append("No urgent alerts.")
    lines.append("")
    lines.append("Cron example: */30 * * * * cd … && PYTHONPATH=. python -m levi.cli.main watch")
    return "\n".join(lines)


class StandingWatch:
    def run(self) -> str:
        return run_watch()
