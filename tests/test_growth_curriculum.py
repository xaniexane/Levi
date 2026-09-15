"""Tests for the LEVI growth curriculum (Chauncey + Rex seed teachings).

All hermetic: the memory store is pointed at tmp_path, never the real
~/.levi. Covers lesson validation, ingestion with founder provenance
and high corroboration, re-load idempotency (zero duplicates), topic
counts, and retrievability of a lesson's text from the memory store.
"""

from __future__ import annotations

import pytest

from levi.growth.curriculum import (
    LESSONS,
    TOPICS,
    load_curriculum,
    curriculum_topics,
    curriculum_entries,
)
from levi.growth.curriculum.lessons import validate_lessons
from levi.memory.store import MemoryStore


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "memory")


# ---------------------------------------------------------------------------
# lesson structure
# ---------------------------------------------------------------------------


def test_lessons_count_in_range():
    assert 25 <= len(LESSONS) <= 40, f"expected 25-40 lessons, got {len(LESSONS)}"


def test_lessons_cover_all_topics():
    covered = {lesson["topic"] for lesson in LESSONS}
    assert covered == set(TOPICS), f"missing topics: {set(TOPICS) - covered}"


def test_lessons_validate_clean():
    assert validate_lessons(list(LESSONS)) == list(LESSONS)


def test_lessons_text_is_crisp():
    for lesson in LESSONS:
        words = lesson["text"].split()
        assert 10 <= len(words) <= 120, (
            f"{lesson['id']}: expected 10-120 words, got {len(words)}"
        )


def test_validate_rejects_bad_lesson():
    with pytest.raises(ValueError):
        validate_lessons([{"id": "x-1"}])
    with pytest.raises(ValueError):
        validate_lessons(
            [
                {
                    "id": "x-1",
                    "topic": "Nope",
                    "kind": "fact",
                    "text": "some text here",
                    "taught_by": "chauncey",
                }
            ]
        )
    with pytest.raises(ValueError):
        validate_lessons(
            [
                {
                    "id": "x-1",
                    "topic": TOPICS[0],
                    "kind": "fact",
                    "text": "some text here",
                    "taught_by": "mallory",
                }
            ]
        )


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------


def test_load_ingests_all_lessons_with_provenance(store):
    report = load_curriculum(store=store)
    assert report["total"] == len(LESSONS)
    assert report["accepted"] == len(LESSONS)
    assert report["corroborated"] == 0
    assert report["skipped"] == 0
    assert report["stamped"] == len(LESSONS)

    entries = curriculum_entries(store=store)
    assert len(entries) == len(LESSONS)
    for entry in entries:
        md = entry.metadata or {}
        assert "growth" in entry.tags
        assert "curriculum" in entry.tags
        assert md.get("taught_by") in {"chauncey", "rex"}
        provenance = md.get("provenance") or {}
        assert provenance.get("taught_by") in {"chauncey", "rex"}
        assert md.get("seed") is True
        assert md.get("status") == "seeded"
        assert md.get("lesson_id")
        # founder seeds start highly corroborated, not provisional
        assert entry.importance >= 0.9
        assert md.get("corroborated_count", 0) >= 20


def test_reload_produces_zero_duplicates(store):
    first = load_curriculum(store=store)
    second = load_curriculum(store=store)
    assert second["accepted"] == 0
    assert second["skipped"] == 0
    entries = curriculum_entries(store=store)
    assert len(entries) == first["total"] == len(LESSONS)
    lesson_ids = [e.metadata["lesson_id"] for e in entries]
    assert len(set(lesson_ids)) == len(LESSONS)


def test_curriculum_topics_reports_correct_counts(store):
    load_curriculum(store=store)
    counts = curriculum_topics(store=store)
    assert set(counts) == set(TOPICS)
    assert sum(counts.values()) == len(LESSONS)
    expected = {}
    for lesson in LESSONS:
        expected[lesson["topic"]] = expected.get(lesson["topic"], 0) + 1
    assert counts == expected


def test_lesson_text_retrievable_via_memory_store(store):
    load_curriculum(store=store)
    lesson = next(les for les in LESSONS if les["id"] == "dna-1")
    hits = store.search("three DNA strands")
    assert any(h.content == lesson["text"] for h in hits), (
        "seed lesson text not retrievable from the memory store"
    )
    entry = next(h for h in hits if h.content == lesson["text"])
    assert entry.metadata["taught_by"] == lesson["taught_by"] == "chauncey"
    assert entry.metadata["topic"] == "Organism DNA"


def test_curriculum_entries_filter_by_topic(store):
    load_curriculum(store=store)
    dna = curriculum_entries(store=store, topic="Organism DNA")
    expected = [les for les in LESSONS if les["topic"] == "Organism DNA"]
    assert len(dna) == len(expected) > 0


def test_fearless_lessons_present_and_attributed(store):
    load_curriculum(store=store)
    fearless = curriculum_entries(store=store, topic="Fearless")
    assert len(fearless) == 2
    for entry in fearless:
        assert entry.metadata["taught_by"] == "chauncey"
    texts = " ".join(e.content for e in fearless)
    assert "refusal" in texts.lower()
    assert "weapons of mass destruction" in texts.lower()
    assert "sexual harm to children" in texts.lower()


def test_later_load_corroborates_after_forget(store):
    load_curriculum(store=store)
    # remove one seed entry; re-load should re-accept just that one
    victim = curriculum_entries(store=store)[0]
    assert store.delete(victim.id)
    report = load_curriculum(store=store)
    assert report["accepted"] == 1
    assert report["corroborated"] == len(LESSONS) - 1
    assert len(curriculum_entries(store=store)) == len(LESSONS)
