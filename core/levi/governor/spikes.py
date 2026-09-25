"""Spike detection against rolling per-key baselines.

Each metered call is observed under several attribution keys
(``global``, ``provider:…``, ``task:…``, ``tool:…``, ``agent:…``).
A key *spikes* when its current-window token total exceeds N× its
previous-window baseline, or blows an absolute cap. No silent passes:
every breach returns an explicit :class:`SpikeAlert` with the numbers.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from levi.governor.meter import UsageRecord


@dataclass
class SpikeAlert:
    key: str
    window_seconds: int
    current_tokens: int
    baseline_tokens: int
    multiplier: float
    reason: str  # "N× baseline" or "absolute cap"

    def __str__(self) -> str:
        return (
            f"spike on {self.key}: {self.current_tokens:,} tokens in "
            f"{self.window_seconds}s ({self.reason}; "
            f"baseline {self.baseline_tokens:,})"
        )


class SpikeDetector:
    """Two-window spike detector. Deterministic; injectable clock."""

    def __init__(
        self,
        window_seconds: int = 600,
        multiplier: float = 4.0,
        absolute_cap: int = 500_000,
        min_baseline_tokens: int = 2_000,
        clock=time.time,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if multiplier <= 1:
            raise ValueError("multiplier must be > 1")
        self.window_seconds = window_seconds
        self.multiplier = multiplier
        self.absolute_cap = absolute_cap
        self.min_baseline_tokens = min_baseline_tokens
        self._clock = clock
        # key -> deque[(ts, tokens)]
        self._events: dict[str, deque] = {}

    @staticmethod
    def keys_for(record: UsageRecord) -> list[str]:
        keys = ["global"]
        if record.provider:
            keys.append(f"provider:{record.provider}")
        if record.task_id:
            keys.append(f"task:{record.task_id}")
        if record.tool_name:
            keys.append(f"tool:{record.tool_name}")
        if record.agent_id:
            keys.append(f"agent:{record.agent_id}")
        return keys

    def observe(self, record: UsageRecord) -> list[SpikeAlert]:
        """Feed one metered record; return any spike alerts (possibly empty)."""
        now = record.ts or self._clock()
        alerts: list[SpikeAlert] = []
        for key in self.keys_for(record):
            events = self._events.setdefault(key, deque())
            events.append((now, record.total))
            self._prune(key, now)
            alert = self._check(key, now)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - 2 * self.window_seconds
        events = self._events[key]
        while events and events[0][0] < cutoff:
            events.popleft()

    def _window_total(
        self, key: str, start: float, end: float, *, inclusive_end: bool = False
    ) -> int:
        if inclusive_end:
            return sum(t for ts, t in self._events[key] if start <= ts <= end)
        return sum(t for ts, t in self._events[key] if start <= ts < end)

    def _check(self, key: str, now: float) -> SpikeAlert | None:
        w = self.window_seconds
        # Baseline: [now-2w, now-w). Current: [now-w, now] — the newest
        # record is timestamped at `now`, so the current window must
        # include it or every observation misses its own call.
        current = self._window_total(key, now - w, now, inclusive_end=True)
        baseline = self._window_total(key, now - 2 * w, now - w)

        if self.absolute_cap and current > self.absolute_cap:
            return SpikeAlert(
                key=key,
                window_seconds=w,
                current_tokens=current,
                baseline_tokens=baseline,
                multiplier=self.multiplier,
                reason=f"absolute cap ({self.absolute_cap:,} tokens)",
            )
        floor = max(baseline, self.min_baseline_tokens)
        if current >= self.min_baseline_tokens and current > self.multiplier * floor:
            return SpikeAlert(
                key=key,
                window_seconds=w,
                current_tokens=current,
                baseline_tokens=baseline,
                multiplier=self.multiplier,
                reason=f"{current / floor:.1f}× baseline",
            )
        return None

    def baseline_report(self, key: str, now: float | None = None) -> dict:
        """Current numbers for one key (for diagnostics)."""
        now = self._clock() if now is None else now
        w = self.window_seconds
        return {
            "key": key,
            "window_seconds": w,
            "current_tokens": self._window_total(key, now - w, now, inclusive_end=True),
            "baseline_tokens": self._window_total(key, now - 2 * w, now - w),
            "multiplier": self.multiplier,
            "absolute_cap": self.absolute_cap,
        }
