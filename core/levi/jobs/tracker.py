"""LEVI jobs tracker — local-first opportunity / deal pipeline.

Tracks items LEVI is working: demand-pipeline opportunities, manual
leads, anything with a lifecycle. Local only: state lives under
``~/.levi/jobs/`` with owner-only permissions (dir 0700, file 0600).
No scraping, no job boards, no auto-applying — this tracks *your*
pipeline, it does not run it.

Status pipeline
---------------
``new`` → ``active`` → ``won`` / ``lost`` / ``dropped``. Moves are
validated against an explicit transition map; there is no silent
invention of states. Terminal states (``won``/``lost``/``dropped``)
can be reopened back to ``active`` or ``new`` — nothing is ever
deleted by a move.

Migration note: an earlier revision of this module used a
job-application pipeline (``review_buffer`` → ``applied`` →
``interview`` → ``prep`` → ``offer`` / ``rejected`` / ``withdrawn``).
Legacy records and the old single-file store (``~/.levi/jobs.json``)
are migrated automatically on load: old stages map onto the new
pipeline (``review_buffer``/``applied`` → ``new``,
``interview``/``prep`` → ``active``, ``offer`` → ``won``,
``rejected`` → ``lost``, ``withdrawn`` → ``dropped``).

Honest contract
---------------
* All demand-sourced imports are labeled HYPOTHESIS in their notes
  until verified — the tracker never invents market data.
* ``upsert`` is idempotent: re-importing the same demand scan does not
  duplicate jobs; it refreshes ``updated_at`` and appends only new
  evidence notes.
* All example data in tests/docs is synthetic.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.demand.pulse import DemandPulse

LEGACY_PATH = Path.home() / ".levi" / "jobs.json"


def default_jobs_dir() -> Path:
    """Default state directory (overridable in tests via monkeypatch)."""
    return Path.home() / ".levi" / "jobs"


def default_path() -> Path:
    return default_jobs_dir() / "jobs.json"


DEFAULT_PATH = default_path()

STATUSES = ("new", "active", "won", "lost", "dropped")

TERMINAL_STATUSES = ("won", "lost", "dropped")

# Explicit transition map: current status -> allowed next statuses.
TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "new": ("active", "dropped"),
    "active": ("new", "won", "lost", "dropped"),
    "won": ("active", "new"),
    "lost": ("active", "new"),
    "dropped": ("active", "new"),
}

# Legacy job-application pipeline -> current pipeline (load-time migration).
_LEGACY_STAGE_MAP = {
    "review_buffer": "new",
    "applied": "new",
    "interview": "active",
    "prep": "active",
    "offer": "won",
    "rejected": "lost",
    "withdrawn": "dropped",
}

MAX_TITLE_LEN = 200
MAX_COMPANY_LEN = 120
MAX_SOURCE_LEN = 120
MAX_NOTE_LEN = 2000


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


@dataclass
class JobNote:
    ts: str
    text: str

    def to_dict(self) -> Dict[str, str]:
        return {"ts": self.ts, "text": self.text}


@dataclass
class Job:
    id: int
    title: str
    status: str = "new"
    source: str = "manual"
    company: str = ""
    notes: List[JobNote] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.title = _check_str("title", self.title, MAX_TITLE_LEN)
        self.company = _check_str(
            "company", self.company, MAX_COMPANY_LEN, allow_empty=True
        )
        self.source = _check_str(
            "source", self.source, MAX_SOURCE_LEN, allow_empty=True
        )
        if not self.source:
            self.source = "manual"
        self.status = _check_status(self.status)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["notes"] = [n.to_dict() if isinstance(n, JobNote) else n for n in self.notes]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        notes = [
            JobNote(ts=n.get("ts", ""), text=n.get("text", ""))
            for n in (data.get("notes") or [])
            if isinstance(n, dict)
        ]
        # Accept the legacy field name ("stage") and legacy stage values.
        status = data.get("status", data.get("stage", "new"))
        if isinstance(status, str) and status in _LEGACY_STAGE_MAP:
            status = _LEGACY_STAGE_MAP[status]
        return cls(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            status=str(status or "new"),
            source=str(data.get("source", "") or "manual"),
            company=str(data.get("company", "")),
            notes=notes,
            created_at=str(data.get("created_at", "")) or _utcnow(),
            updated_at=str(data.get("updated_at", "")) or _utcnow(),
        )


class JobTracker:
    """Local-first opportunity pipeline tracker (JSON persistence)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self._jobs: Dict[int, Job] = {}
        self._next_id = 1
        self._restrictions: List[str] = []
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        data = self._read_store(self.path)
        if data is None and self.path == default_path() and LEGACY_PATH.exists():
            # One-time migration from the old single-file store.
            data = self._read_store(LEGACY_PATH)
        if data is None:
            return
        self._next_id = int(data.get("next_id", 1) or 1)
        for item in data.get("jobs", []) or []:
            try:
                job = Job.from_dict(item)
            except (ValueError, KeyError, TypeError):
                continue
            self._jobs[job.id] = job
        self._restrictions = [
            str(r) for r in (data.get("restrictions") or []) if str(r).strip()
        ]

    @staticmethod
    def _read_store(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            # Corrupt or unreadable state: start empty rather than crash.
            return None
        return data if isinstance(data, dict) else None

    def _tighten_permissions(self) -> None:
        """Best-effort owner-only permissions (POSIX; no-op where unsupported)."""
        try:
            os.chmod(self.path.parent, 0o700)
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _persist(self) -> None:
        payload = {
            "version": 2,
            "next_id": self._next_id,
            "jobs": [j.to_dict() for j in self._jobs.values()],
            "restrictions": self._restrictions,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".jobs.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._tighten_permissions()

    # -- jobs -----------------------------------------------------------

    def add(
        self,
        title: str,
        status: str = "new",
        source: str = "manual",
        company: str = "",
    ) -> Job:
        """Add a job to the pipeline (starts in ``new`` by default)."""
        job = Job(
            id=self._next_id,
            title=title,
            status=status,
            source=source or "manual",
            company=company or "",
        )
        self._jobs[job.id] = job
        self._next_id += 1
        self._persist()
        return job

    @staticmethod
    def _identity_key(title: str, company: str, source: str) -> Tuple[str, str, str]:
        return (
            title.strip().casefold(),
            company.strip().casefold(),
            source.strip().casefold() or "manual",
        )

    def find(
        self, title: str, company: str = "", source: str = "manual"
    ) -> Optional[Job]:
        """Find a job by its idempotency key (title/company/source)."""
        key = self._identity_key(title, company, source)
        for job in self._jobs.values():
            if self._identity_key(job.title, job.company, job.source) == key:
                return job
        return None

    def upsert(
        self,
        title: str,
        company: str = "",
        source: str = "manual",
        note: Optional[str] = None,
    ) -> Tuple[Job, bool]:
        """Idempotent add-or-refresh.

        If a job with the same (title, company, source) already exists,
        refresh its ``updated_at`` (and append ``note`` when it adds new
        evidence) instead of duplicating it. Returns ``(job, created)``.
        """
        existing = self.find(title, company, source)
        if existing is None:
            job = self.add(title=title, company=company, source=source)
            if note:
                self.note(job.id, note)
                job = self.get(job.id)
            return job, True
        if note:
            text = _check_str("note", note, MAX_NOTE_LEN)
            if text not in {n.text for n in existing.notes}:
                existing.notes.append(JobNote(ts=_utcnow(), text=text))
        existing.updated_at = _utcnow()
        self._persist()
        return existing, False

    def update(
        self,
        job_id: int,
        title: Optional[str] = None,
        company: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Job:
        """Update job fields; status changes go through transition validation."""
        job = self.get(job_id)
        if title is not None:
            job.title = _check_str("title", title, MAX_TITLE_LEN)
        if company is not None:
            job.company = _check_str(
                "company", company, MAX_COMPANY_LEN, allow_empty=True
            )
        if source is not None:
            job.source = (
                _check_str("source", source, MAX_SOURCE_LEN, allow_empty=True)
                or "manual"
            )
        if status is not None:
            self._check_transition(job.status, status)
            job.status = status
        job.updated_at = _utcnow()
        self._persist()
        return job

    def get(self, job_id: int) -> Job:
        try:
            jid = int(job_id)
        except (TypeError, ValueError):
            raise ValueError(f"job id must be an integer, got {job_id!r}") from None
        job = self._jobs.get(jid)
        if job is None:
            raise KeyError(f"no job with id {jid}")
        return job

    def list(self, status: Optional[str] = None) -> List[Job]:
        if status is not None:
            _check_status(status)
        jobs = sorted(self._jobs.values(), key=lambda j: j.id)
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
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

    def move(self, job_id: int, status: str) -> Job:
        """Move a job to a new pipeline status (validated)."""
        job = self.get(job_id)
        self._check_transition(job.status, status)
        job.status = status
        job.updated_at = _utcnow()
        self._persist()
        return job

    def note(self, job_id: int, text: str) -> JobNote:
        """Append a timestamped note to a job."""
        text = _check_str("note", text, MAX_NOTE_LEN)
        job = self.get(job_id)
        note = JobNote(ts=_utcnow(), text=text)
        job.notes.append(note)
        job.updated_at = _utcnow()
        self._persist()
        return note

    # -- restrictions ---------------------------------------------------
    # Pipeline constraints: e.g. "local-first only", "no paid APIs".

    def restrictions(self) -> List[str]:
        return list(self._restrictions)

    def add_restriction(self, text: str) -> List[str]:
        text = _check_str("restriction", text, MAX_TITLE_LEN)
        if text not in self._restrictions:
            self._restrictions.append(text)
            self._persist()
        return self.restrictions()

    def remove_restriction(self, text: str) -> List[str]:
        text = _check_str("restriction", text, MAX_TITLE_LEN)
        if text in self._restrictions:
            self._restrictions.remove(text)
            self._persist()
        return self.restrictions()

    # -- reporting ------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        counts = {status: 0 for status in STATUSES}
        for job in self._jobs.values():
            counts[job.status] += 1
        active = sum(counts[s] for s in STATUSES if s not in TERMINAL_STATUSES)
        return {
            "total": len(self._jobs),
            "active": active,
            "by_status": counts,
            "restrictions": len(self._restrictions),
        }

    def permissions_ok(self) -> bool:
        """True when the state dir/file carry owner-only permissions (POSIX)."""
        if os.name != "posix":
            return True
        try:
            d = stat.S_IMODE(os.stat(self.path.parent).st_mode)
            f = stat.S_IMODE(os.stat(self.path).st_mode)
        except OSError:
            return False
        return d == 0o700 and f == 0o600


# -- demand import -------------------------------------------------------
# The demand pipeline (levi.demand) is read, never modified: opportunities
# and five-factor score cards are upserted as tracked jobs with
# source="demand-pipeline". Idempotent — re-imports refresh, not duplicate.


def import_demand(
    tracker: JobTracker,
    demand_path: Optional[Path] = None,
    min_worth: float = 0.0,
    min_score: float = 0.0,
    limit: int = 0,
    dry_run: bool = False,
    _pulse_factory: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Import DemandPulse opportunities/score cards as tracked jobs."""
    if not 0.0 <= float(min_worth) <= 1.0:
        raise ValueError(f"min_worth must be in [0, 1], got {min_worth!r}")
    if not 0.0 <= float(min_score) <= 100.0:
        raise ValueError(f"min_score must be in [0, 100], got {min_score!r}")

    if _pulse_factory is not None:
        pulse = _pulse_factory(demand_path)
    elif demand_path is not None:
        pulse = DemandPulse(path=demand_path)
    else:
        pulse = DemandPulse()

    created = 0
    refreshed = 0
    skipped = 0
    imported: List[Dict[str, Any]] = []

    def _record(title: str, note: str) -> None:
        nonlocal created, refreshed
        if dry_run:
            imported.append({"title": title, "note": note})
            return
        _, was_created = tracker.upsert(
            title=title, company="", source="demand-pipeline", note=note
        )
        if was_created:
            created += 1
        else:
            refreshed += 1
        imported.append({"title": title, "note": note})

    for opp in sorted(pulse.opportunities, key=lambda o: -o.worth):
        if opp.worth < min_worth:
            skipped += 1
            continue
        note = (
            f"demand-pipeline opportunity (HYPOTHESIS): worth={opp.worth:.2f} "
            f"demand_id={opp.demand_id} demand={opp.demand_score:.2f} "
            f"serviceability={opp.serviceability:.2f} cost={opp.startup_cost:.2f}"
            + (f" | {opp.notes}" if opp.notes else "")
        )
        _record(opp.title, note)
        if limit and len(imported) >= limit:
            break

    for card in sorted(pulse.score_cards, key=lambda c: -c.composite):
        if card.composite < min_score:
            skipped += 1
            continue
        factors = "; ".join(
            f"{f.name}={f.value:.0f} ({f.basis[:60]})" for f in card.factors
        )
        note = (
            f"demand-pipeline five-factor card (HYPOTHESIS): "
            f"composite={card.composite:.1f} tier={card.tier} "
            f"alert={card.alert} | {factors}"
            + (f" | {card.notes}" if card.notes else "")
        )
        _record(card.title, note)
        if limit and len(imported) >= limit:
            break

    return {
        "created": created,
        "refreshed": refreshed,
        "skipped": skipped,
        "imported": imported,
        "dry_run": dry_run,
    }


# -- skills --------------------------------------------------------------
# Registered into SkillRegistry (category="productivity"). Lazy import of
# Skill/SkillRisk keeps this module importable without the registry.


def _skill_add(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        job = JobTracker().add(
            title=str(args.get("title", "")),
            company=str(args.get("company", "") or ""),
            source=str(args.get("source", "") or "manual"),
            status=str(args.get("status", "") or "new"),
        )
    except (ValueError, OSError) as exc:
        return f"jobs add failed: {exc}"
    return f"added job [{job.id}] {job.title} → {job.status}"


def _skill_list(args: Dict[str, Any]) -> str:
    args = args or {}
    status = args.get("status")
    try:
        jobs = JobTracker().list(status=str(status) if status else None)
    except (ValueError, OSError) as exc:
        return f"jobs list failed: {exc}"
    if not jobs:
        return "no jobs tracked" + (f" with status {status}" if status else "")
    return "\n".join(
        f"[{j.id}] {j.title} — {j.status} (source: {j.source})" for j in jobs
    )


def _skill_move(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        job = JobTracker().move(args.get("id"), str(args.get("status", "")))
    except (ValueError, KeyError, OSError) as exc:
        return f"jobs move failed: {exc}"
    return f"moved job [{job.id}] {job.title} → {job.status}"


def _build_job_skills() -> List[Any]:
    from levi.skill.registry import Skill, SkillRisk

    return [
        Skill(
            id="jobs_add",
            name="Jobs Add",
            description=(
                "Add a job to the local pipeline (starts at status 'new'). "
                "Tracking only — never acts on anything."
            ),
            category="productivity",
            risk_level=SkillRisk.INFO,
            handler=_skill_add,
            tags=["jobs", "productivity", "tracker"],
            version="2.0.0",
        ),
        Skill(
            id="jobs_list",
            name="Jobs List",
            description="List tracked jobs, optionally filtered by pipeline status.",
            category="productivity",
            risk_level=SkillRisk.INFO,
            handler=_skill_list,
            tags=["jobs", "productivity", "tracker"],
            version="2.0.0",
        ),
        Skill(
            id="jobs_move",
            name="Jobs Move",
            description=(
                "Move a tracked job along the pipeline "
                "(new → active → won/lost/dropped). Invalid transitions rejected."
            ),
            category="productivity",
            risk_level=SkillRisk.LOW,
            handler=_skill_move,
            tags=["jobs", "productivity", "tracker"],
            version="2.0.0",
        ),
    ]


JOB_SKILLS: List[Any] = _build_job_skills()
