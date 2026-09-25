"""Tests for levi.growth.lessons — the ACE failure-lesson loop.

Covers: content addressing (stable hash), Reflector extraction (one
delta per failure shape), the Curator acceptance gate (A1/A2/A3),
dedup by content hash, append-only playbook writes, and the ace_cycle
driver (dry-run writes nothing, rerun dedups). All hermetic: the
growth dir is pointed at tmp_path.
"""

from __future__ import annotations

import json

import pytest

from levi.growth import lessons
from levi.growth.experience import Experience
from levi.growth.lessons import (
    DeltaLesson,
    ace_cycle,
    acceptance_check,
    append_lesson,
    curate,
    extract_delta_lesson,
    lesson_id,
    read_playbook,
)


@pytest.fixture()
def growth_dir(tmp_path, monkeypatch):
    d = tmp_path / "growth"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(d))
    return d


def _exp(i, content, source="drive-upload"):
    return Experience(
        id=f"e{i}",
        kind="levi-did",
        source=source,
        content=content,
        ts="2026-09-22T06:00:00Z",
        meta={},
    )


# ---------------------------------------------------------------------------
# content addressing
# ---------------------------------------------------------------------------


def test_lesson_id_stable_and_content_addressed():
    a = lesson_id("When X fails, do Y instead.")
    b = lesson_id("  when x fails,  do y instead. ")
    c = lesson_id("When X fails, do Z instead.")
    assert a == b  # normalization-insensitive
    assert a != c  # content-addressed
    assert a.startswith("les-")


# ---------------------------------------------------------------------------
# Reflector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        "Drive upload failed: connection reset by peer",
        "API call timed out after 30s",
        "Write denied: permission not granted",
        "Config file not found at ~/.levi/x.yaml",
        "Upload blocked: an equivalent write is already running",
    ],
)
def test_reflector_extracts_one_delta_per_failure_shape(failure):
    les = extract_delta_lesson(failure)
    assert les is not None
    assert les.failure
    assert len(les.lesson) >= 24
    assert les.verification
    assert les.id == lesson_id(les.lesson)


def test_reflector_skips_non_failures():
    assert extract_delta_lesson("looks good, all green") is None
    assert extract_delta_lesson("ok") is None


# ---------------------------------------------------------------------------
# Curator: acceptance gate
# ---------------------------------------------------------------------------


def test_curator_accepts_well_formed_lesson():
    les = extract_delta_lesson("Drive upload failed: connection reset")
    verdict = curate(les, existing_ids=set())
    assert verdict.accepted, verdict.reason
    assert verdict.lesson_id == les.id


def test_curator_rejects_missing_delta():
    les = DeltaLesson(
        failure="x failed",
        lesson="Something about the general nature of failure and systems.",
        verification="Check that it works.",
    )
    failed = acceptance_check(les)
    assert "A1-delta-named" in failed


def test_curator_rejects_missing_verification():
    les = DeltaLesson(
        failure="x failed",
        lesson="When x fails, do y instead next time.",
        verification="",
    )
    # delta names the change but states no check
    assert "A2-verification-stated" in acceptance_check(les)


def test_curator_rejects_non_lesson():
    verdict = curate("not a lesson", existing_ids=set())
    assert not verdict.accepted


def test_curator_dedups_by_content_hash():
    les = extract_delta_lesson("Drive upload failed: connection reset")
    v1 = curate(les, existing_ids=set())
    v2 = curate(les, existing_ids={les.id})
    assert v1.accepted
    assert not v2.accepted
    assert "duplicate" in v2.reason


# ---------------------------------------------------------------------------
# playbook: append-only
# ---------------------------------------------------------------------------


def test_append_and_read_playbook(growth_dir):
    les = extract_delta_lesson("API call timed out after 30s")
    rec = append_lesson(les, cycle_id="cyc-test")
    assert rec["id"] == les.id
    assert rec["status"] == "accepted"
    assert rec["cycle_id"] == "cyc-test"
    rows = read_playbook()
    assert len(rows) == 1
    assert rows[0]["id"] == les.id
    # raw file is one JSON object per line (append-only)
    lines = (growth_dir / "lessons.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == les.id


def test_append_rejects_failing_lesson(growth_dir):
    les = DeltaLesson(failure="x", lesson="too short", verification="")
    with pytest.raises(ValueError):
        append_lesson(les)


# ---------------------------------------------------------------------------
# ace_cycle driver
# ---------------------------------------------------------------------------


def test_ace_cycle_dry_run_writes_nothing(growth_dir):
    exps = [
        _exp(1, "Drive upload failed: connection reset by peer"),
        _exp(2, "looks good, all green", source="chat"),
    ]
    rep = ace_cycle(exps, cycle_id="c1", dry_run=True)
    assert rep["proposed"] == 1
    assert rep["accepted"] == 1
    assert not (growth_dir / "lessons.jsonl").exists()


def test_ace_cycle_rerun_dedups(growth_dir):
    exps = [_exp(1, "Drive upload failed: connection reset by peer")]
    r1 = ace_cycle(exps, cycle_id="c1")
    r2 = ace_cycle(exps, cycle_id="c2")
    assert r1["accepted"] == 1
    assert r2["accepted"] == 0
    assert r2["duplicates"] == 1
    assert len(read_playbook()) == 1  # append-only: no second write


def test_ace_cycle_one_lesson_per_source(growth_dir):
    exps = [
        _exp(1, "Drive upload failed: connection reset", source="drive"),
        _exp(2, "Drive write failed: disk full", source="drive"),
    ]
    rep = ace_cycle(exps, cycle_id="c1")
    assert rep["proposed"] == 1  # one delta per failure source


def test_ace_cycle_never_breaks_on_junk(growth_dir):
    rep = ace_cycle([None, "not-an-experience"], cycle_id="c1")
    assert rep["proposed"] == 0
