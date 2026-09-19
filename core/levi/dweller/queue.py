"""Dweller queue — persistent, journaled job storage.

Jobs live under ``~/.levi/dweller/`` (overridable with ``LEVI_HOME``,
the same convention the rest of LEVI uses). Each job is one JSON file
under ``jobs/``; every state change appends a line to ``journal.jsonl``
so the full history of a job survives a crash and can be audited.

Writes are atomic (temp file + rename). stdlib only.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .jobs import Job


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def dweller_home() -> Path:
    """The Dweller's root: ``$LEVI_HOME/.levi/dweller`` or
    ``~/.levi/dweller``."""
    base = os.environ.get("LEVI_HOME") or str(Path.home())
    return Path(base) / ".levi" / "dweller"


def _jobs_dir(home: Optional[Path] = None) -> Path:
    d = (home or dweller_home()) / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _journal_path(home: Optional[Path] = None) -> Path:
    h = home or dweller_home()
    h.mkdir(parents=True, exist_ok=True)
    return h / "journal.jsonl"


def _receipts_dir(home: Optional[Path] = None) -> Path:
    d = (home or dweller_home()) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _journal(
    home: Optional[Path], event: str, job: Job, extra: Optional[Dict[str, Any]] = None
) -> None:
    entry = {
        "ts": _utcnow(),
        "event": event,
        "job_id": job.id,
        "kind": job.kind,
        "state": job.state,
    }
    if extra:
        entry.update(extra)
    with open(_journal_path(home), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def enqueue(job: Job, home: Optional[Path] = None) -> Job:
    """Persist a new queued job. Raises if the id already exists."""
    target = _jobs_dir(home) / (job.id + ".json")
    if target.exists():
        raise ValueError("job already queued: %s" % job.id)
    save_job(job, home=home, event="enqueued")
    return job


def save_job(job: Job, home: Optional[Path] = None, event: str = "updated") -> Job:
    """Persist a job and journal the state change."""
    _atomic_write(
        _jobs_dir(home) / (job.id + ".json"),
        json.dumps(job.to_dict(), indent=2, sort_keys=True),
    )
    _journal(home, event, job)
    return job


def get_job(job_id: str, home: Optional[Path] = None) -> Job:
    """Load a job by id; raises ``KeyError`` when unknown."""
    path = _jobs_dir(home) / (job_id + ".json")
    if not path.exists():
        raise KeyError("no such job: %s" % job_id)
    return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_jobs(home: Optional[Path] = None) -> List[Job]:
    """All jobs, oldest first."""
    jobs = []
    for path in sorted(_jobs_dir(home).glob("*.json")):
        try:
            jobs.append(Job.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue  # a corrupt file never sinks the listing
    return jobs


def save_receipt(
    job_id: str, receipt: Dict[str, Any], home: Optional[Path] = None
) -> Path:
    """Persist a job's final receipt. Every job gets one, even failures."""
    path = _receipts_dir(home) / (job_id + ".json")
    _atomic_write(path, json.dumps(receipt, indent=2, sort_keys=True))
    return path


def load_receipt(job_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Load a job's receipt; raises ``KeyError`` when none exists."""
    path = _receipts_dir(home) / (job_id + ".json")
    if not path.exists():
        raise KeyError("no receipt for job: %s" % job_id)
    return json.loads(path.read_text(encoding="utf-8"))


def journal_tail(n: int = 50, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Last n journal entries (for audit/debug)."""
    path = _journal_path(home)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
