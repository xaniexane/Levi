"""Tests for the blue-team growth curriculum (study-hall track).

NOTE: ``tests/test_growth_curriculum.py`` already covers the founder
seed curriculum (Chauncey + Rex teachings). This file covers the
separate defensive blue-team / LEVI-domain track in
``levi.growth.curriculum.blue_team`` plus a proof that
``levi.growth.study.get_lessons()`` resolves the real contract
(``from levi.growth.curriculum import LESSONS``) instead of falling
back to the torch seed.

All hermetic: journal/state writes go through ``LEVI_GROWTH_DIR``
pointed at tmp_path, never the real ~/.levi. No network.
"""

from __future__ import annotations

import re

import pytest

from levi.growth.curriculum.blue_team import (
    BLUE_TEAM_KINDS,
    BLUE_TEAM_LESSONS,
    BLUE_TEAM_TOPICS,
    validate_blue_team_lessons,
)
from levi.growth.study import (
    get_lessons,
    grade,
    make_question,
    recall_by_topic,
    run_quiz,
)


@pytest.fixture(autouse=True)
def isolated_growth_home(tmp_path, monkeypatch):
    """Hermetic journal/state: the torch seed fallback sees nothing."""
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    monkeypatch.setenv("HOME", str(tmp_path))


# ---------------------------------------------------------------------------
# lesson structure
# ---------------------------------------------------------------------------


def test_blue_team_lessons_count_in_range():
    assert 24 <= len(BLUE_TEAM_LESSONS) <= 40, (
        f"expected 24-40 lessons, got {len(BLUE_TEAM_LESSONS)}"
    )


def test_blue_team_lessons_have_exact_five_keys():
    for lesson in BLUE_TEAM_LESSONS:
        assert set(lesson) == {"id", "topic", "kind", "text", "taught_by"}, (
            f"{lesson.get('id')}: keys = {sorted(lesson)}"
        )
        assert isinstance(lesson["id"], str) and lesson["id"]
        assert isinstance(lesson["topic"], str) and lesson["topic"]
        assert isinstance(lesson["kind"], str) and lesson["kind"]
        assert isinstance(lesson["text"], str) and lesson["text"].strip()
        assert isinstance(lesson["taught_by"], str) and lesson["taught_by"]


def test_blue_team_ids_unique():
    ids = [lesson["id"] for lesson in BLUE_TEAM_LESSONS]
    assert len(set(ids)) == len(ids), "duplicate lesson ids"


def test_blue_team_kinds_within_accepted_set():
    kinds = {lesson["kind"] for lesson in BLUE_TEAM_LESSONS}
    assert kinds <= set(BLUE_TEAM_KINDS), f"unexpected kinds: {kinds - set(BLUE_TEAM_KINDS)}"
    assert kinds == {"concept", "procedure", "checklist", "scenario"}, (
        f"expected all four kinds represented, got {sorted(kinds)}"
    )


def test_blue_team_topics_coherent():
    covered = {lesson["topic"] for lesson in BLUE_TEAM_LESSONS}
    assert covered == set(BLUE_TEAM_TOPICS), (
        f"topic drift: {covered ^ set(BLUE_TEAM_TOPICS)}"
    )
    assert 6 <= len(covered) <= 8


def test_blue_team_text_sentence_count():
    for lesson in BLUE_TEAM_LESSONS:
        sentences = [
            s for s in re.split(r"(?<=[.!?])\s+", lesson["text"].strip()) if s
        ]
        assert 2 <= len(sentences) <= 6, (
            f"{lesson['id']}: expected 2-6 sentences, got {len(sentences)}"
        )


def test_blue_team_taught_by_has_provenance():
    for lesson in BLUE_TEAM_LESSONS:
        tb = lesson["taught_by"]
        assert ":" in tb and not tb.startswith(":") and not tb.endswith(":"), (
            f"{lesson['id']}: taught_by should name a provenance, got {tb!r}"
        )


def test_validate_accepts_module_lessons():
    assert validate_blue_team_lessons(list(BLUE_TEAM_LESSONS)) is not None


def test_validate_rejects_bad_lessons():
    good = dict(BLUE_TEAM_LESSONS[0])
    bad_keyset = dict(good)
    del bad_keyset["taught_by"]
    with pytest.raises(ValueError):
        validate_blue_team_lessons([bad_keyset])
    with pytest.raises(ValueError):
        validate_blue_team_lessons([{**good, "kind": "fact"}])
    with pytest.raises(ValueError):
        validate_blue_team_lessons([{**good, "topic": "Nope"}])
    with pytest.raises(ValueError):
        validate_blue_team_lessons([{**good, "text": "   "}])
    with pytest.raises(ValueError):
        validate_blue_team_lessons([good, dict(good)])
    with pytest.raises(ValueError):
        validate_blue_team_lessons("not-a-list")


# ---------------------------------------------------------------------------
# the real contract path through study.py
# ---------------------------------------------------------------------------


def test_get_lessons_uses_real_contract_not_seed():
    """get_lessons() resolves the curriculum import first.

    With an isolated growth dir the torch seed fallback is empty, so a
    non-empty result can only come from ``from levi.growth.curriculum
    import LESSONS`` — the real contract path is live.
    """
    from levi.growth import journal as _journal

    assert _journal.growth_dir().is_dir()
    assert not (_journal.growth_dir() / "curriculum_seed.json").exists()

    lessons = get_lessons()
    assert lessons, "expected the curriculum contract path to return lessons"
    assert all(isinstance(it, dict) and it.get("text") for it in lessons)

    from levi.growth.curriculum import LESSONS

    assert lessons == [it for it in LESSONS if isinstance(it, dict) and it.get("text")]


def test_blue_team_lessons_quiz_end_to_end():
    """Blue-team lessons flow through the study-hall quiz machinery."""
    quiz = run_quiz(lessons=list(BLUE_TEAM_LESSONS), sample_size=5)
    assert quiz["sampled"] == 5
    assert quiz["total_lessons"] == len(BLUE_TEAM_LESSONS)
    assert quiz["mean_score"] is not None
    assert 0.0 <= quiz["mean_score"] <= 1.0
    # topic-cued recall unions every lesson under the topic, so scores
    # should be near-perfect on intact material
    assert quiz["mean_score"] >= 0.9


def test_blue_team_question_and_recall():
    lesson = BLUE_TEAM_LESSONS[0]
    q = make_question(lesson)
    assert q["topic"] == lesson["topic"]
    assert q["key_terms"]
    recalled = recall_by_topic(list(BLUE_TEAM_LESSONS), lesson["topic"])
    assert recalled is not None
    assert lesson["text"] in recalled["text"]
    g = grade(q, recalled)
    assert g["score"] > 0.0
    # a blank topic draws a blank — honest failure mode
    assert recall_by_topic(list(BLUE_TEAM_LESSONS), "no such topic") is None
