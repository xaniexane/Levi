"""Dweller jobs — the data model and the state machine.

A :class:`Job` is one unit of grinding work: an id, a kind (one of the
built-in runner kinds), parameters, a sandbox root the job may not
leave, and an ordered list of :class:`JobStep`s.

State machine: ``queued -> running -> done | failed``. A job that is
denied at its permission gate or refused for a sandbox violation never
leaves ``queued`` — the receipt records why. A failed job is resumable:
:meth:`Job.resume` returns it to ``running`` and the engine continues
from the first step that is not ``done``.

stdlib only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

#: The only states a job may hold. Terminal: done, failed.
STATES = ("queued", "running", "done", "failed")
TERMINAL = ("done", "failed")

#: The only states a step may hold.
STEP_STATES = ("queued", "running", "done", "failed", "skipped")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "job") -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12])


@dataclass
class JobStep:
    """One step of a grind job."""

    id: str
    label: str
    kind: str  # runner kind: repo-sweep | crossref | watch
    state: str = "queued"
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "state": self.state,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JobStep":
        return cls(
            id=d["id"],
            label=d["label"],
            kind=d["kind"],
            state=d.get("state", "queued"),
            result=dict(d.get("result", {})),
            error=d.get("error", ""),
            attempts=int(d.get("attempts", 0)),
        )


@dataclass
class Job:
    """One grind job, owned by the Dweller."""

    id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    sandbox_root: str = ""
    steps: List[JobStep] = field(default_factory=list)
    state: str = "queued"
    created_ts: str = ""
    started_ts: str = ""
    finished_ts: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError("bad job state: %r" % self.state)
        if not self.created_ts:
            self.created_ts = _utcnow()

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL

    def pending_steps(self) -> List[JobStep]:
        """Steps not yet done, in order — the resume frontier."""
        return [s for s in self.steps if s.state != "done"]

    def mark_running(self) -> None:
        if self.state == "running":
            return  # idempotent: resume paths may already hold it
        if self.state not in ("queued", "failed"):
            raise ValueError(
                "job %s cannot start from state %r" % (self.id, self.state)
            )
        self.state = "running"
        if not self.started_ts:
            self.started_ts = _utcnow()

    def mark_done(self, note: str = "") -> None:
        self.state = "done"
        self.finished_ts = _utcnow()
        if note:
            self.note = note

    def mark_failed(self, note: str = "") -> None:
        self.state = "failed"
        self.finished_ts = _utcnow()
        if note:
            self.note = note

    def resume(self) -> "Job":
        """Return this job to running; the engine resumes at the first
        step that is not done. Only failed (or queued) jobs resume."""
        if self.state not in ("failed", "queued"):
            raise ValueError(
                "job %s cannot resume from state %r" % (self.id, self.state)
            )
        self.state = "running"
        self.finished_ts = ""
        self.note = ""
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "params": self.params,
            "sandbox_root": self.sandbox_root,
            "steps": [s.to_dict() for s in self.steps],
            "state": self.state,
            "created_ts": self.created_ts,
            "started_ts": self.started_ts,
            "finished_ts": self.finished_ts,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Job":
        return cls(
            id=d["id"],
            kind=d["kind"],
            params=dict(d.get("params", {})),
            sandbox_root=d.get("sandbox_root", ""),
            steps=[JobStep.from_dict(s) for s in d.get("steps", [])],
            state=d.get("state", "queued"),
            created_ts=d.get("created_ts", ""),
            started_ts=d.get("started_ts", ""),
            finished_ts=d.get("finished_ts", ""),
            note=d.get("note", ""),
        )


def new_job(
    kind: str,
    params: Optional[Dict[str, Any]] = None,
    sandbox_root: str = "",
    steps: Optional[List[JobStep]] = None,
    job_id: str = "",
) -> Job:
    """Create a fresh queued job."""
    return Job(
        id=job_id or _new_id(),
        kind=kind,
        params=dict(params or {}),
        sandbox_root=sandbox_root,
        steps=list(steps or []),
        state="queued",
    )
