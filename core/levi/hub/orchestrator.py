"""hub.orchestrator: Discover → Evaluate → Execute → Track → Optimize → Repeat.

This is the original's unfinished business: ``omega_agent.py`` had a
SyntaxError at line 103 and never imported, let alone ran. The hub's
orchestrator follows the proven shape from the Master Blueprint —
Overseer (Chauncey) / Execution Engine (the hub) split, HITL gates —
but it ACTUALLY RUNS.

One cycle:
  discover  — gather inputs (last DemandPulse scan, competition changes,
              job buffer counts). OBSERVED.
  evaluate  — rank what matters. INFERENCE.
  execute   — advisory acts run; consequential acts become HITL requests
              (never self-applied).
  track     — receipt written to the hub db.
  optimize  — HYPOTHESIS recommendations for the next cycle.
  repeat    — the caller decides cadence (CLI/cron); the loop body is pure.

Advisory-only. No money, no applications sent, no external writes beyond
polite keyless reads.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import agent as scout
from . import hitl, store
from levi.demand import processing as dp_processing


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def discover(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """Gather cycle inputs. Everything here is OBSERVED (or honestly empty)."""
    inputs: Dict[str, Any] = {"label": "OBSERVED", "at": _now()}
    # DemandPulse: last persisted scan, if any
    try:
        scan = dp_processing.load_last_scan()
        if scan:
            inputs["demand"] = {
                "scanned_at": scan.get("scanned_at"),
                "signals": len(scan.get("signals", [])),
                "opportunities": len(scan.get("opportunities", [])),
                "high_priority": scan.get("pipeline_counts", {}).get("high", 0),
                "heatmap_green": [
                    k
                    for k, v in (scan.get("heatmap") or {}).items()
                    if isinstance(v, dict) and v.get("band") == "green"
                ],
            }
        else:
            inputs["demand"] = {"note": "no scan yet — run pulse scan first"}
    except Exception as exc:
        inputs["demand"] = {"error": f"{type(exc).__name__}: {exc}"}
    # competition changes
    try:
        from levi.demand import competition as comp

        changes = comp.check_changes()
        inputs["competition_changes"] = [
            {
                "competitor": c.get("competitor"),
                "url": c.get("url"),
                "changed": c.get("changed"),
            }
            for c in changes
        ]
    except Exception as exc:
        inputs["competition_changes"] = {"error": f"{type(exc).__name__}: {exc}"}
    # job buffer depth
    try:
        from levi.jobs import store as job_store

        wh = job_store.Warehouse()
        inputs["job_buffer"] = len(wh.list_rows("review_buffer"))
    except Exception as exc:
        inputs["job_buffer"] = {"error": f"{type(exc).__name__}: {exc}"}
    # pending approvals the Overseer still owes the engine
    inputs["hitl_pending"] = len(hitl.pending(path=path))
    return inputs


def evaluate(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Rank what matters this cycle. INFERENCE — judgment, not measurement."""
    ranked: List[Dict[str, Any]] = []
    demand = inputs.get("demand") or {}
    if isinstance(demand, dict) and demand.get("high_priority"):
        ranked.append(
            {
                "item": f"{demand['high_priority']} high-priority demand opportunities",
                "why": "DemandPulse scored them above the high bar",
                "weight": 3,
            }
        )
    changes = inputs.get("competition_changes")
    if isinstance(changes, list) and any(c.get("changed") for c in changes):
        n = sum(1 for c in changes if c.get("changed"))
        ranked.append(
            {
                "item": f"{n} competitor page(s) changed",
                "why": "rival movement may obsolete our edge",
                "weight": 2,
            }
        )
    if inputs.get("hitl_pending"):
        ranked.append(
            {
                "item": f"{inputs['hitl_pending']} pending approval(s)",
                "why": "the engine is blocked on the Overseer's word",
                "weight": 3,
            }
        )
    if isinstance(inputs.get("job_buffer"), int) and inputs["job_buffer"] == 0:
        ranked.append(
            {
                "item": "job review buffer is empty",
                "why": "no pipeline without intake",
                "weight": 1,
            }
        )
    ranked.sort(key=lambda r: r["weight"], reverse=True)
    return {"label": "INFERENCE", "ranked": ranked, "at": _now()}


def execute(
    evaluation: Dict[str, Any], *, path: Optional[Path] = None
) -> Dict[str, Any]:
    """Run advisory acts; queue consequential ones as HITL. Never self-applies."""
    acted: List[Dict[str, Any]] = []
    queued: List[Dict[str, Any]] = []
    for item in evaluation.get("ranked", []):
        text = item["item"]
        if "competitor" in text:
            # advisory: refresh the gap proposals so the founder sees them
            try:
                from levi.demand import competition as comp

                pkg = comp.propose_upgrades()
                acted.append(
                    {
                        "act": "refreshed upgrade proposals",
                        "proposals": len(pkg.get("proposals", [])),
                        "label": "OBSERVED",
                    }
                )
            except Exception as exc:
                acted.append({"act": "refresh proposals", "error": str(exc)})
        elif "approval" in text:
            acted.append(
                {
                    "act": "surfaced pending approvals",
                    "note": "overseer decision required — engine does not chase",
                    "label": "OBSERVED",
                }
            )
        elif "job review buffer is empty" in text:
            # consequential-ish: fetching is fine (polite reads), but staging
            # writes to the buffer — dry-run only unless approved
            req = hitl.request_approval(
                "jobs.refresh",
                {"act": "keyless job sweep + stage to review buffer", "dry_run": False},
                path=path,
            )
            queued.append({"hitl_id": req["id"], "for": text})
        else:
            acted.append({"act": "noted", "item": text, "label": "OBSERVED"})
    return {"acted": acted, "queued": queued, "label": "OBSERVED", "at": _now()}


def optimize(
    inputs: Dict[str, Any], evaluation: Dict[str, Any], execution: Dict[str, Any]
) -> Dict[str, Any]:
    """Recommendations for the next cycle. HYPOTHESIS, always."""
    recs: List[Dict[str, Any]] = []
    if not (inputs.get("demand") or {}).get("scanned_at"):
        recs.append("run a DemandPulse scan — the engine is flying blind on demand")
    if (inputs.get("hitl_pending") or 0) > 3:
        recs.append("clear the approval backlog — the engine stalls behind it")
    if execution.get("queued"):
        recs.append("decide the queued HITL requests before the next cycle")
    return {
        "label": "HYPOTHESIS",
        "recommendations": recs,
        "advisory_only": True,
        "at": _now(),
    }


def run_cycle(goal: str = "", *, path: Optional[Path] = None) -> Dict[str, Any]:
    """Run one full Discover → … → Repeat cycle. Returns the receipt."""
    stages: Dict[str, Any] = {"goal": goal or "keep the hub turning", "at": _now()}
    stages["discover"] = discover(path=path)
    stages["evaluate"] = evaluate(stages["discover"])
    stages["execute"] = execute(stages["evaluate"], path=path)
    stages["optimize"] = optimize(
        stages["discover"], stages["evaluate"], stages["execute"]
    )
    receipt = {
        "ok": True,
        "cycle": stages,
        "overseer": "Chauncey (decides)",
        "execution_engine": "hub (advises, never self-applies)",
        "label": "INFERENCE",
    }
    conn = store.connect(path)
    try:
        conn.execute(
            "INSERT INTO runs (kind, receipt, created) VALUES ('cycle', ?, ?)",
            (json.dumps(receipt), _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return receipt


def status(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """One-line health for the CLI dashboard."""
    hb = scout.heartbeat(path=path)
    return {
        "ok": True,
        "hub": "levi.hub 0.1.0",
        "heartbeat": hb,
        "label": "OBSERVED",
    }
