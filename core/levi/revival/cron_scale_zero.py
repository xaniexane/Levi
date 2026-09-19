"""cron_scale_zero — scheduled short runs instead of always-on workers.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 4,
scheduler-triggered short runs instead of always-on workers; on owned
hardware, batch cadence lets machines sleep between runs).

Functional pattern studied: replace a 24/7 worker with a schedule of short
runs. The machine (or the wallet) rests between runs, and an append-only
ledger records every run with idempotency watermarks so a crashed or
double-fired run never double-applies work.

What this module is: three real mechanisms, no network. ``CronExpr`` parses
five-field cron expressions (ranges, steps, lists) and computes the next
fire time after any datetime — a genuine scheduling algorithm. ``RunLedger``
is an append-only JSONL run record with watermark idempotency
(``record()`` refuses to re-record a run id). ``savings()`` does the honest
cost math: always-on cost vs scheduled cost given run duration and
electricity/hardware rates, plus ``quiet_windows()`` showing the sleep gaps
a schedule leaves on owned hardware.

Honest limits: this module computes schedules and keeps the ledger — it
does not install crontabs or wake machines. Execution of the job itself is
the operator's runner; the ledger is how the runner stays idempotent.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

ORIGIN = "levi-revival/cron-scale-zero"

_FIELD_RANGES = {
    0: (0, 59),  # minute
    1: (0, 23),  # hour
    2: (1, 31),  # day of month
    3: (1, 12),  # month
    4: (0, 6),  # day of week (0 = Monday, per datetime.weekday())
}


def _parse_field(text: str, lo: int, hi: int) -> List[int]:
    """Parse one cron field into a sorted value list."""
    values: set[int] = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_text = part.split("/", 1)
            step = int(step_text)
            if step < 1:
                raise ValueError(f"bad step in cron field: {text!r}")
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)
        if not (lo <= start <= hi and lo <= end <= hi and start <= end):
            raise ValueError(f"cron field out of range: {text!r}")
        values.update(range(start, end + 1, step))
    return sorted(values)


class CronExpr:
    """Five-field cron expression with real next-fire computation."""

    def __init__(self, expr: str) -> None:
        fields = expr.split()
        if len(fields) != 5:
            raise ValueError(f"cron expression needs 5 fields: {expr!r}")
        self.expr = expr
        self.minute = _parse_field(fields[0], *_FIELD_RANGES[0])
        self.hour = _parse_field(fields[1], *_FIELD_RANGES[1])
        self.dom = _parse_field(fields[2], *_FIELD_RANGES[2])
        self.month = _parse_field(fields[3], *_FIELD_RANGES[3])
        self.dow = _parse_field(fields[4], *_FIELD_RANGES[4])
        # Track whether dom/dow were restricted (cron OR-semantics).
        self._dom_star = fields[2] == "*"
        self._dow_star = fields[4] == "*"

    def matches(self, dt: datetime) -> bool:
        if dt.minute not in self.minute or dt.hour not in self.hour:
            return False
        if dt.month not in self.month:
            return False
        dom_ok = dt.day in self.dom
        dow_ok = dt.weekday() in self.dow
        if self._dom_star and self._dow_star:
            day_ok = True
        elif self._dom_star:
            day_ok = dow_ok
        elif self._dow_star:
            day_ok = dom_ok
        else:
            day_ok = dom_ok or dow_ok
        return day_ok

    def next_after(self, dt: datetime) -> datetime:
        """Next fire time strictly after ``dt``. Searches minute by minute
        up to ~366 days out; raises if nothing fires (should not happen for
        sane expressions)."""
        candidate = (dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
        limit = candidate + timedelta(days=367)
        while candidate <= limit:
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise RuntimeError(f"no fire time within a year for {self.expr!r}")

    def upcoming(self, dt: datetime, n: int) -> List[datetime]:
        out = []
        cursor = dt
        for _ in range(n):
            cursor = self.next_after(cursor)
            out.append(cursor)
        return out


@dataclass
class RunRecord:
    run_id: str
    job: str
    scheduled_for: str  # ISO datetime
    started_at: float
    finished_at: Optional[float] = None
    ok: bool = False
    note: str = ""


class DuplicateRunError(Exception):
    """A run id was already recorded — the idempotency watermark fired."""


class RunLedger:
    """Append-only run ledger with idempotency watermarks."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._seen.add(json.loads(line)["run_id"])

    def record(self, record: RunRecord) -> RunRecord:
        if record.run_id in self._seen:
            raise DuplicateRunError(f"run already recorded: {record.run_id}")
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.__dict__) + "\n")
        self._seen.add(record.run_id)
        return record

    def start(
        self, job: str, scheduled_for: datetime, run_id: Optional[str] = None
    ) -> RunRecord:
        rid = run_id or f"{job}-{scheduled_for.isoformat()}"
        return self.record(
            RunRecord(
                run_id=rid,
                job=job,
                scheduled_for=scheduled_for.isoformat(),
                started_at=time.time(),
            )
        )

    def finish(self, run_id: str, ok: bool = True, note: str = "") -> None:
        """Mark a run finished by appending a completion record linked to
        the same run id (the ledger is append-only; history is never edited).
        """
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "run_id": run_id,
                        "event": "finish",
                        "ok": ok,
                        "note": note,
                        "ts": time.time(),
                    }
                )
                + "\n"
            )

    def runs_for(self, job: str) -> List[dict]:
        out = []
        if not self.path.exists():
            return out
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("job") == job:
                out.append(rec)
        return out


@dataclass
class CostModel:
    """Cost math: always-on worker vs scheduled short runs."""

    always_on_watts: float = 0.0  # 0 when the machine can fully sleep
    run_watts: float = 150.0
    sleep_watts: float = 8.0  # owned hardware at rest between runs
    electricity_usd_per_kwh: float = 0.15
    run_minutes: float = 5.0

    def _energy_usd(self, watts: float, hours: float) -> float:
        return (watts / 1000.0) * self.electricity_usd_per_kwh * hours

    def monthly_always_on(self) -> float:
        return self._energy_usd(max(self.always_on_watts, self.run_watts), 24 * 30)

    def monthly_scheduled(self, runs_per_day: float) -> float:
        run_hours = runs_per_day * (self.run_minutes / 60.0) * 30
        sleep_hours = 24 * 30 - run_hours
        return self._energy_usd(self.run_watts, run_hours) + self._energy_usd(
            self.sleep_watts, sleep_hours
        )

    def savings(self, runs_per_day: float) -> Dict[str, float]:
        always = self.monthly_always_on()
        sched = self.monthly_scheduled(runs_per_day)
        return {
            "always_on_usd": round(always, 2),
            "scheduled_usd": round(sched, 2),
            "saved_usd": round(always - sched, 2),
            "saved_pct": round(100 * (always - sched) / always, 1) if always else 0.0,
        }


def quiet_windows(
    fire_times: List[datetime], min_gap: timedelta = timedelta(hours=1)
) -> List[tuple]:
    """Gaps between scheduled runs at least ``min_gap`` long — the sleep
    windows on owned hardware. Returns (start, end, duration) tuples."""
    ordered = sorted(fire_times)
    out = []
    for start, end in zip(ordered, ordered[1:], strict=False):
        if end - start >= min_gap:
            out.append((start, end, end - start))
    return out
