"""Spool it, grade it, poll it: graded batch transfer.

Studied from: protocols-hunt-20260916-0041/report.md (Find 2 - UUCP)

The load-bearing mechanism: jobs are sealed into a spool with a
*grade* — a single character priority where lower means "transfer
first" (grades run 0-9, A-Z, a-z). When the poll window opens, the
machine connects once, pushes the spool in grade order, and hangs up.
Important work crosses first; cheap work fills the remaining window.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is grade-ordered spooling with a
connect-transfer-hangup poll cycle. Not revived: actual dial-up
handshakes — the "call" is a scheduling event, not a modem.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


ORIGIN = "levi-revival/spool-grade-poll"

_GRADES = string.digits + string.ascii_uppercase + string.ascii_lowercase


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SpoolError(Exception):
    """Base class for spool failures."""


def grade_rank(grade: str) -> int:
    """Order grades: '0' (highest) through 'z' (lowest)."""
    if len(grade) != 1 or grade not in _GRADES:
        raise SpoolError(f"invalid grade {grade!r}: one char in 0-9A-Za-z")
    return _GRADES.index(grade)


class JobState(str, Enum):
    SPOOLED = "spooled"
    IN_FLIGHT = "in-flight"
    DONE = "done"
    FAILED = "failed"


@dataclass
class SpoolJob:
    """One sealed unit of transfer work."""

    job_id: str
    description: str
    grade: str = "d"  # single char; '0' first, 'z' last
    payload: str = ""
    destination: str = ""
    state: JobState = JobState.SPOOLED
    spooled_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None

    def __post_init__(self) -> None:
        grade_rank(self.grade)  # validate


class Spool:
    """A graded job spool with a poll cycle.

    ``spool`` seals jobs in. ``poll`` runs one connection: jobs leave in
    grade order (ties keep FIFO), and the cycle stops when the window
    budget (max jobs per poll) is exhausted — leftover work waits for
    the next poll, still grade-ordered.
    """

    def __init__(self, max_per_poll: int = 25) -> None:
        if max_per_poll < 1:
            raise SpoolError("max_per_poll must be >= 1")
        self.max_per_poll = max_per_poll
        self.jobs: dict[str, SpoolJob] = {}
        self.poll_log: list[str] = []  # human-readable history

    # -- spooling -----------------------------------------------------------

    def spool(self, job: SpoolJob) -> None:
        if job.job_id in self.jobs:
            raise SpoolError(f"duplicate job id: {job.job_id}")
        self.jobs[job.job_id] = job

    def ordered(self) -> list[SpoolJob]:
        """Pending jobs in transfer order: grade first, then FIFO."""
        pending = [j for j in self.jobs.values() if j.state == JobState.SPOOLED]
        return sorted(pending, key=lambda j: (grade_rank(j.grade), j.spooled_at))

    # -- polling --------------------------------------------------------------

    def poll(self, connection: str = "dial") -> list[SpoolJob]:
        """Run one connect-transfer-hangup cycle; return transferred jobs."""
        transferred: list[SpoolJob] = []
        for job in self.ordered():
            if len(transferred) >= self.max_per_poll:
                break
            job.state = JobState.IN_FLIGHT
            # The transfer itself is the queue's business; the spool
            # records the hand-off honestly and marks completion.
            job.state = JobState.DONE
            job.completed_at = datetime.now().isoformat()
            transferred.append(job)
        self.poll_log.append(
            f"{datetime.now().isoformat()} {connection}: "
            f"transferred {len(transferred)} job(s)"
        )
        return transferred

    def fail(self, job_id: str, reason: str = "") -> None:
        """Mark a job failed (e.g. remote rejected it); it may be re-spooled."""
        job = self.jobs.get(job_id)
        if job is None:
            raise SpoolError(f"unknown job: {job_id}")
        job.state = JobState.FAILED
        self.poll_log.append(
            f"{datetime.now().isoformat()} failed {job_id}"
            + (f": {reason}" if reason else "")
        )

    # -- queries ------------------------------------------------------------

    def by_grade(self, grade: str) -> list[SpoolJob]:
        grade_rank(grade)
        return [
            j
            for j in self.jobs.values()
            if j.grade == grade and j.state == JobState.SPOOLED
        ]

    def pending_count(self) -> int:
        return sum(1 for j in self.jobs.values() if j.state == JobState.SPOOLED)

    # -- persistence ------------------------------------------------------------

    def seal(self, directory: str | Path) -> None:
        """Write each spooled job as a file pair (description + payload)."""
        spool_dir = Path(directory)
        spool_dir.mkdir(parents=True, exist_ok=True)
        for job in self.jobs.values():
            if job.state != JobState.SPOOLED:
                continue
            (spool_dir / f"{job.job_id}.desc").write_text(
                f"grade={job.grade}\ndest={job.destination}\n{job.description}\n",
                encoding="utf-8",
            )
            (spool_dir / f"{job.job_id}.data").write_text(job.payload, encoding="utf-8")
