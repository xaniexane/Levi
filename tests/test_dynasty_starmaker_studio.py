# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Dynasty wave tests — Starmaker Studio.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from levi.dynasty.dna import AgentError, assert_clean
from levi.dynasty.wave.starmaker_studio import (
    JOB_KINDS,
    JobError,
    StarmakerStudio,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def _studio(tmp_home):
    agent = StarmakerStudio()
    agent.enroll()
    return agent


def _renders_path(tmp_home: Path) -> Path:
    return tmp_home / "dynasty" / "starmaker" / "renders.jsonl"


# -- job queue ---------------------------------------------------------
def test_submit_and_status(tmp_home):
    studio = _studio(tmp_home)
    job_id = studio.submit("avatar", {"seed": "x1", "style": "mvp"})
    status = studio.job_status(job_id)
    assert status["status"] == "queued"
    assert status["kind"] == "avatar"
    assert len(job_id) == 16


def test_submit_each_kind(tmp_home):
    studio = _studio(tmp_home)
    assert set(JOB_KINDS) == {"avatar", "photo", "video"}
    for kind in JOB_KINDS:
        assert studio.job_status(studio.submit(kind, {}))["kind"] == kind


def test_submit_unknown_kind_raises(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(JobError):
        studio.submit("hologram", {})
    with pytest.raises(JobError):
        studio.submit("", {})
    with pytest.raises(JobError):
        studio.submit(None, {})


def test_submit_bad_spec_raises(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(JobError):
        studio.submit("photo", ["not", "a", "dict"])
    with pytest.raises(JobError):
        studio.submit("photo", {"cb": lambda: 1})  # not JSON-serializable


def test_job_status_unknown_id_raises(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(JobError):
        studio.job_status("deadbeefdeadbeef")


def test_render_next_empty_queue_returns_none(tmp_home):
    studio = _studio(tmp_home)
    assert studio.render_next() is None


def test_render_next_lifecycle_and_receipt(tmp_home):
    studio = _studio(tmp_home)
    first = studio.submit("video", {"seconds": 12, "topic": "intro"})
    second = studio.submit("photo", {"prompt": "sunset"})
    job = studio.render_next()
    assert job["job_id"] == first  # FIFO
    assert job["status"] == "done"
    assert "simulated" in job["output"]["note"].lower()
    assert studio.job_status(first)["status"] == "done"
    assert studio.job_status(second)["status"] == "queued"

    records = studio.list_renders()
    assert len(records) == 1
    rec = records[0]
    assert rec["job_id"] == first
    assert rec["kind"] == "video"
    assert "completed_at" in rec
    expected_sha = hashlib.sha256(
        json.dumps(
            {"seconds": 12, "topic": "intro"}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert rec["spec_sha256"] == expected_sha

    # receipt file actually landed on disk under tmp LEVI_HOME
    on_disk = _renders_path(tmp_home).read_text(encoding="utf-8").strip().splitlines()
    assert len(on_disk) == 1
    assert json.loads(on_disk[0])["job_id"] == first


def test_list_renders_empty_when_no_renders(tmp_home):
    studio = _studio(tmp_home)
    assert studio.list_renders() == []


def test_fail_job(tmp_home):
    studio = _studio(tmp_home)
    job_id = studio.submit("avatar", {"seed": "doomed"})
    failed = studio.fail_job(job_id, "spec rejected by policy")
    assert failed["status"] == "failed"
    assert failed["reason"] == "spec rejected by policy"
    assert studio.job_status(job_id)["status"] == "failed"


def test_fail_job_unknown_id_raises(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(JobError):
        studio.fail_job("nope" * 4, "reason")


def test_fail_job_no_reason_raises(tmp_home):
    studio = _studio(tmp_home)
    job_id = studio.submit("avatar", {})
    with pytest.raises(JobError):
        studio.fail_job(job_id, "")


def test_fail_job_terminal_state_raises(tmp_home):
    studio = _studio(tmp_home)
    job_id = studio.submit("avatar", {})
    studio.render_next()
    with pytest.raises(JobError):
        studio.fail_job(job_id, "too late")


# -- learning player ---------------------------------------------------
def _chapters():
    return [
        {"title": "cold open", "seconds": 30},
        {"title": "the build", "seconds": 90},
        {"title": "outro", "seconds": 30},
    ]


def test_add_chapters(tmp_home):
    studio = _studio(tmp_home)
    record = studio.add_chapters("vid-1", _chapters())
    assert record["total_seconds"] == 150
    assert len(record["chapters"]) == 3


def test_add_chapters_bad_input(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", [])
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", [{"title": "x", "seconds": 0}])
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", [{"title": "x", "seconds": -5}])
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", [{"title": "", "seconds": 10}])
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", [{"title": "x"}])
    with pytest.raises(AgentError):
        studio.add_chapters("vid-1", "not-a-list")


def test_watch_accumulates_and_reports_progress(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    studio.watch("amy", "vid-1", 20)
    studio.watch("amy", "vid-1", 25)
    prog = studio.progress("amy", "vid-1")
    assert prog["watched_seconds"] == 45
    assert prog["percent"] == pytest.approx(30.0)
    assert prog["current_chapter"] == "the build"


def test_watch_clamps_to_total(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    prog = studio.watch("amy", "vid-1", 10_000)  # way past the end
    assert prog["watched_seconds"] == 150
    assert prog["percent"] == 100.0
    assert prog["current_chapter"] == "outro"


def test_watch_negative_raises(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    with pytest.raises(AgentError):
        studio.watch("amy", "vid-1", -1)


def test_watch_unknown_video_raises(tmp_home):
    studio = _studio(tmp_home)
    with pytest.raises(AgentError):
        studio.watch("amy", "nope", 5)


def test_resume_position(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    studio.watch("amy", "vid-1", 40)
    resume = studio.resume_position("amy", "vid-1")
    assert resume["watched_seconds"] == 40
    assert resume["current_chapter"] == "the build"
    assert resume["remaining_seconds"] == 110


def test_progress_fresh_user_starts_at_zero(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    prog = studio.progress("new-user", "vid-1")
    assert prog["watched_seconds"] == 0
    assert prog["percent"] == 0.0
    assert prog["current_chapter"] == "cold open"


def test_users_tracked_independently(tmp_home):
    studio = _studio(tmp_home)
    studio.add_chapters("vid-1", _chapters())
    studio.watch("amy", "vid-1", 50)
    assert studio.progress("bob", "vid-1")["watched_seconds"] == 0
    assert studio.progress("amy", "vid-1")["watched_seconds"] == 50


# -- eyes-only fence ----------------------------------------------------
def test_no_eyes_only_markers_in_notes_or_receipts(tmp_home):
    studio = _studio(tmp_home)
    job_id = studio.submit("avatar", {"seed": "clean"})
    studio.render_next()
    studio.add_chapters("vid-1", _chapters())
    studio.watch("amy", "vid-1", 10)
    for record in studio.list_renders():
        assert_clean(json.dumps(record), "render receipt")
    assert_clean(json.dumps(studio.job_status(job_id)), "job status")
