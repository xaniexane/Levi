"""Cadence engine — rhythm math over an event list.

Inputs
------
``events``: list of ISO-8601 timestamps (any order; duplicates dropped)
``period_hours``: expected cadence in hours (default 24.0)
``now``: optional ISO-8601 reference time (default: actual now — pass
it explicitly for deterministic replays)

Outputs a rhythm read: detected period vs expected period, streak of
on-time events, drift (how far the rhythm has slipped), missed beats,
and the next due time. Built for automation rhythm scheduling —
"has this automation drifted off its beat?" — but pure computation,
so it works on any timestamped series.

Deterministic when ``now`` is supplied.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

TOLERANCE = 0.25  # ±25% of the period still counts as "on time"


def _parse(ts: Any) -> datetime:
    if not isinstance(ts, str):
        raise EngineInputError("cadence: events must be ISO-8601 strings")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        raise EngineInputError(f"cadence: bad timestamp '{ts}'") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cadence(inputs: Dict[str, Any]) -> EngineResult:
    raw = inputs.get("events") or []
    if not isinstance(raw, list):
        raise EngineInputError("cadence: 'events' must be a list")
    period_h = float(inputs.get("period_hours", 24.0))
    if period_h <= 0:
        raise EngineInputError("cadence: 'period_hours' must be positive")
    now_raw = inputs.get("now")
    now = _parse(now_raw) if now_raw else datetime.now(timezone.utc)

    events = sorted({_parse(e).timestamp() for e in raw})
    trace: List[str] = [f"{len(events)} unique events; expected period {period_h}h"]

    verdict: Dict[str, Any] = {"event_count": len(events)}
    if len(events) < 2:
        verdict.update(
            {
                "detected_period_hours": None,
                "on_time_streak": 0,
                "missed_beats": 0,
                "drift_hours": 0.0,
                "next_due": None,
            }
        )
        trace.append("fewer than 2 events — no rhythm to read")
        return EngineResult(
            engine_id="cadence", verdict=verdict, confidence=0.0, trace=trace
        )

    # Detected period: median gap between consecutive events.
    gaps = [b - a for a, b in zip(events, events[1:])]
    gaps_sorted = sorted(gaps)
    mid = len(gaps_sorted) // 2
    if len(gaps_sorted) % 2:
        median_gap = gaps_sorted[mid]
    else:
        median_gap = (gaps_sorted[mid - 1] + gaps_sorted[mid]) / 2
    detected_h = median_gap / 3600.0
    trace.append(f"detected period {detected_h:.1f}h vs expected {period_h}h")

    # On-time streak: walk back from the latest event; a gap within
    # ±TOLERANCE of the expected period keeps the streak alive.
    streak = 1
    for a, b in zip(reversed(events[:-1]), reversed(events[1:])):
        gap_h = (b - a) / 3600.0
        if abs(gap_h - period_h) <= period_h * TOLERANCE:
            streak += 1
        else:
            break
    # Missed beats: gaps wide enough to swallow whole periods.
    missed = sum(int(gap // 3600 // period_h) - 1 for gap in gaps)
    missed = max(missed, 0)

    last = events[-1]
    next_due_ts = last + period_h * 3600.0
    overdue_h = max((now.timestamp() - next_due_ts) / 3600.0, 0.0)
    next_due = datetime.fromtimestamp(next_due_ts, tz=timezone.utc).isoformat()

    # Confidence: how close detected period is to expected (capped).
    ratio = detected_h / period_h if period_h else 1.0
    closeness = 1.0 - min(abs(ratio - 1.0), 1.0)
    confidence = round(0.3 + 0.7 * closeness, 3)

    verdict.update(
        {
            "detected_period_hours": round(detected_h, 2),
            "period_match": round(ratio, 3),
            "on_time_streak": streak,
            "missed_beats": missed,
            "drift_hours": round(overdue_h, 2),
            "next_due": next_due,
            "overdue": overdue_h > 0,
        }
    )
    trace.append(f"on-time streak {streak}; missed beats {missed}")
    trace.append(
        f"next due {next_due}" + (f" — OVERDUE by {overdue_h:.1f}h" if overdue_h else " — on beat")
    )
    return EngineResult(
        engine_id="cadence", verdict=verdict, confidence=confidence, trace=trace
    )


CADENCE_ENGINE = Engine(
    id="cadence",
    name="Cadence",
    description=(
        "Rhythm math over timestamped events: detected vs expected "
        "period, on-time streak, drift, missed beats, and next-due."
    ),
    required=("events",),
    schema={
        "events": "list of ISO-8601 timestamps",
        "period_hours": "expected cadence in hours (default 24.0)",
        "now": "ISO-8601 reference time (optional; pass for determinism)",
    },
    risk="info",
    handler=_cadence,
)

registry.register(CADENCE_ENGINE)
