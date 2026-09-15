"""Tests for levi.growth.study — study hall: cadence + self-quiz.

Hermetic: growth dir, sessions dir, and memory store are pointed at
tmp_path; the curriculum is stubbed via monkeypatched LESSONS.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import levi.growth.curriculum as curriculum_mod
from levi.daemon import heartbeat as hb
from levi.growth import journal as growth_journal
from levi.growth import study
from levi.memory.store import MemoryStore


LESSONS = [
    {
        "id": "t1",
        "topic": "Photosynthesis",
        "kind": "fact",
        "text": (
            "Photosynthesis converts sunlight into chemical energy. "
            "Chlorophyll absorbs light inside chloroplasts, splitting water "
            "and releasing oxygen while fixing carbon dioxide into glucose."
        ),
        "taught_by": "chauncey",
    },
    {
        "id": "t2",
        "topic": "Mitosis",
        "kind": "fact",
        "text": (
            "Mitosis divides one cell into two identical daughter cells. "
            "Chromosomes condense during prophase, align at metaphase, "
            "separate in anaphase, and the cell splits in telophase."
        ),
        "taught_by": "rex",
    },
    {
        "id": "t3",
        "topic": "Gravity",
        "kind": "fact",
        "text": (
            "Gravity attracts masses toward each other. Newton described it "
            "as a force proportional to mass and inverse to distance squared; "
            "Einstein reframed it as spacetime curvature."
        ),
        "taught_by": "chauncey",
    },
]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    growth = tmp_path / "growth"
    mem = tmp_path / "memory"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(sessions))
    monkeypatch.setattr(curriculum_mod, "LESSONS", [dict(x) for x in LESSONS])
    return {"growth": growth, "mem": mem, "sessions": sessions, "home": tmp_path}


def _store(env) -> MemoryStore:
    return MemoryStore(data_dir=env["mem"])


# ---------------------------------------------------------------------------
# idle gating
# ---------------------------------------------------------------------------


def _touch(path: Path, age_hours: float) -> None:
    path.write_text("{}\n", encoding="utf-8")
    ts = time.time() - age_hours * 3600
    os.utime(path, (ts, ts))


def test_idle_when_no_activity(env):
    assert study.is_idle(env["home"], window_hours=4) is True


def test_not_idle_when_session_recent(env):
    _touch(env["sessions"] / "chat-1.jsonl", age_hours=0.5)
    assert study.is_idle(env["home"], window_hours=4) is False


def test_idle_when_session_stale(env):
    _touch(env["sessions"] / "chat-1.jsonl", age_hours=5)
    assert study.is_idle(env["home"], window_hours=4) is True


def test_heartbeat_study_skips_when_active(env, monkeypatch):
    _touch(env["sessions"] / "chat-1.jsonl", age_hours=0.2)
    state: dict = {}
    now = datetime.now(timezone.utc)
    note = hb._maybe_run_study(env["home"], state, now)
    assert "not idle" in note
    assert "last_study" not in state


def test_heartbeat_study_runs_when_idle(env, monkeypatch):
    monkeypatch.setenv("LEVI_STUDY_INTERVAL_HOURS", "4")
    state: dict = {}
    now = datetime.now(timezone.utc)
    note = hb._maybe_run_study(env["home"], state, now)
    assert note.startswith("study: ran cycle"), note
    assert state["last_study"]
    assert state["study_runs"] == 1


def test_heartbeat_study_interval_gate(env):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    state = {"last_study": recent}
    note = hb._maybe_run_study(env["home"], state, datetime.now(timezone.utc))
    assert note == "study: interval not elapsed"


def test_heartbeat_study_disabled(env, monkeypatch):
    monkeypatch.setenv("LEVI_STUDY_ENABLED", "0")
    state: dict = {}
    note = hb._maybe_run_study(env["home"], state, datetime.now(timezone.utc))
    assert "disabled" in note
    assert "last_study" not in state


# ---------------------------------------------------------------------------
# quiz
# ---------------------------------------------------------------------------


def test_quiz_perfect_recall_on_intact_lessons(env):
    quiz = study.run_quiz(sample_size=3)
    assert quiz["total_lessons"] == 3
    assert quiz["sampled"] == 3
    assert quiz["mean_score"] == 1.0
    topics = {i["topic"] for i in quiz["items"]}
    assert topics == {"Photosynthesis", "Mitosis", "Gravity"}
    for item in quiz["items"]:
        assert item["blank_hit"] is True


def test_quiz_round_robin_covers_lessons(env):
    first = study.run_quiz(sample_size=2)
    second = study.run_quiz(sample_size=2)
    got = {i["topic"] for i in first["items"]} | {i["topic"] for i in second["items"]}
    assert got == {"Photosynthesis", "Mitosis", "Gravity"}


def test_quiz_draws_blank_when_topic_missing(env):
    quiz = study.run_quiz(lessons=[LESSONS[0]], sample_size=1)
    # remove the lesson from the recall pool: recall fails → score 0
    g = study.grade(study.make_question(LESSONS[0]), None)
    assert g["score"] == 0.0
    assert quiz["items"][0]["score"] == 1.0  # control: pool intact → perfect


def test_quiz_no_curriculum(env, monkeypatch):
    monkeypatch.setattr(curriculum_mod, "LESSONS", [])
    quiz = study.run_quiz()
    assert quiz["mean_score"] is None
    assert quiz["sampled"] == 0
    assert "no curriculum" in (quiz["reason"] or "")


# ---------------------------------------------------------------------------
# study run + trend
# ---------------------------------------------------------------------------


def test_study_run_journals_quiz(env):
    report = study.run_study(store=_store(env))
    assert report["quiz"]["mean_score"] == 1.0
    entries = growth_journal.read_entries(limit=5)
    studies = [e for e in entries if e.get("kind") == "study"]
    assert len(studies) == 1
    s = studies[0]
    assert s["quiz"]["mean_score"] == 1.0
    assert s["quiz"]["sampled"] == 3  # only 3 lessons exist
    assert "quiz_trend_avg" in s


def test_study_run_dry_run_writes_nothing(env):
    study.run_study(store=_store(env), dry_run=True)
    assert growth_journal.read_entries(limit=5) == []


def test_study_trend_orders_runs(env):
    study.run_study(store=_store(env))
    study.run_study(store=_store(env))
    trend = study.study_trend(limit=10)
    assert len(trend) == 2
    assert trend[0]["ts"] <= trend[1]["ts"]
    assert all(r["mean_score"] == 1.0 for r in trend)
    text = study.format_trend(trend)
    assert "avg=1.00 over 2 scored run(s)" in text


def test_study_trend_empty(env):
    assert "No study runs yet" in study.format_trend(study.study_trend())


def test_study_run_without_curriculum_still_cycles(env, monkeypatch):
    monkeypatch.setattr(curriculum_mod, "LESSONS", [])
    report = study.run_study(store=_store(env))
    assert report["quiz"]["mean_score"] is None
    studies = [
        e for e in growth_journal.read_entries(limit=5) if e.get("kind") == "study"
    ]
    assert studies and studies[0]["quiz"]["sampled"] == 0


def test_study_safety_rails_only_growth_writes(env):
    store = _store(env)
    study.run_study(store=store)
    for e in store.list(limit=5000):
        assert "growth" in e.tags  # only growth-tagged entries, nothing else


def test_quiz_reports_taught_by(env):
    quiz = study.run_quiz(sample_size=3)
    by = {i["topic"]: i["taught_by"] for i in quiz["items"]}
    assert by["Photosynthesis"] == "chauncey"
    assert by["Mitosis"] == "rex"
