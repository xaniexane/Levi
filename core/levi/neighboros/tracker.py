"""NeighborOS live Jobs project — local-first service-job pipeline.

Tracks the dispatch queue NeighborOS operates on: service jobs move
``requested`` → ``dispatched`` → ``in_progress`` → ``completed``
(with ``cancelled`` as the other terminal state), and a worker roster
maps who can take work in which category. This is the queue the daily
operations brief reads.

Local only: state lives under ``~/.levi/neighboros/`` with owner-only
permissions (dir 0700, files 0600), written atomically. No network, no
payments, no external dispatch service — the module tracks the queue,
it does not execute real-world dispatch.

Honest contract
---------------
* The tracker never invents jobs, workers, estimates, or payouts.
* ``upsert_job`` is idempotent on (title, customer, category): re-adding
  the same request refreshes ``updated_at`` instead of duplicating.
* All example data in tests/docs is synthetic.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STATUSES = ("requested", "dispatched", "in_progress", "completed", "cancelled")
TERMINAL_STATUSES = ("completed", "cancelled")
OPEN_STATUSES = ("requested", "dispatched", "in_progress")

TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "requested": ("dispatched", "cancelled"),
    "dispatched": ("in_progress", "requested", "cancelled"),
    "in_progress": ("completed", "dispatched", "cancelled"),
    "completed": (),
    "cancelled": (),
}

PRIORITIES = ("normal", "high", "emergency")

WORKER_STATUSES = ("active", "inactive")

# Service categories from the NeighborOS blueprints (free text also allowed).
KNOWN_CATEGORIES = (
    "handyman",
    "lawn care",
    "cleaning",
    "junk removal",
    "moving help",
    "tech support",
    "plumbing",
    "electrical",
    "hvac",
    "appliance help",
)

MAX_TITLE_LEN = 200
MAX_NAME_LEN = 120
MAX_CATEGORY_LEN = 60
MAX_NOTE_LEN = 2000


def default_neighboros_dir() -> Path:
    """Default state directory (overridable in tests via monkeypatch)."""
    return Path.home() / ".levi" / "neighboros"


def default_jobs_path() -> Path:
    return default_neighboros_dir() / "jobs.json"


def default_workers_path() -> Path:
    return default_neighboros_dir() / "workers.json"


def default_briefs_dir() -> Path:
    return default_neighboros_dir() / "briefs"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_iso() -> str:
    return date.today().isoformat()


def _check_str(name: str, value: Any, max_len: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    value = value.strip()
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")
    if len(value) > max_len:
        raise ValueError(f"{name} exceeds {max_len} chars ({len(value)})")
    return value


def _check_status(status: Any) -> str:
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    return status


def _check_priority(priority: Any) -> str:
    if not isinstance(priority, str) or priority not in PRIORITIES:
        raise ValueError(f"unknown priority {priority!r}; expected one of {PRIORITIES}")
    return priority


def _check_due(due: Any) -> str:
    if due is None:
        return ""
    due = _check_str("due", due, 10, allow_empty=True)
    if not due:
        return ""
    try:
        date.fromisoformat(due)
    except ValueError:
        raise ValueError(f"due must be YYYY-MM-DD, got {due!r}") from None
    return due


def _tighten(path: Path) -> None:
    try:
        os.chmod(path.parent, 0o700)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".nos.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _tighten(path)


def _read_store(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class JobNote:
    ts: str
    text: str

    def to_dict(self) -> Dict[str, str]:
        return {"ts": self.ts, "text": self.text}


@dataclass
class ServiceJob:
    id: int
    title: str
    category: str = ""
    priority: str = "normal"
    status: str = "requested"
    customer: str = ""
    worker: str = ""
    due: str = ""
    notes: List[JobNote] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.title = _check_str("title", self.title, MAX_TITLE_LEN)
        self.category = _check_str(
            "category", self.category, MAX_CATEGORY_LEN, allow_empty=True
        )
        self.priority = _check_priority(self.priority)
        self.status = _check_status(self.status)
        self.customer = _check_str(
            "customer", self.customer, MAX_NAME_LEN, allow_empty=True
        )
        self.worker = _check_str("worker", self.worker, MAX_NAME_LEN, allow_empty=True)
        self.due = _check_due(self.due)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["notes"] = [n.to_dict() if isinstance(n, JobNote) else n for n in self.notes]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceJob":
        notes = [
            JobNote(ts=n.get("ts", ""), text=n.get("text", ""))
            for n in (data.get("notes") or [])
            if isinstance(n, dict)
        ]
        return cls(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            category=str(data.get("category", "") or ""),
            priority=str(data.get("priority", "") or "normal"),
            status=str(data.get("status", "") or "requested"),
            customer=str(data.get("customer", "") or ""),
            worker=str(data.get("worker", "") or ""),
            due=str(data.get("due", "") or ""),
            notes=notes,
            created_at=str(data.get("created_at", "")) or _utcnow(),
            updated_at=str(data.get("updated_at", "")) or _utcnow(),
        )

    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


@dataclass
class Worker:
    id: int
    name: str
    categories: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.name = _check_str("name", self.name, MAX_NAME_LEN)
        cats = []
        for c in self.categories or []:
            c = _check_str("category", c, MAX_CATEGORY_LEN)
            if c and c not in cats:
                cats.append(c)
        self.categories = cats
        if self.status not in WORKER_STATUSES:
            raise ValueError(
                f"unknown worker status {self.status!r}; "
                f"expected one of {WORKER_STATUSES}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Worker":
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", "")),
            categories=[str(c) for c in (data.get("categories") or [])],
            status=str(data.get("status", "") or "active"),
            created_at=str(data.get("created_at", "")) or _utcnow(),
        )


class NeighborTracker:
    """Local-first NeighborOS Jobs project: service jobs + worker roster."""

    def __init__(
        self,
        jobs_path: Optional[Path] = None,
        workers_path: Optional[Path] = None,
    ) -> None:
        self.jobs_path = (
            Path(jobs_path) if jobs_path is not None else default_jobs_path()
        )
        self.workers_path = (
            Path(workers_path) if workers_path is not None else default_workers_path()
        )
        self._jobs: Dict[int, ServiceJob] = {}
        self._workers: Dict[int, Worker] = {}
        self._next_job_id = 1
        self._next_worker_id = 1
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        data = _read_store(self.jobs_path)
        if data is not None:
            self._next_job_id = int(data.get("next_id", 1) or 1)
            for item in data.get("jobs", []) or []:
                try:
                    job = ServiceJob.from_dict(item)
                except (ValueError, KeyError, TypeError):
                    continue
                self._jobs[job.id] = job
        wdata = _read_store(self.workers_path)
        if wdata is not None:
            self._next_worker_id = int(wdata.get("next_id", 1) or 1)
            for item in wdata.get("workers", []) or []:
                try:
                    worker = Worker.from_dict(item)
                except (ValueError, KeyError, TypeError):
                    continue
                self._workers[worker.id] = worker

    def _persist_jobs(self) -> None:
        _atomic_write(
            self.jobs_path,
            {
                "version": 1,
                "next_id": self._next_job_id,
                "jobs": [j.to_dict() for j in self._jobs.values()],
            },
        )

    def _persist_workers(self) -> None:
        _atomic_write(
            self.workers_path,
            {
                "version": 1,
                "next_id": self._next_worker_id,
                "workers": [w.to_dict() for w in self._workers.values()],
            },
        )

    # -- jobs -----------------------------------------------------------

    def add_job(
        self,
        title: str,
        category: str = "",
        priority: str = "normal",
        customer: str = "",
        due: str = "",
    ) -> ServiceJob:
        """Request a new service job (starts in ``requested``)."""
        job = ServiceJob(
            id=self._next_job_id,
            title=title,
            category=category or "",
            priority=priority,
            customer=customer or "",
            due=due or "",
        )
        self._jobs[job.id] = job
        self._next_job_id += 1
        self._persist_jobs()
        return job

    @staticmethod
    def _identity_key(title: str, customer: str, category: str) -> Tuple[str, str, str]:
        return (
            title.strip().casefold(),
            customer.strip().casefold(),
            category.strip().casefold(),
        )

    def find_job(
        self, title: str, customer: str = "", category: str = ""
    ) -> Optional[ServiceJob]:
        key = self._identity_key(title, customer, category)
        for job in self._jobs.values():
            if self._identity_key(job.title, job.customer, job.category) == key:
                return job
        return None

    def upsert_job(
        self,
        title: str,
        customer: str = "",
        category: str = "",
        priority: str = "normal",
        due: str = "",
        note: Optional[str] = None,
    ) -> Tuple[ServiceJob, bool]:
        """Idempotent request: same (title, customer, category) refreshes."""
        existing = self.find_job(title, customer, category)
        if existing is None:
            job = self.add_job(
                title=title,
                category=category,
                priority=priority,
                customer=customer,
                due=due,
            )
            if note:
                self.note_job(job.id, note)
                job = self.get_job(job.id)
            return job, True
        if note:
            text = _check_str("note", note, MAX_NOTE_LEN)
            if text not in {n.text for n in existing.notes}:
                existing.notes.append(JobNote(ts=_utcnow(), text=text))
        existing.updated_at = _utcnow()
        self._persist_jobs()
        return existing, False

    def get_job(self, job_id: int) -> ServiceJob:
        try:
            jid = int(job_id)
        except (TypeError, ValueError):
            raise ValueError(f"job id must be an integer, got {job_id!r}") from None
        job = self._jobs.get(jid)
        if job is None:
            raise KeyError(f"no job with id {jid}")
        return job

    def list_jobs(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[ServiceJob]:
        if status is not None:
            _check_status(status)
        jobs = sorted(self._jobs.values(), key=lambda j: j.id)
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        if category is not None:
            jobs = [j for j in jobs if j.category.casefold() == category.casefold()]
        return jobs

    @staticmethod
    def _check_transition(current: str, new: str) -> None:
        _check_status(new)
        allowed = TRANSITIONS.get(current, ())
        if new != current and new not in allowed:
            raise ValueError(
                f"invalid transition {current!r} → {new!r}; "
                f"allowed from {current!r}: {allowed or '(none)'}"
            )

    def move_job(self, job_id: int, status: str) -> ServiceJob:
        job = self.get_job(job_id)
        self._check_transition(job.status, status)
        job.status = status
        job.updated_at = _utcnow()
        self._persist_jobs()
        return job

    def assign_job(self, job_id: int, worker_name: str) -> ServiceJob:
        """Dispatch: assign a worker; requested jobs move to dispatched."""
        worker_name = _check_str("worker", worker_name, MAX_NAME_LEN)
        job = self.get_job(job_id)
        job.worker = worker_name
        if job.status == "requested":
            job.status = "dispatched"
        job.updated_at = _utcnow()
        self._persist_jobs()
        return job

    def update_job(
        self,
        job_id: int,
        title: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        customer: Optional[str] = None,
        due: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ServiceJob:
        job = self.get_job(job_id)
        if title is not None:
            job.title = _check_str("title", title, MAX_TITLE_LEN)
        if category is not None:
            job.category = _check_str(
                "category", category, MAX_CATEGORY_LEN, allow_empty=True
            )
        if priority is not None:
            job.priority = _check_priority(priority)
        if customer is not None:
            job.customer = _check_str(
                "customer", customer, MAX_NAME_LEN, allow_empty=True
            )
        if due is not None:
            job.due = _check_due(due)
        if status is not None:
            self._check_transition(job.status, status)
            job.status = status
        job.updated_at = _utcnow()
        self._persist_jobs()
        return job

    def note_job(self, job_id: int, text: str) -> JobNote:
        text = _check_str("note", text, MAX_NOTE_LEN)
        job = self.get_job(job_id)
        note = JobNote(ts=_utcnow(), text=text)
        job.notes.append(note)
        job.updated_at = _utcnow()
        self._persist_jobs()
        return note

    # -- workers ----------------------------------------------------------

    def add_worker(self, name: str, categories: List[str]) -> Worker:
        worker = Worker(
            id=self._next_worker_id, name=name, categories=list(categories or [])
        )
        self._workers[worker.id] = worker
        self._next_worker_id += 1
        self._persist_workers()
        return worker

    def get_worker(self, worker_id: int) -> Worker:
        try:
            wid = int(worker_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"worker id must be an integer, got {worker_id!r}"
            ) from None
        worker = self._workers.get(wid)
        if worker is None:
            raise KeyError(f"no worker with id {wid}")
        return worker

    def list_workers(self, status: Optional[str] = None) -> List[Worker]:
        if status is not None and status not in WORKER_STATUSES:
            raise ValueError(
                f"unknown worker status {status!r}; expected one of {WORKER_STATUSES}"
            )
        workers = sorted(self._workers.values(), key=lambda w: w.id)
        if status is not None:
            workers = [w for w in workers if w.status == status]
        return workers

    def set_worker_status(self, worker_id: int, status: str) -> Worker:
        if status not in WORKER_STATUSES:
            raise ValueError(
                f"unknown worker status {status!r}; expected one of {WORKER_STATUSES}"
            )
        worker = self.get_worker(worker_id)
        worker.status = status
        self._persist_workers()
        return worker

    def active_workers_for(self, category: str) -> List[Worker]:
        """Active workers whose categories cover ``category`` (case-insensitive)."""
        want = category.strip().casefold()
        return [
            w
            for w in self._workers.values()
            if w.status == "active" and any(c.casefold() == want for c in w.categories)
        ]

    # -- reporting --------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        counts = {s: 0 for s in STATUSES}
        for job in self._jobs.values():
            counts[job.status] += 1
        open_jobs = sum(counts[s] for s in OPEN_STATUSES)
        return {
            "jobs_total": len(self._jobs),
            "jobs_open": open_jobs,
            "jobs_by_status": counts,
            "workers_total": len(self._workers),
            "workers_active": sum(
                1 for w in self._workers.values() if w.status == "active"
            ),
        }

    def permissions_ok(self) -> bool:
        """True when state dir/files carry owner-only permissions (POSIX)."""
        if os.name != "posix":
            return True
        try:
            d = stat.S_IMODE(os.stat(self.jobs_path.parent).st_mode)
            jf = stat.S_IMODE(os.stat(self.jobs_path).st_mode)
            wf = stat.S_IMODE(os.stat(self.workers_path).st_mode)
        except OSError:
            return False
        return d == 0o700 and jf == 0o600 and wf == 0o600
