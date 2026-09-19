# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Threadweaver waves — listening sessions, wave scheduler, digests.

Hermetic: state persists under a tmp LEVI_HOME via monkeypatch. No
network, no writes to the real user HOME.
"""

from __future__ import annotations

import json

import pytest

from levi.dynasty.wave.threadweaver_waves import (
    ListeningSessions,
    SessionError,
    WaveError,
    WaveScheduler,
    digest,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


@pytest.fixture
def sessions(tmp_home):
    return ListeningSessions()


@pytest.fixture
def scheduler(tmp_home):
    return WaveScheduler()


# -- listening sessions: happy path -----------------------------------


def test_session_full_cycle(sessions):
    sid = sessions.create_session("late night")
    assert isinstance(sid, str) and sid
    assert sessions.join(sid, "levi") == ["levi"]
    assert sessions.join(sid, "keeper") == ["levi", "keeper"]
    assert sessions.enqueue(sid, "media://track-a") == 1
    assert sessions.enqueue(sid, "media://track-b") == 2

    pos = sessions.position(sid)
    assert pos == {
        "now_playing": None,
        "queue_depth": 2,
        "participants": ["levi", "keeper"],
    }

    assert sessions.advance(sid) == "media://track-a"
    assert sessions.position(sid)["now_playing"] == "media://track-a"
    assert sessions.advance(sid) == "media://track-b"
    assert sessions.advance(sid) is None  # empty advance -> None, not error
    assert sessions.position(sid)["queue_depth"] == 0

    assert sessions.leave(sid, "keeper") == ["levi"]
    assert sessions.position(sid)["participants"] == ["levi"]


def test_session_join_is_idempotent(sessions):
    sid = sessions.create_session("x")
    sessions.join(sid, "levi")
    sessions.join(sid, "levi")
    assert sessions.position(sid)["participants"] == ["levi"]


def test_sessions_persist_across_instances(tmp_home):
    first = ListeningSessions()
    sid = first.create_session("keep")
    first.join(sid, "levi")
    first.enqueue(sid, "media://one")

    second = ListeningSessions()  # same LEVI_HOME
    pos = second.position(sid)
    assert pos["queue_depth"] == 1
    assert pos["participants"] == ["levi"]
    assert second.advance(sid) == "media://one"


# -- listening sessions: adversarial ----------------------------------


def test_unknown_session_raises_session_error(sessions):
    with pytest.raises(SessionError):
        sessions.position("nope")
    with pytest.raises(SessionError):
        sessions.join("nope", "levi")
    with pytest.raises(SessionError):
        sessions.leave("nope", "levi")
    with pytest.raises(SessionError):
        sessions.enqueue("nope", "media://x")
    with pytest.raises(SessionError):
        sessions.advance("nope")


def test_session_bad_names_refused(sessions):
    with pytest.raises(SessionError):
        sessions.create_session("")
    with pytest.raises(SessionError):
        sessions.create_session("   ")
    with pytest.raises(SessionError):
        sessions.create_session(None)


def test_leave_non_member_refused(sessions):
    sid = sessions.create_session("x")
    sessions.join(sid, "levi")
    with pytest.raises(SessionError):
        sessions.leave(sid, "stranger")


def test_enqueue_empty_ref_refused(sessions):
    sid = sessions.create_session("x")
    with pytest.raises(SessionError):
        sessions.enqueue(sid, "")
    with pytest.raises(SessionError):
        sessions.enqueue(sid, None)


def test_advance_empty_queue_returns_none(sessions):
    sid = sessions.create_session("quiet")
    assert sessions.advance(sid) is None
    assert sessions.advance(sid) is None  # repeatable


# -- wave scheduler: happy path ---------------------------------------


def test_wave_schedule_due_fire(scheduler):
    wid = scheduler.schedule_wave("thread-1", "2026-09-18T10:00:00", {"text": "hello"})
    assert isinstance(wid, str) and wid

    # not due before its time
    assert scheduler.due_waves("2026-09-18T09:59:59") == []

    due = scheduler.due_waves("2026-09-18T10:00:00")
    assert len(due) == 1
    assert due[0]["id"] == wid
    assert due[0]["thread_id"] == "thread-1"

    payload = scheduler.fire(wid)
    assert payload == {"text": "hello"}
    assert scheduler.due_waves("2026-09-18T12:00:00") == []  # fired: gone


def test_wave_due_ordering_oldest_first(scheduler):
    first = scheduler.schedule_wave("t", "2026-09-18T08:00:00", {"n": 1})
    second = scheduler.schedule_wave("t", "2026-09-18T09:00:00", {"n": 2})
    due = scheduler.due_waves("2026-09-18T10:00:00")
    assert [w["id"] for w in due] == [first, second]


def test_wave_cancel(scheduler):
    wid = scheduler.schedule_wave("t", "2026-09-18T10:00:00", {"n": 1})
    scheduler.cancel(wid)
    assert scheduler.due_waves("2026-09-18T12:00:00") == []


def test_waves_persist_across_instances(tmp_home):
    first = WaveScheduler()
    wid = first.schedule_wave("t", "2026-09-18T10:00:00", {"n": 7})
    second = WaveScheduler()
    assert [w["id"] for w in second.due_waves("2026-09-18T11:00:00")] == [wid]


# -- wave scheduler: adversarial --------------------------------------


def test_double_fire_raises_wave_error(scheduler):
    wid = scheduler.schedule_wave("t", "2026-09-18T10:00:00", {"n": 1})
    scheduler.fire(wid)
    with pytest.raises(WaveError):
        scheduler.fire(wid)


def test_fire_cancelled_wave_refused(scheduler):
    wid = scheduler.schedule_wave("t", "2026-09-18T10:00:00", {"n": 1})
    scheduler.cancel(wid)
    with pytest.raises(WaveError):
        scheduler.fire(wid)


def test_fire_unknown_wave_refused(scheduler):
    with pytest.raises(WaveError):
        scheduler.fire("nope")


def test_cancel_fired_or_unknown_refused(scheduler):
    wid = scheduler.schedule_wave("t", "2026-09-18T10:00:00", {"n": 1})
    scheduler.fire(wid)
    with pytest.raises(WaveError):
        scheduler.cancel(wid)
    with pytest.raises(WaveError):
        scheduler.cancel("nope")


def test_schedule_malformed_inputs_refused(scheduler):
    with pytest.raises(WaveError):
        scheduler.schedule_wave("", "2026-09-18T10:00:00", {})
    with pytest.raises(WaveError):
        scheduler.schedule_wave("t", "not-a-time", {})
    with pytest.raises(WaveError):
        scheduler.schedule_wave("t", "", {})
    with pytest.raises(WaveError):
        scheduler.schedule_wave("t", "2026-09-18T10:00:00", "nope")
    with pytest.raises(WaveError):
        scheduler.schedule_wave("t", "2026-09-18T10:00:00", {"bad": object()})
    with pytest.raises(WaveError):
        scheduler.due_waves("garbage")


def test_wave_store_corrupt_raises(tmp_home, scheduler):
    path = tmp_home / "dynasty" / "threadweaver" / "waves.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(WaveError):
        scheduler.due_waves("2026-09-18T10:00:00")


# -- digest ------------------------------------------------------------


def test_digest_happy_path():
    steps = [
        {"step": "draft", "author": "levi", "ts": "2026-09-18T10:00:00", "text": "a"},
        {
            "step": "challenge",
            "author": "keeper",
            "ts": "2026-09-18T10:01:00",
            "text": "b",
            "media_ref": "media://one",
        },
        {
            "step": "consolidate",
            "author": "levi",
            "ts": "2026-09-18T10:02:00",
            "text": "c",
            "media_refs": ["media://one", "media://two"],
        },
    ]
    result = digest(steps)
    assert result == {
        "step_count": 3,
        "participants": ["keeper", "levi"],
        "first_ts": "2026-09-18T10:00:00",
        "last_ts": "2026-09-18T10:02:00",
        "media_refs": ["media://one", "media://two"],
    }


def test_digest_empty_and_sparse():
    assert digest([]) == {
        "step_count": 0,
        "participants": [],
        "first_ts": None,
        "last_ts": None,
        "media_refs": [],
    }
    result = digest([{"step": "draft", "text": "no meta"}])
    assert result["step_count"] == 1
    assert result["participants"] == []
    assert result["first_ts"] is None


def test_digest_dedupes_participants_and_media():
    steps = [
        {"author": "levi", "media_ref": "m1"},
        {"author": "levi", "media_refs": ["m1", "m2"]},
    ]
    result = digest(steps)
    assert result["participants"] == ["levi"]
    assert result["media_refs"] == ["m1", "m2"]


def test_digest_malformed_input():
    with pytest.raises(TypeError):
        digest("not a list")
    with pytest.raises(TypeError):
        digest([{"ok": True}, "not a dict"])
    with pytest.raises(TypeError):
        digest(None)


def test_digest_is_pure(tmp_home):
    before = list((tmp_home).iterdir()) if tmp_home.exists() else []
    digest([{"author": "levi", "ts": "2026-09-18T10:00:00", "text": "x"}])
    after = list((tmp_home).iterdir()) if tmp_home.exists() else []
    assert before == after
    assert not (tmp_home / "dynasty").exists()


def test_session_store_file_is_json(tmp_home, sessions):
    sid = sessions.create_session("check")
    sessions.join(sid, "levi")
    data = json.loads(
        (tmp_home / "dynasty" / "threadweaver" / "sessions.json").read_text(
            encoding="utf-8"
        )
    )
    assert sid in data
    assert data[sid]["participants"] == ["levi"]
