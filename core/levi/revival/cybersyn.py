"""Cybersyn opsroom method: run a decision room that fits in a human head.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #24)

Three load-bearing mechanisms, from the historical opsroom idea:

1. **Variety attenuation.** A metric stream carries more variety than a
   human can hold, so the room attenuates it: from the full stream, keep
   only what fits the 7-item grasp limit — the N most deviant metrics
   (furthest from their expected band). Everything else is recorded but
   not displayed. The operator sees seven dials, not seven hundred.
2. **Algedonic signals.** Pain/pleasure channels: when a metric breaches
   a threshold, the room raises a raw alert signal — PAIN (breach is bad)
   or PLEASURE (breach is good, e.g. output above target). No nuance at
   the signal layer; nuance belongs to the decision.
3. **Forced decision log.** Every alert *demands* a logged decision.
   An alert is not resolved by being acknowledged — it is resolved only
   when a decision is recorded against it (act / monitor / dismiss with
   reason). Undecided alerts are open; the room refuses to close them
   silently.

Metrics are dicts with ``name``, ``value``, and optional ``target``
(expected value) and ``tolerance`` (acceptable deviation). stdlib-only.
No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


ORIGIN = "levi-revival/cybersyn"

GRASP_LIMIT = 7


@dataclass
class AttenuatedView:
    """What fits in the operator's head right now."""

    displayed: List[Dict[str, object]]
    hidden_count: int
    hidden_names: List[str]


def attenuate(
    metrics: List[Dict[str, object]], grasp_limit: int = GRASP_LIMIT
) -> AttenuatedView:
    """Filter a metric stream to what fits the grasp limit.

    Metrics are ranked by *deviation from their expected band*: how far
    the value is from target, relative to tolerance. The most deviant
    ``grasp_limit`` metrics are displayed (deviants first); the rest are
    hidden but named, so nothing is silently dropped.
    """
    if grasp_limit < 1:
        raise ValueError("grasp_limit must be at least 1")
    scored = []
    for m in metrics:
        name = m.get("name")
        if not name:
            raise ValueError("every metric needs a name")
        value = _number(m.get("value"), f"metric {name!r} value")
        target = _number(m.get("target", 0.0), f"metric {name!r} target")
        tolerance = _number(m.get("tolerance", 1.0), f"metric {name!r} tolerance")
        if tolerance <= 0:
            raise ValueError(f"metric {name!r} tolerance must be positive")
        deviation = abs(value - target) / tolerance
        scored.append(
            (
                deviation,
                {
                    "name": name,
                    "value": value,
                    "target": target,
                    "tolerance": tolerance,
                    "deviation": round(deviation, 4),
                    "in_band": deviation <= 1.0,
                },
            )
        )
    scored.sort(key=lambda s: -s[0])
    displayed = [entry for _, entry in scored[:grasp_limit]]
    hidden = scored[grasp_limit:]
    return AttenuatedView(
        displayed=displayed,
        hidden_count=len(hidden),
        hidden_names=[entry["name"] for _, entry in hidden],
    )


def _number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number, got {value!r}")
    return float(value)


# --------------------------------------------------------------------------
# Algedonic signals
# --------------------------------------------------------------------------
@dataclass
class Alert:
    name: str
    signal: str  # "PAIN" or "PLEASURE"
    value: float
    threshold: float
    raised_at: str
    decision: Optional[Dict[str, str]] = None

    @property
    def open(self) -> bool:
        return self.decision is None


class OpsRoom:
    """The room: thresholds in, signals out, decisions demanded."""

    def __init__(self) -> None:
        self.thresholds: Dict[str, Dict[str, float]] = {}
        self.alerts: List[Alert] = []
        self.decision_log: List[Dict[str, str]] = []

    def set_threshold(
        self,
        metric: str,
        pain_below: Optional[float] = None,
        pain_above: Optional[float] = None,
        pleasure_above: Optional[float] = None,
        pleasure_below: Optional[float] = None,
    ) -> None:
        """Define what counts as a pain or pleasure breach for a metric.

        ``pain_below``/``pain_above``: value crossing these is PAIN.
        ``pleasure_above``/``pleasure_below``: value crossing these is
        PLEASURE (a good breach, e.g. throughput over target). At least
        one threshold is required.
        """
        cfg = {
            "pain_below": pain_below,
            "pain_above": pain_above,
            "pleasure_above": pleasure_above,
            "pleasure_below": pleasure_below,
        }
        if all(v is None for v in cfg.values()):
            raise ValueError("at least one threshold is required")
        self.thresholds[metric] = cfg

    def ingest(self, metrics: List[Dict[str, object]]) -> List[Alert]:
        """Run one metric tick through the thresholds.

        Returns the alerts raised *this tick*. Metrics with no
        configured thresholds are attenuated silently (tracked, never
        signaled).
        """
        raised = []
        for m in metrics:
            name = m.get("name")
            if name not in self.thresholds:
                continue
            value = _number(m.get("value"), f"metric {name!r} value")
            cfg = self.thresholds[name]
            signal: Optional[str] = None
            threshold: Optional[float] = None
            if cfg["pain_below"] is not None and value < cfg["pain_below"]:
                signal, threshold = "PAIN", cfg["pain_below"]
            elif cfg["pain_above"] is not None and value > cfg["pain_above"]:
                signal, threshold = "PAIN", cfg["pain_above"]
            elif cfg["pleasure_above"] is not None and value > cfg["pleasure_above"]:
                signal, threshold = "PLEASURE", cfg["pleasure_above"]
            elif cfg["pleasure_below"] is not None and value < cfg["pleasure_below"]:
                signal, threshold = "PLEASURE", cfg["pleasure_below"]
            if signal is not None:
                alert = Alert(
                    name=name,
                    signal=signal,
                    value=value,
                    threshold=threshold,  # type: ignore[arg-type]
                    raised_at=datetime.now(timezone.utc).isoformat(),
                )
                self.alerts.append(alert)
                raised.append(alert)
        return raised

    # ------------------------------------------------------------------
    # Forced decision log: alerts close only on a recorded decision
    # ------------------------------------------------------------------
    def decide(self, alert_index: int, action: str, reason: str) -> Dict:
        """Record a decision against an open alert.

        ``action`` is free text ("escalate", "monitor", "dismiss", ...),
        but it must be accompanied by a ``reason`` — a decision without
        a reason is just an acknowledgement, and the room doesn't
        accept those.
        """
        if not 0 <= alert_index < len(self.alerts):
            raise ValueError(f"alert index out of range: {alert_index}")
        if not action.strip() or not reason.strip():
            raise ValueError("a decision needs both an action and a reason")
        alert = self.alerts[alert_index]
        if not alert.open:
            raise ValueError("alert already has a decision")
        decision = {
            "alert": alert.name,
            "signal": alert.signal,
            "action": action.strip(),
            "reason": reason.strip(),
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        alert.decision = decision
        self.decision_log.append(decision)
        return decision

    def open_alerts(self) -> List[Alert]:
        return [a for a in self.alerts if a.open]

    def room_status(self) -> Dict[str, object]:
        """The room's honest state: open alerts are debts, not noise."""
        return {
            "total_alerts": len(self.alerts),
            "open_alerts": len(self.open_alerts()),
            "decisions_logged": len(self.decision_log),
            "room_clear": not self.open_alerts(),
        }
