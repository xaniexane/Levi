"""The 10 original DemandPulse workflows, wired into the LEVI alert engine.

Original workflow table (from omega_demandpulse.py, schedules kept verbatim):

  1. Daily Trend Scanner            — 7:00 AM CDT daily
  2. Community Pain Point Miner     — Every 6 hours
  3. Weekly Opportunity Digest      — Monday 8:00 AM CDT
  4. High-Score Alert               — Event-driven (score >= threshold)
  5. Competition Monitor            — Daily 10:00 AM CDT
  6. Economic Indicator Watcher     — Sunday 9:00 PM CDT
  7. Monthly Industry Landscape Report — 1st of month 8:00 AM
  8. Signal Correlation Engine      — After each ingestion
  9. Breakout Detector              — Hourly
  10. Portfolio Performance Tracker — Friday 6:00 PM CDT

Alert-engine mapping (honest about what the engine can express):
  - Workflows 1, 3, 5, 6, 7, 10 become briefing alerts. Weekly briefings
    pin a day-of-week (workflow 3 -> Monday, 6 -> Sunday, 10 -> Friday);
    workflow 7 uses the monthly recurrence (fires on the 1st).
  - Workflow 4 becomes a threshold alert (composite >= 75, event-driven).
  - Workflows 2 and 9 become watch alerts on the "pain_point" and
    "breakout" segments. The original "every 6 hours" / "hourly" figures
    are the *scan* cadence, not the alert: the sweep evaluates watches on
    every tick, and they fire when new signals land in the segment.
  - Workflow 8 is not an alert — it is the correlation step that already
    runs inside every ``run_scan`` (process_signals after ingestion). It
    can also be re-run over the last stored scan via ``run_workflow(8)``.

``install_workflows`` creates the nine alert-backed workflows idempotently
(same name+type never installs twice). ``feed_scan_into_demandpulse``
bridges a scan into DemandPulse signals so watch alerts actually fire:
one OBSERVED signal per cluster in its signal-type segment, plus a
"breakout" signal for multi-source clusters with 4+ signals.

Labels stay visible everywhere: ingested text is OBSERVED, clusters are
INFERENCE, scored opportunities are HYPOTHESIS. Advisory only — running
a workflow fetches public feeds and evaluates alerts; it executes no
purchases and takes no external actions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.demand.alerts import Alert, AlertEngine
from levi.demand.processing import (
    load_last_scan,
    process_signals,
    run_scan,
)
from levi.demand.pulse import DemandPulse, DemandSignal

# The original workflow table — names and schedules kept verbatim.
WORKFLOWS: Dict[int, Dict[str, str]] = {
    1: {"name": "Daily Trend Scanner", "schedule": "7:00 AM CDT daily"},
    2: {"name": "Community Pain Point Miner", "schedule": "Every 6 hours"},
    3: {"name": "Weekly Opportunity Digest", "schedule": "Monday 8:00 AM CDT"},
    4: {"name": "High-Score Alert", "schedule": "Event-driven (score ≥ threshold)"},
    5: {"name": "Competition Monitor", "schedule": "Daily 10:00 AM CDT"},
    6: {"name": "Economic Indicator Watcher", "schedule": "Sunday 9:00 PM CDT"},
    7: {
        "name": "Monthly Industry Landscape Report",
        "schedule": "1st of month 8:00 AM",
    },
    8: {"name": "Signal Correlation Engine", "schedule": "After each ingestion"},
    9: {"name": "Breakout Detector", "schedule": "Hourly"},
    10: {"name": "Portfolio Performance Tracker", "schedule": "Friday 6:00 PM CDT"},
}

# Alert specs for the nine alert-backed workflows (8 is a pipeline step).
# "dow": 0=Monday..6=Sunday for weekly briefings.
WORKFLOW_ALERTS: Dict[int, Dict[str, Any]] = {
    1: {
        "kind": "briefing",
        "time": "07:00",
        "recurrence": "daily",
        "channels": ("console", "file"),
    },
    2: {
        "kind": "watch",
        "segment": "pain_point",
        "channels": ("console", "file"),
    },
    3: {
        "kind": "briefing",
        "time": "08:00",
        "recurrence": "weekly",
        "dow": 0,
        "channels": ("console", "file"),
    },
    4: {
        "kind": "threshold",
        "threshold": 75.0,
        "channels": ("console", "file"),
    },
    5: {
        "kind": "briefing",
        "time": "10:00",
        "recurrence": "daily",
        "channels": ("console", "file"),
    },
    6: {
        "kind": "briefing",
        "time": "21:00",
        "recurrence": "weekly",
        "dow": 6,
        "channels": ("console", "file"),
    },
    7: {
        "kind": "briefing",
        "time": "08:00",
        "recurrence": "monthly",
        "channels": ("console", "file"),
    },
    9: {
        "kind": "watch",
        "segment": "breakout",
        "channels": ("console", "file"),
    },
    10: {
        "kind": "briefing",
        "time": "18:00",
        "recurrence": "weekly",
        "dow": 4,
        "channels": ("console", "file"),
    },
}

_BREAKOUT_MIN_SIGNALS = 4  # multi-source cluster of 4+ signals = breakout


def _workflow_alert_name(number: int) -> str:
    return f"DP Workflow {number}: {WORKFLOWS[number]['name']}"


def list_workflows() -> List[Dict[str, Any]]:
    """The original 10 workflows with their schedules and alert mapping."""
    rows = []
    for number in sorted(WORKFLOWS):
        spec = WORKFLOW_ALERTS.get(number)
        rows.append(
            {
                "id": number,
                "name": WORKFLOWS[number]["name"],
                "schedule": WORKFLOWS[number]["schedule"],
                "alert_kind": spec["kind"] if spec else "pipeline",
            }
        )
    return rows


def install_workflows(
    engine: Optional[AlertEngine] = None,
    skip_existing: bool = True,
) -> List[Alert]:
    """Create the nine alert-backed workflow alerts. Idempotent.

    When ``skip_existing`` is true (default), an alert whose name+type
    already exists is left alone — installing twice never duplicates.
    Returns the alerts that were created (empty on a no-op reinstall).
    """
    engine = engine or AlertEngine()
    created: List[Alert] = []
    for number in sorted(WORKFLOW_ALERTS):
        spec = WORKFLOW_ALERTS[number]
        name = _workflow_alert_name(number)
        if skip_existing and any(
            a.name == name and a.type == spec["kind"] for a in engine.alerts
        ):
            continue
        kwargs: Dict[str, Any] = {
            "time": spec.get("time", "07:00"),
            "recurrence": spec.get("recurrence", "daily"),
            "threshold": spec.get("threshold", 75.0),
            "segment": spec.get("segment", ""),
            "channels": spec.get("channels", ("console", "file")),
            "message": spec.get("message", ""),
        }
        if "dow" in spec:
            kwargs["dow"] = spec["dow"]
        created.append(engine.create(spec["kind"], name, **kwargs))
    return created


def feed_scan_into_demandpulse(
    dp: DemandPulse,
    scan: Dict[str, Any],
) -> List[DemandSignal]:
    """Bridge a scan's clusters into DemandPulse signals (OBSERVED).

    One signal per cluster in its signal-type segment (so workflow 2's
    pain_point watch fires), plus a "breakout" signal for multi-source
    clusters with 4+ signals (so workflow 9 fires). Signals are real
    fetched text — kind OBSERVED — never invented.
    """
    produced: List[DemandSignal] = []
    clusters = scan.get("clusters", []) or []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        theme = (cluster.get("theme", "") or "").strip()[:300]
        if not theme:
            continue
        segment = cluster.get("signal_type", "") or "trend"
        confidence = 0.9 if cluster.get("multi_source_validated") else 0.6
        sources = sorted({s.get("source", "?") for s in cluster.get("signals", [])})
        evidence = (
            f"workflow scan {scan.get('scanned_at', '')}: "
            f"{cluster.get('signal_count', 0)} OBSERVED signals from "
            f"{', '.join(sources) or 'unknown sources'} "
            f"(cluster {cluster.get('cluster_id', '?')}, INFERENCE grouping)"
        )
        sig = DemandSignal(
            id=f"dp-{cluster.get('cluster_id', 'unknown')}",
            need=theme,
            segment=segment,
            evidence=evidence,
            confidence=confidence,
            kind="OBSERVED",
        )
        dp._register_signal(sig)
        produced.append(sig)
        if (
            cluster.get("multi_source_validated")
            and int(cluster.get("signal_count", 0) or 0) >= _BREAKOUT_MIN_SIGNALS
        ):
            breakout = DemandSignal(
                id=f"dp-breakout-{cluster.get('cluster_id', 'unknown')}",
                need=f"BREAKOUT: {theme}",
                segment="breakout",
                evidence=evidence,
                confidence=0.9,
                kind="OBSERVED",
            )
            dp._register_signal(breakout)
            produced.append(breakout)
    dp._persist()
    return produced


def run_workflow(
    number: int,
    query: str = "ai tools",
    dp: Optional[DemandPulse] = None,
    engine: Optional[AlertEngine] = None,
) -> Dict[str, Any]:
    """Run one workflow by its original number. Advisory only.

    Workflows 1-7, 9-10 run a live scan and feed the results into
    DemandPulse so their watch/threshold alerts can fire on the next
    sweep. Workflow 8 re-correlates the last stored scan (the same
    process_signals step every run_scan already performs).
    """
    if number not in WORKFLOWS:
        raise ValueError(f"unknown workflow {number}; expected 1..10")
    if number == 8:
        last = load_last_scan()
        if not last:
            return {"workflow": 8, "correlated": 0, "note": "no stored scan yet"}
        clusters = process_signals(last.get("signals", []) or [])
        return {
            "workflow": 8,
            "correlated": len(clusters),
            "scanned_at": last.get("scanned_at"),
            "note": "re-correlated stored signals (INFERENCE)",
        }
    dp = dp or DemandPulse()
    scan = run_scan(query)
    fed = feed_scan_into_demandpulse(dp, scan)
    engine = engine or AlertEngine()
    receipt = engine.run(dp)
    return {
        "workflow": number,
        "name": WORKFLOWS[number]["name"],
        "signals": len(scan.get("signals", [])),
        "clusters": len(scan.get("clusters", [])),
        "opportunities": len(scan.get("opportunities", [])),
        "fed_into_demandpulse": len(fed),
        "alert_receipt": {
            "fired": receipt["fired"],
            "delivered": receipt["delivered"],
            "held": receipt["held"],
            "flushed": receipt["flushed"],
        },
        "scanned_at": scan.get("scanned_at"),
    }


def workflow_status(engine: Optional[AlertEngine] = None) -> List[Dict[str, Any]]:
    """Each workflow plus whether its alert is installed and enabled."""
    engine = engine or AlertEngine()
    rows = []
    for row in list_workflows():
        spec = WORKFLOW_ALERTS.get(row["id"])
        if spec is None:
            rows.append({**row, "installed": None, "enabled": None})
            continue
        name = _workflow_alert_name(row["id"])
        match = next(
            (a for a in engine.alerts if a.name == name and a.type == spec["kind"]),
            None,
        )
        rows.append(
            {
                **row,
                "installed": match is not None,
                "enabled": bool(match.enabled) if match else False,
            }
        )
    return rows
