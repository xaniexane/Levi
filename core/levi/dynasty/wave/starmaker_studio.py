# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Starmaker Studio — the creator suite's render bench and learning player.

Media job queue (avatar / photo / video), a video learning player with
chaptered progress, and sealed render receipts. HONEST LABEL: the render
backend is SIMULATED — no GPU, no model, no pixels. ``render_next()``
advances a queued job by minting a deterministic procedural descriptor
from the spec digest and sealing a receipt. The simulation is declared
in the code, in the docstrings, and in every receipt; it is never
presented as a real render.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["JOB_KINDS", "JobError", "StarmakerStudio"]

JOB_KINDS = ("avatar", "photo", "video")

# The one and only render backend: procedural, deterministic, honest.
_SIM_BACKEND = "simulated-cpu"

_STATUS_QUEUED = "queued"
_STATUS_RENDERING = "rendering"
_STATUS_DONE = "done"
_STATUS_FAILED = "failed"

_MAX_USER_LEN = 64
_MAX_VIDEO_ID_LEN = 128


class JobError(AgentError):
    """Bad input or bad state in the studio's job queue."""


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _spec_sha256(spec: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _check_kind(kind: Any) -> str:
    if not isinstance(kind, str) or kind not in JOB_KINDS:
        raise JobError(f"unknown job kind {kind!r}: want one of {list(JOB_KINDS)}")
    return kind


def _check_spec(spec: Any) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        raise JobError(f"job spec must be a dict, got {type(spec).__name__}")
    try:
        json.dumps(spec, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise JobError(f"job spec is not JSON-serializable: {exc}") from exc
    return spec


def _check_name(value: Any, what: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"{what} must be a non-empty string")
    clean = value.strip()
    if len(clean) > limit:
        raise AgentError(f"{what} too long (>{limit} chars)")
    if any(ord(c) < 32 for c in clean):
        raise AgentError(f"{what} carries control characters")
    return scrub_text(clean)


def _check_chapters(chapters: Any) -> List[Dict[str, Any]]:
    if not isinstance(chapters, list) or not chapters:
        raise AgentError("chapters must be a non-empty list")
    if len(chapters) > 1024:
        raise AgentError("too many chapters (>1024)")
    clean: List[Dict[str, Any]] = []
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            raise AgentError(f"chapter {i} must be a dict")
        title = ch.get("title")
        seconds = ch.get("seconds")
        if not isinstance(title, str) or not title.strip():
            raise AgentError(f"chapter {i} needs a non-empty title")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise AgentError(f"chapter {i} seconds must be a number")
        if not math.isfinite(seconds) or seconds <= 0:
            raise AgentError(f"chapter {i} seconds must be positive")
        clean.append({"title": scrub_text(title.strip()), "seconds": seconds})
    return clean


class StarmakerStudio(DynastyAgent):
    """The studio bench: queued renders, chaptered learning player, receipts."""

    agent_id = "starmaker-studio"
    display_name = "Starmaker Studio"
    owns = "creator suite tooling"
    first_milestone = "media job queue + learning player + render receipts"
    proficiency = {"media": 10, "creator": 9, "general": 6}
    specialties = [
        "media job queue (simulated renders)",
        "video learning player with chapters",
        "render receipts",
    ]
    attributes = [
        {
            "name": "honest-simulation",
            "assertion": (
                "renders are simulated procedurally and every descriptor, "
                "receipt, and docstring says so — a simulated render is "
                "never presented as a real one"
            ),
        },
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._lock = threading.RLock()
        self._home = home or _home()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self._videos: Dict[str, Dict[str, Any]] = {}
        self._watch: Dict[str, Dict[str, float]] = {}

    # -- home resolution ------------------------------------------------
    def _renders_path(self) -> Path:
        return self._home / "dynasty" / "starmaker" / "renders.jsonl"

    def _write_receipt(self, record: Dict[str, Any]) -> None:
        path = self._renders_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True) + "\n"
        new_file = not path.exists()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
        if new_file:
            os.chmod(path, 0o600)

    # -- media job queue -----------------------------------------------
    def submit(self, kind: str, spec: Dict[str, Any]) -> str:
        """Queue a media job. Returns the job id. Unknown kind -> JobError."""
        kind = _check_kind(kind)
        spec = _check_spec(spec)
        with self._lock:
            self._seq += 1
            digest = _spec_sha256(spec)
            stamp = _now_iso()
            job_id = hashlib.sha256(
                f"studio|{kind}|{digest}|{self._seq}|{stamp}".encode("utf-8")
            ).hexdigest()[:16]
            self._jobs[job_id] = {
                "job_id": job_id,
                "kind": kind,
                "spec_sha256": digest,
                "status": _STATUS_QUEUED,
                "created_at": stamp,
                "reason": None,
            }
            self.note(f"queued {kind} job {job_id[:8]}")
            return job_id

    def job_status(self, job_id: str) -> Dict[str, Any]:
        """Snapshot of a job. Unknown id -> JobError."""
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobError(f"unknown job id {job_id!r}")
        return dict(job)

    def fail_job(self, job_id: str, reason: str) -> Dict[str, Any]:
        """Mark a queued or rendering job failed, with a recorded reason."""
        reason = scrub_text(str(reason or "")).strip()
        if not reason:
            raise JobError("fail_job needs a reason")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobError(f"unknown job id {job_id!r}")
            if job["status"] in (_STATUS_DONE, _STATUS_FAILED):
                raise JobError(f"job {job_id!r} already {job['status']}")
            job["status"] = _STATUS_FAILED
            job["reason"] = reason
            job["failed_at"] = _now_iso()
            self.note(f"job {job_id[:8]} failed: {reason[:60]}")
            return dict(job)

    def render_next(self) -> Optional[Dict[str, Any]]:
        """Advance the oldest queued job through the SIMULATED backend.

        Lifecycle: queued -> rendering -> done. Returns the finished job
        dict, or None when the queue is empty. The "render" is a
        deterministic procedural descriptor — no GPU, no model, no
        pixels — and is labeled as simulated everywhere.
        """
        with self._lock:
            job = next(
                (j for j in self._jobs.values() if j["status"] == _STATUS_QUEUED),
                None,
            )
            if job is None:
                return None
            job["status"] = _STATUS_RENDERING
            digest = job["spec_sha256"]
            # Simulated render: derive a procedural descriptor from the
            # spec digest. Honest label, nothing hidden.
            output = {
                "backend": _SIM_BACKEND,
                "descriptor": "simulated-render",
                "seed_digest": digest[:32],
                "note": (
                    "procedural descriptor only — no render engine; "
                    "this job was SIMULATED, not rendered"
                ),
            }
            completed_at = _now_iso()
            job["status"] = _STATUS_DONE
            job["output"] = output
            job["completed_at"] = completed_at
            receipt = {
                "job_id": job["job_id"],
                "kind": job["kind"],
                "spec_sha256": digest,
                "completed_at": completed_at,
                "backend": _SIM_BACKEND,
            }
            self._write_receipt(receipt)
            self.note(f"rendered (simulated) {job['kind']} job {job['job_id'][:8]}")
            return dict(job)

    def list_renders(self) -> List[Dict[str, Any]]:
        """Read back the sealed render receipts."""
        path = self._renders_path()
        if not path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if isinstance(record, dict):
                    records.append(record)
        return records

    # -- video learning player ------------------------------------------
    def add_chapters(
        self, video_id: str, chapters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Register chapter markers for a video. Returns the video record."""
        video_id = _check_name(video_id, "video_id", _MAX_VIDEO_ID_LEN)
        clean = _check_chapters(chapters)
        total = sum(c["seconds"] for c in clean)
        with self._lock:
            self._videos[video_id] = {
                "video_id": video_id,
                "chapters": clean,
                "total_seconds": total,
            }
            self.note(f"chapters set for {video_id}: {len(clean)} chapters")
            return dict(self._videos[video_id])

    def _video(self, video_id: str) -> Dict[str, Any]:
        video = self._videos.get(video_id)
        if video is None:
            raise AgentError(f"unknown video {video_id!r}")
        return video

    def _watched(self, user: str, video_id: str) -> float:
        return self._watch.get(user, {}).get(video_id, 0.0)

    @staticmethod
    def _current_chapter(video: Dict[str, Any], watched: float) -> str:
        chapters = video["chapters"]
        cumulative = 0.0
        for ch in chapters:
            cumulative += ch["seconds"]
            if watched < cumulative:
                return ch["title"]
        return chapters[-1]["title"]

    def watch(self, user: str, video_id: str, seconds: float) -> Dict[str, Any]:
        """Accumulate watch time, clamped to the video's total length."""
        user = _check_name(user, "user", _MAX_USER_LEN)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise AgentError("seconds must be a number")
        if not math.isfinite(seconds) or seconds < 0:
            raise AgentError("seconds must be a non-negative number")
        with self._lock:
            video = self._video(video_id)
            watched = min(
                self._watched(user, video_id) + seconds, video["total_seconds"]
            )
            self._watch.setdefault(user, {})[video_id] = watched
            self.note(f"{user} watched {video_id} +{seconds}s")
            return self.progress(user, video_id)

    def progress(self, user: str, video_id: str) -> Dict[str, Any]:
        """Progress snapshot: watched seconds, percent, current chapter."""
        user = _check_name(user, "user", _MAX_USER_LEN)
        with self._lock:
            video = self._video(video_id)
            watched = self._watched(user, video_id)
            total = video["total_seconds"]
            percent = round((watched / total) * 100, 2) if total else 0.0
            return {
                "user": user,
                "video_id": video_id,
                "watched_seconds": watched,
                "total_seconds": total,
                "percent": percent,
                "current_chapter": self._current_chapter(video, watched),
            }

    def resume_position(self, user: str, video_id: str) -> Dict[str, Any]:
        """Where to resume: watched position, chapter, and what remains."""
        user = _check_name(user, "user", _MAX_USER_LEN)
        with self._lock:
            video = self._video(video_id)
            watched = self._watched(user, video_id)
            return {
                "user": user,
                "video_id": video_id,
                "watched_seconds": watched,
                "current_chapter": self._current_chapter(video, watched),
                "remaining_seconds": video["total_seconds"] - watched,
            }

    # -- domain dispatch -------------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "submit_job":
            return {"job_id": self.submit(task.get("kind", ""), task.get("spec", {}))}
        if shape == "render_next":
            return {"job": self.render_next()}
        if shape == "fail_job":
            return self.fail_job(
                str(task.get("job_id", "")), str(task.get("reason", ""))
            )
        if shape == "job_status":
            return self.job_status(str(task.get("job_id", "")))
        if shape == "add_chapters":
            return self.add_chapters(
                str(task.get("video_id", "")), task.get("chapters", [])
            )
        if shape == "watch":
            return self.watch(
                str(task.get("user", "")),
                str(task.get("video_id", "")),
                task.get("seconds", 0),
            )
        if shape == "progress":
            return self.progress(
                str(task.get("user", "")), str(task.get("video_id", ""))
            )
        if shape == "resume":
            return self.resume_position(
                str(task.get("user", "")), str(task.get("video_id", ""))
            )
        if shape == "renders":
            return {"renders": self.list_renders()}
        return super().handle(task)

    # -- first green task -------------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        job_id = self.submit("avatar", {"seed": "studio-first", "style": "mvp"})
        job = self.render_next()
        return self.do_task(
            "wave.first_task",
            {
                "job_id": job_id,
                "job": job,
                "renders": len(self.list_renders()),
                "simulated": True,
                "milestone": self.first_milestone,
            },
            task="starmaker-studio:first",
        )
