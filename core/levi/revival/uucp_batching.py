"""uucp_batching — store-and-forward batching with dial windows.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 4:
hosts connect once daily, flush queued mail/news/files, disconnect).

Functional pattern studied: instead of staying connected (or keeping an
endpoint warm) around the clock, queue work locally, connect during a short
scheduled window, flush everything at once, collect acknowledgments, and
disconnect. The modern analogs named in the studied material are batch
inference APIs (quoted at 30-50% discounts) and queued GPU windows instead
of always-warm endpoints — the mechanism is identical: batch the work,
pay the cheap window rate, sleep the rest.

What this module is: a real local spool-and-flush mechanism. ``Spool``
queues jobs as durable files under a spool directory (``queued/``);
``DialWindow`` decides whether a connect window is open; ``flush()`` moves
queued jobs to ``sent/`` through a pluggable transport callable, writes an
ack record per job into ``acked/``, and applies exponential backoff with a
dead-letter queue after repeated failures. Everything is files on disk, so
a crash between windows loses nothing.

Honest limits: the transport is operator-supplied (a callable taking the
job dict and returning an ack string); this module never touches the
network. Cost comparison uses the operator's quoted rates — the 30-50%
discount figure from the studied material is a *parameter default*, not a
promise.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

ORIGIN = "levi-revival/uucp-batching"

Transport = Callable[[dict], str]  # job -> ack token; raises on failure


@dataclass
class Job:
    job_id: str
    kind: str
    payload: dict
    enqueued_at: float = field(default_factory=time.time)
    attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "payload": self.payload,
            "enqueued_at": self.enqueued_at,
            "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            job_id=data["job_id"],
            kind=data["kind"],
            payload=data["payload"],
            enqueued_at=data.get("enqueued_at", time.time()),
            attempts=data.get("attempts", 0),
        )


@dataclass
class DialWindow:
    """A daily connect window, e.g. 02:00-02:30."""

    start: dtime
    end: dtime
    name: str = "nightly"

    def is_open(self, at: Optional[datetime] = None) -> bool:
        at = at or datetime.now()
        now = at.time()
        if self.start <= self.end:
            return self.start <= now < self.end
        return now >= self.start or now < self.end  # wraps midnight

    def next_open(self, at: Optional[datetime] = None) -> datetime:
        at = at or datetime.now()
        candidate = at.replace(
            hour=self.start.hour, minute=self.start.minute, second=0, microsecond=0
        )
        if candidate <= at:
            candidate += timedelta(days=1)
        return candidate


@dataclass
class FlushReport:
    window: str
    attempted: int
    acked: int
    failed: int
    dead_lettered: int
    acks: Dict[str, str] = field(default_factory=dict)  # job_id -> ack


class Spool:
    """Durable store-and-forward queue backed by files."""

    def __init__(
        self, root: Path, max_attempts: int = 5, backoff_base_s: float = 60.0
    ) -> None:
        self.root = Path(root)
        self.queued = self.root / "queued"
        self.sent = self.root / "sent"
        self.acked = self.root / "acked"
        self.dead = self.root / "dead"
        for d in (self.queued, self.sent, self.acked, self.dead):
            d.mkdir(parents=True, exist_ok=True)
        self.max_attempts = max_attempts
        self.backoff_base_s = backoff_base_s
        self._last_failure_at: Dict[str, float] = {}

    # -- enqueue ---------------------------------------------------------------
    def enqueue(self, kind: str, payload: dict, job_id: Optional[str] = None) -> Job:
        job = Job(job_id=job_id or uuid.uuid4().hex, kind=kind, payload=payload)
        self._write(self.queued, job)
        return job

    def queued_jobs(self) -> List[Job]:
        return sorted(
            (self._read(self.queued / p) for p in self.queued.glob("*.json")),
            key=lambda j: j.enqueued_at,
        )

    def __len__(self) -> int:
        return len(list(self.queued.glob("*.json")))

    # -- flush -------------------------------------------------------------------
    def flush(
        self, transport: Transport, window: DialWindow, at: Optional[datetime] = None
    ) -> FlushReport:
        """Flush the queue if the dial window is open. Jobs that fail are
        kept queued with exponential backoff; jobs past max_attempts go to
        the dead-letter queue. Returns a full report."""
        report = FlushReport(
            window=window.name, attempted=0, acked=0, failed=0, dead_lettered=0
        )
        if not window.is_open(at):
            return report
        now = time.time()
        for job in self.queued_jobs():
            if not self._backoff_elapsed(job, now):
                continue
            report.attempted += 1
            job.attempts += 1
            try:
                ack = transport(job.to_dict())
            except Exception:
                report.failed += 1
                self._last_failure_at[job.job_id] = now
                if job.attempts >= self.max_attempts:
                    self._move(self.queued, self.dead, job)
                    report.dead_lettered += 1
                    del self._last_failure_at[job.job_id]
                else:
                    self._write(self.queued, job)  # persist attempt count
                continue
            self._move(self.queued, self.sent, job)
            (self.acked / f"{job.job_id}.ack").write_text(
                json.dumps({"job_id": job.job_id, "ack": ack, "at": time.time()}),
                encoding="utf-8",
            )
            report.acked += 1
            report.acks[job.job_id] = ack
            self._last_failure_at.pop(job.job_id, None)
        return report

    def _backoff_elapsed(self, job: Job, now: float) -> bool:
        last = self._last_failure_at.get(job.job_id)
        if last is None:
            return True
        wait = self.backoff_base_s * (2 ** max(0, job.attempts - 1))
        return (now - last) >= wait

    def dead_letters(self) -> List[Job]:
        return [self._read(p) for p in self.dead.glob("*.json")]

    def requeue_dead(self, job_id: str) -> Job:
        """Return a dead-lettered job to the queue with attempts reset."""
        path = self.dead / f"{job_id}.json"
        if not path.exists():
            raise ValueError(f"no dead letter: {job_id}")
        job = self._read(path)
        job.attempts = 0
        path.unlink()
        self._write(self.queued, job)
        return job

    # -- file helpers --------------------------------------------------------------
    def _write(self, directory: Path, job: Job) -> None:
        (directory / f"{job.job_id}.json").write_text(
            json.dumps(job.to_dict()), encoding="utf-8"
        )

    def _read(self, path: Path) -> Job:
        return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _move(self, src_dir: Path, dst_dir: Path, job: Job) -> None:
        (dst_dir / f"{job.job_id}.json").write_text(
            json.dumps(job.to_dict()), encoding="utf-8"
        )
        (src_dir / f"{job.job_id}.json").unlink(missing_ok=True)


@dataclass
class BatchRateCard:
    """Quoted rates for always-warm vs batched windows (operator-supplied)."""

    warm_usd_per_1k: float = 1.0
    batch_usd_per_1k: float = 0.6  # default ~40% discount; a parameter, not a promise

    @property
    def discount_pct(self) -> float:
        if self.warm_usd_per_1k <= 0:
            return 0.0
        return 100.0 * (1 - self.batch_usd_per_1k / self.warm_usd_per_1k)

    def compare(self, units_per_month_k: float) -> Dict[str, float]:
        warm = self.warm_usd_per_1k * units_per_month_k
        batch = self.batch_usd_per_1k * units_per_month_k
        return {
            "warm_usd": round(warm, 2),
            "batch_usd": round(batch, 2),
            "saved_usd": round(warm - batch, 2),
            "discount_pct": round(self.discount_pct, 1),
        }
