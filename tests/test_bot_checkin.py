"""Tests for levi.bot.checkin — the daily check-in question engine."""

from __future__ import annotations

import datetime as dt

import pytest

from levi.bot import checkin


def test_question_rotation_is_deterministic():
    day = dt.date(2026, 9, 20)
    assert checkin.question_for(day) == checkin.question_for(day)
    # Consecutive days ask different questions (bank has >1 entry).
    assert checkin.question_for(day) != checkin.question_for(day + dt.timedelta(days=1))
    # Same calendar date in another year asks the same question.
    other = dt.date(2027, 9, 20)
    assert checkin.question_for(day) == checkin.question_for(other)


def test_bank_is_nontrivial():
    assert len(checkin.QUESTIONS) >= 10
    assert len(set(checkin.QUESTIONS)) == len(checkin.QUESTIONS)


def test_todays_unanswered(tmp_path):
    state = checkin.todays(home=tmp_path)
    assert state["answered"] is False
    assert state["answer"] is None
    assert state["question"]


def test_answer_roundtrip(tmp_path):
    rec = checkin.answer("Shipped the digest builder.", home=tmp_path)
    assert rec["question"] == checkin.question_for()
    state = checkin.todays(home=tmp_path)
    assert state["answered"] is True
    assert state["answer"] == "Shipped the digest builder."


def test_answer_blank_refused(tmp_path):
    with pytest.raises(ValueError):
        checkin.answer("   ", home=tmp_path)
    assert checkin.todays(home=tmp_path)["answered"] is False


def test_answer_too_long_refused(tmp_path):
    with pytest.raises(ValueError):
        checkin.answer("x" * 10_001, home=tmp_path)


def test_journal_semantics_newest_wins(tmp_path):
    checkin.answer("first", home=tmp_path)
    checkin.answer("second", home=tmp_path)
    state = checkin.todays(home=tmp_path)
    assert state["answer"] == "second"
    assert len(checkin.history(home=tmp_path)) == 2


def test_history_newest_first_and_limited(tmp_path):
    # Journal semantics: newest *recorded* first, regardless of the day.
    for i in range(5):
        checkin.answer(f"a{i}", day=dt.date(2026, 9, 16 + i), home=tmp_path)
    hist = checkin.history(home=tmp_path, limit=2)
    assert [h["answer"] for h in hist] == ["a4", "a3"]


def test_history_empty_store(tmp_path):
    assert checkin.history(home=tmp_path) == []


def test_format_checkin(tmp_path):
    text = checkin.format_checkin(checkin.todays(home=tmp_path))
    assert "Check-in" in text and "Q:" in text and "no answer yet" in text
    checkin.answer("did the thing", home=tmp_path)
    text = checkin.format_checkin(checkin.todays(home=tmp_path))
    assert "A: did the thing" in text
