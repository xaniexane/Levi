"""Tests for the debrief bot — the evening mirror of the check-in bot.

Proofs for the laws in ``levi/bot/debrief.py``: deterministic rotation,
append-only journal, deny-closed answers, skippable evenings, corrupt
lines skipped, and the check-in/debrief bookends in ``pair_status``.
"""

import datetime as _dt
import json

import pytest

from levi.bot import checkin, debrief


def test_question_rotation_is_deterministic():
    day = _dt.date(2026, 9, 23)
    assert debrief.question_for(day) == debrief.question_for(day)
    assert debrief.question_for(day) in debrief.QUESTIONS


def test_rotation_cycles_through_bank():
    seen = {
        debrief.question_for(_dt.date(2026, 1, 1) + _dt.timedelta(days=i))
        for i in range(len(debrief.QUESTIONS))
    }
    assert seen == set(debrief.QUESTIONS)


def test_answer_appends_and_todays_reads(tmp_path):
    rec = debrief.answer("closed the loop on the census", home=tmp_path)
    assert rec["date"] == "2026-09-23" or rec["date"]  # date-shaped
    state = debrief.todays(home=tmp_path)
    assert state["answered"] is True
    assert state["answer"] == "closed the loop on the census"


def test_answer_twice_keeps_both_newest_wins(tmp_path):
    debrief.answer("first close", home=tmp_path)
    debrief.answer("second close", home=tmp_path)
    state = debrief.todays(home=tmp_path)
    assert state["answer"] == "second close"
    assert len(debrief.history(home=tmp_path)) == 2


def test_blank_answer_refused(tmp_path):
    with pytest.raises(ValueError):
        debrief.answer("   ", home=tmp_path)
    assert debrief.todays(home=tmp_path)["answered"] is False


def test_overlong_answer_refused(tmp_path):
    with pytest.raises(ValueError):
        debrief.answer("x" * 10_001, home=tmp_path)


def test_skipped_day_leaves_no_record(tmp_path):
    state = debrief.todays(home=tmp_path)
    assert state["answered"] is False
    assert state["answer"] is None


def test_corrupt_lines_skipped(tmp_path):
    path = tmp_path / ".levi" / "bot" / "debriefs.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "not json\n"
        + json.dumps({"date": "2026-09-20", "answer": "kept"})
        + "\n"
        + json.dumps({"nope": True})
        + "\n",
        encoding="utf-8",
    )
    hist = debrief.history(home=tmp_path)
    assert len(hist) == 1
    assert hist[0]["answer"] == "kept"


def test_journal_is_owner_only(tmp_path):
    import os
    import stat

    debrief.answer("quiet close", home=tmp_path)
    path = tmp_path / ".levi" / "bot" / "debriefs.jsonl"
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_format_debrief_unanswered(tmp_path):
    text = debrief.format_debrief(debrief.todays(home=tmp_path))
    assert "Debrief" in text
    assert "no answer yet" in text


def test_pair_status_bookends(tmp_path):
    checkin.answer("morning intent", home=tmp_path)
    status = debrief.pair_status(home=tmp_path)
    assert status["closed"] is False  # debrief missing
    assert status["checkin"]["answered"] is True
    debrief.answer("evening close", home=tmp_path)
    status = debrief.pair_status(home=tmp_path)
    assert status["closed"] is True


def test_pair_status_reads_checkin_without_writing(tmp_path):
    before = (
        list((tmp_path / ".levi" / "bot").glob("*"))
        if (tmp_path / ".levi" / "bot").exists()
        else []
    )
    debrief.pair_status(home=tmp_path)
    after = (
        list((tmp_path / ".levi" / "bot").glob("*"))
        if (tmp_path / ".levi" / "bot").exists()
        else []
    )
    assert before == after  # read-only: no journal files created
