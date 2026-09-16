"""Hybrid Search & Apply job tracker — LEVI-native build.

The source repo carried only an *empty spreadsheet template* whose sheet
names sketched a job-application tracker (Review Buffer → Jobs →
Interviews → Prep, plus Restrictions). There was no code, data, or engine
to port — so this module **builds the implied system** from scratch:
a local-first pipeline tracker with JSON persistence, a CLI
(`levi jobs`), and registry skills.

Honest contract
---------------
* Local only: state lives in ``~/.levi/jobs.json``. No scraping, no job
  boards, no auto-applying — this tracks *your* search, it does not run
  it. Applications are always your action.
* Stages are a fixed pipeline: review_buffer → applied → interview →
  prep → offer, with rejected / withdrawn as terminal exits. Moves are
  validated; there is no silent stage invention.
* All example data in tests/docs is synthetic.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path.home() / ".levi" / "jobs.json"

STAGES = (
    "review_buffer",
    "applied",
    "interview",
    "prep",
    "offer",
    "rejected",
    "withdrawn",
)

TERMINAL_STAGES = ("offer", "rejected", "withdrawn")

MAX_TITLE_LEN = 200
MAX_COMPANY_LEN = 120
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
    company: str
    stage: str = "review_buffer"
    source: str = ""
    notes: List[JobNote] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.title = _check_str("title", self.title, MAX_TITLE_LEN)
        self.company = _check_str("company", self.company, MAX_COMPANY_LEN)
        self.source = _check_str("source", self.source, MAX_TITLE_LEN, allow_empty=True)
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage!r}; expected one of {STAGES}")

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
        return cls(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            company=str(data.get("company", "")),
            stage=str(data.get("stage", "review_buffer")),
            source=str(data.get("source", "")),
            notes=notes,
            created_at=str(data.get("created_at", "")) or _utcnow(),
            updated_at=str(data.get("updated_at", "")) or _utcnow(),
        )


class JobTracker:
    """Local-first job-application pipeline tracker (JSON persistence)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_PATH
        self._jobs: Dict[int, Job] = {}
        self._next_id = 1
        self._restrictions: List[str] = []
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupt or unreadable state: start empty rather than crash.
            return
        if not isinstance(data, dict):
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

    def _persist(self) -> None:
        payload = {
            "next_id": self._next_id,
            "jobs": [j.to_dict() for j in self._jobs.values()],
            "restrictions": self._restrictions,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    # -- jobs -----------------------------------------------------------

    def add(
        self,
        title: str,
        company: str,
        source: str = "",
        stage: str = "review_buffer",
    ) -> Job:
        """Add a job to the pipeline (starts in review_buffer by default)."""
        job = Job(
            id=self._next_id,
            title=title,
            company=company,
            stage=stage,
            source=source or "",
        )
        self._jobs[job.id] = job
        self._next_id += 1
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

    def list(self, stage: Optional[str] = None) -> List[Job]:
        if stage is not None and stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        jobs = sorted(self._jobs.values(), key=lambda j: j.id)
        if stage is not None:
            jobs = [j for j in jobs if j.stage == stage]
        return jobs

    def move(self, job_id: int, stage: str) -> Job:
        """Move a job to a new pipeline stage."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        job = self.get(job_id)
        job.stage = stage
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
    # Search constraints: e.g. "remote only", "no relocation", salary floor.

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
        counts = {stage: 0 for stage in STAGES}
        for job in self._jobs.values():
            counts[job.stage] += 1
        active = sum(counts[s] for s in STAGES if s not in TERMINAL_STAGES)
        return {
            "total": len(self._jobs),
            "active": active,
            "by_stage": counts,
            "restrictions": len(self._restrictions),
        }


# -- skills --------------------------------------------------------------
# Registered into SkillRegistry (category="productivity"). Lazy import of
# Skill/SkillRisk keeps this module importable without the registry.


def _skill_add(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        job = JobTracker().add(
            title=str(args.get("title", "")),
            company=str(args.get("company", "")),
            source=str(args.get("source", "") or ""),
        )
    except (ValueError, OSError) as exc:
        return f"jobs add failed: {exc}"
    return f"added job [{job.id}] {job.title} @ {job.company} → review_buffer"


def _skill_list(args: Dict[str, Any]) -> str:
    args = args or {}
    stage = args.get("stage")
    try:
        jobs = JobTracker().list(stage=str(stage) if stage else None)
    except (ValueError, OSError) as exc:
        return f"jobs list failed: {exc}"
    if not jobs:
        return "no jobs tracked" + (f" in stage {stage}" if stage else "")
    return "\n".join(f"[{j.id}] {j.title} @ {j.company} — {j.stage}" for j in jobs)


def _skill_move(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        job = JobTracker().move(args.get("id"), str(args.get("stage", "")))
    except (ValueError, KeyError, OSError) as exc:
        return f"jobs move failed: {exc}"
    return f"moved job [{job.id}] {job.title} → {job.stage}"


def _build_job_skills() -> List[Any]:
    from levi.skill.registry import Skill, SkillRisk

    return [
        Skill(
            id="jobs_add",
            name="Jobs Add",
            description=(
                "Add a job to the local search pipeline (starts in "
                "review_buffer). Tracking only — never applies anywhere."
            ),
            category="productivity",
            risk_level=SkillRisk.INFO,
            handler=_skill_add,
            tags=["jobs", "productivity", "tracker"],
            version="1.0.0",
        ),
        Skill(
            id="jobs_list",
            name="Jobs List",
            description="List tracked jobs, optionally filtered by pipeline stage.",
            category="productivity",
            risk_level=SkillRisk.INFO,
            handler=_skill_list,
            tags=["jobs", "productivity", "tracker"],
            version="1.0.0",
        ),
        Skill(
            id="jobs_move",
            name="Jobs Move",
            description="Move a tracked job to a new pipeline stage.",
            category="productivity",
            risk_level=SkillRisk.LOW,
            handler=_skill_move,
            tags=["jobs", "productivity", "tracker"],
            version="1.0.0",
        ),
    ]


JOB_SKILLS: List[Any] = _build_job_skills()
