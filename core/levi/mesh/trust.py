"""Peer trust — scoring plus the drift-alarm hook.

Scoring is transparent: successes build trust, failures/mismatches/
misreports burn it. The drift-alarm is the silent part, per Chauncey's
canon (2026-09-18): "Derivation or sometimes variation — too much
drift in either direction triggers an invisible alarm."

Either direction means what it says:

* drift toward failure — high failure or replica-disagreement rates;
* drift toward the implausible — sustained perfect results at
  impossible speed (fabricated results look *too* clean).

Flags are SILENT by design: they are recorded in a founder-visible
log and never announced to the flagged peer. There is deliberately
no broadcast path — a peer that knows it tripped the alarm can adapt
around it. ``flags_for_founder`` enforces the founder gate via
``levi.cybrus.identity.is_founder``; the public surface exposes only
``score()``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Dict, List, Optional

try:
    from levi.cybrus.identity import is_founder
except ImportError:  # pragma: no cover - defensive; package is present

    def is_founder(record) -> bool:  # type: ignore[misc]
        return False


# -- tuning: when the invisible alarm trips --------------------------------
_MIN_OBSERVATIONS = 3  # need at least this many before flagging failure
_FAILURE_RATE_ALARM = 0.5  # drift toward failure
_MISMATCH_RATE_ALARM = 0.3  # drift toward disagreement
_PERFECT_MIN_OBS = 20  # need volume before calling "too perfect"
_PERFECT_SPEED_RATIO = 0.1  # avg latency < 10% of fleet median at 100% ok


class TrustMonitor:
    """Per-peer trust scores and silent drift flags."""

    def __init__(self) -> None:
        self._ok: Dict[str, int] = {}
        self._failed: Dict[str, int] = {}
        self._mismatched: Dict[str, int] = {}
        self._misreported: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}
        self._flags: List[Dict] = []
        self._flagged: Dict[str, set] = {}  # node_id -> kinds already raised

    # -- observation --------------------------------------------------------

    def _ensure(self, node_id: str) -> None:
        for store in (self._ok, self._failed, self._mismatched, self._misreported):
            store.setdefault(node_id, 0)
        self._latencies.setdefault(node_id, [])
        self._flagged.setdefault(node_id, set())

    def record_success(self, node_id: str, latency_s: float = 0.0) -> None:
        self._ensure(node_id)
        self._ok[node_id] += 1
        if latency_s > 0:
            self._latencies[node_id].append(latency_s)
        self._evaluate(node_id)

    def record_failure(self, node_id: str) -> None:
        self._ensure(node_id)
        self._failed[node_id] += 1
        self._evaluate(node_id)

    def record_mismatch(self, node_id: str) -> None:
        """This node's result disagreed with an agreed replica pair."""
        self._ensure(node_id)
        self._mismatched[node_id] += 1
        self._evaluate(node_id)

    def record_misreport(self, node_id: str) -> None:
        """Advertised resources proved false (offered what it lacks)."""
        self._ensure(node_id)
        self._misreported[node_id] += 1
        self._evaluate(node_id)

    # -- public surface -----------------------------------------------------

    def observations(self, node_id: str) -> int:
        self._ensure(node_id)
        return self._ok[node_id] + self._failed[node_id] + self._mismatched[node_id]

    def score(self, node_id: str) -> float:
        """Public trust score in [0, 1]. Starts at 1.0, only moves down."""
        self._ensure(node_id)
        score = 1.0
        score -= 0.3 * self._failed[node_id]
        score -= 0.5 * self._mismatched[node_id]
        score -= 0.4 * self._misreported[node_id]
        return max(0.0, round(score, 3))

    def flags_for_founder(self, identity_record: Optional[Dict] = None) -> List[Dict]:
        """The silent flag log — founder only. Anyone else gets []."""
        if not is_founder(identity_record):
            return []
        return [dict(f) for f in self._flags]

    # -- the invisible alarm -------------------------------------------------

    def _raise(self, node_id: str, kind: str, detail: str) -> None:
        if kind in self._flagged[node_id]:
            return  # one silent flag per kind per node; no noise
        self._flagged[node_id].add(kind)
        self._flags.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "node_id": node_id,
                "kind": kind,
                "detail": detail,
            }
        )

    def _evaluate(self, node_id: str) -> None:
        n = self.observations(node_id)
        if n >= _MIN_OBSERVATIONS:
            bad = self._failed[node_id] + self._mismatched[node_id]
            if bad / n >= _FAILURE_RATE_ALARM:
                self._raise(
                    node_id,
                    "degraded",
                    f"failure rate {bad}/{n} — drift toward failure",
                )
            if self._mismatched[node_id] / n >= _MISMATCH_RATE_ALARM:
                self._raise(
                    node_id,
                    "integrity",
                    f"replica disagreement {self._mismatched[node_id]}"
                    f"/{n} — results cannot be trusted",
                )
        if self._misreported[node_id] >= 2:
            self._raise(
                node_id, "misreport", "advertised resources proved false more than once"
            )
        # too perfect: flawless at impossible speed
        if (
            n >= _PERFECT_MIN_OBS
            and self._failed[node_id] == 0
            and self._mismatched[node_id] == 0
        ):
            fleet_lat = [v for lat in self._latencies.values() for v in lat]
            mine = self._latencies[node_id]
            if fleet_lat and mine:
                med = median(fleet_lat)
                if med > 0 and (sum(mine) / len(mine)) < med * _PERFECT_SPEED_RATIO:
                    self._raise(
                        node_id,
                        "anomaly",
                        f"{n}/{n} perfect at <10% of fleet median latency — "
                        "drift toward the implausible; possible fabrication",
                    )
