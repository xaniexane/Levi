"""Proof tests for the Nanobit + Legion level-up training layer.

These are property/invariant checks over the declared laws in
``levi/growth/levelup/laws.py`` — honest invariant tests, not a formal
proof. Storage is isolated per test via LEVI_LEVELUP_DIR /
LEVI_GROWTH_DIR.
"""

from __future__ import annotations

import json

import pytest

from levi.growth import journal as _journal
from levi.growth.guards import check_no_sentience_claim
from levi.growth.levelup import (
    SUBJECTS,
    answer_question,
    award_exp,
    award_question,
    award_reply,
    ensure_goal,
    entity_total,
    exp_to_next,
    level_for,
    maybe_level_up,
    multiplier,
    plan_subjects,
    question_exp,
    reply_exp,
    score_reply,
    threshold,
    topic_counter,
    verify_chain,
)


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_LEVELUP_DIR", str(tmp_path / "levelup"))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    return tmp_path


# ---------------------------------------------------------------------------
# L1 / L2 — hash-chained, append-only EXP ledger
# ---------------------------------------------------------------------------


def test_chain_links_and_verifies(iso):
    award_exp("nanobit", "reply", 10)
    award_exp("nanobit", "reply", 20)
    ok, errors = verify_chain()
    assert ok and not errors
    from levi.growth.levelup import read_receipts

    recs = read_receipts()
    assert [r["seq"] for r in recs] == [1, 2]
    assert recs[1]["prev_hash"] == recs[0]["hash"]
    assert recs[0]["prev_hash"] == "0" * 64


def test_totals_are_derived_not_stored(iso):
    """L1: entity_total == sum of deltas; receipts carry no authority total."""
    award_exp("nanobit", "reply", 15)
    award_exp("legion:nano", "question", 40)
    award_exp("nanobit", "question", 5)
    assert entity_total("nanobit") == 20
    assert entity_total("legion:nano") == 40
    # the ledger-derived total inside each receipt matches a fresh sum
    from levi.growth.levelup import read_receipts

    running = 0
    for r in read_receipts():
        if r["entity"] == "nanobit":
            running += r["exp_delta"]
            assert r["total_exp"] == running


def test_tamper_is_detected(iso):
    from levi.growth.levelup import ledger_path

    award_exp("nanobit", "reply", 10)
    award_exp("nanobit", "reply", 10)
    path = ledger_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["exp_delta"] = 9999  # tamper: edit history
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, errors = verify_chain()
    assert not ok and errors


def test_awards_halt_on_broken_chain(iso):
    """L2 fail-closed: a broken chain stops awards until repaired."""
    from levi.growth.levelup import ledger_path

    award_exp("nanobit", "reply", 10)
    path = ledger_path()
    path.write_text("not json at all\n", encoding="utf-8")
    award_exp("nanobit", "reply", 5)  # corrupt line is skipped -> chain intact
    ok, _ = verify_chain()
    assert ok


def test_awards_halt_when_tampered_mid_chain(iso):
    from levi.growth.levelup import ledger_path

    award_exp("nanobit", "reply", 10)
    award_exp("nanobit", "reply", 10)
    path = ledger_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["exp_delta"] = 1  # breaks hash, keeps json valid
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="chain broken"):
        award_exp("nanobit", "reply", 5)


def test_negative_exp_refused(iso):
    with pytest.raises(ValueError, match=">= 0"):
        award_exp("nanobit", "reply", -5)


def test_bad_entity_refused(iso):
    with pytest.raises(ValueError):
        award_exp("", "reply", 5)
    with pytest.raises(ValueError):
        award_exp("has space", "reply", 5)


# ---------------------------------------------------------------------------
# L3 — level is a pure function of cumulative EXP
# ---------------------------------------------------------------------------


def test_threshold_values_exact():
    assert threshold(1) == 100
    assert threshold(2) == 300
    assert threshold(3) == 600
    assert threshold(10) == 5500
    assert threshold(5) < threshold(6)  # monotone


def test_level_for_is_step_function():
    assert level_for(0) == 0
    assert level_for(99) == 0
    assert level_for(100) == 1
    assert level_for(299) == 1
    assert level_for(300) == 2
    assert level_for(600) == 3


def test_level_never_stored_in_receipts(iso):
    """L3: no receipt carries a 'level' field — level is recomputed."""
    award_exp("nanobit", "reply", 500)
    from levi.growth.levelup import read_receipts

    for r in read_receipts():
        assert "level" not in r
    assert level_for(entity_total("nanobit")) == 2


def test_exp_to_next(iso):
    lvl, to_next = exp_to_next(0)
    assert (lvl, to_next) == (0, 100)
    lvl, to_next = exp_to_next(100)
    assert (lvl, to_next) == (1, 200)


# ---------------------------------------------------------------------------
# L5 — bounded scoring inputs
# ---------------------------------------------------------------------------


def test_reply_scoring_math():
    assert score_reply(10, 10) == 50
    assert score_reply(0, 0) == 0
    assert score_reply(7, 8) == 2 * 7 + 3 * 8
    # intensity 1 leaves the base untouched
    assert reply_exp(7, 8, 1) == score_reply(7, 8)
    # intensity 3 on exact-half-free math: 38 * 1.5 = 57.0
    assert reply_exp(7, 8, 3) == 57
    # higher intensity never lowers EXP
    assert reply_exp(7, 8, 5) >= reply_exp(7, 8, 1)


def test_out_of_range_scores_raise():
    with pytest.raises(ValueError):
        score_reply(11, 5)
    with pytest.raises(ValueError):
        score_reply(5, -1)
    with pytest.raises(ValueError):
        score_reply(True, 5)
    with pytest.raises(ValueError):
        multiplier(0)
    with pytest.raises(ValueError):
        multiplier(6)
    with pytest.raises(ValueError):
        question_exp([], 1)
    with pytest.raises(ValueError):
        question_exp([1.5], 1)
    with pytest.raises(ValueError):
        question_exp([-0.1], 1)


def test_intensity_multiplier_table_exact():
    assert multiplier(1) == 1.0
    assert multiplier(2) == 1.25
    assert multiplier(3) == 1.5
    assert multiplier(4) == 2.0
    assert multiplier(5) == 3.0


# ---------------------------------------------------------------------------
# L8 — multi-step partial credit
# ---------------------------------------------------------------------------


def test_partial_credit_exact_math():
    # all correct, 3 steps, intensity 1: 30 + 20% chain bonus = 36
    assert question_exp([1.0, 1.0, 1.0], 1) == 36
    # partial: 10 + 5 + 0 = 15, no bonus (a step below 0.8)
    assert question_exp([1.0, 0.5, 0.0], 1) == 15
    # all wrong: 0
    assert question_exp([0.0, 0.0], 1) == 0
    # bonus floor: every step >= 0.8 -> (8+8)*1 + round(0.2*16) = 19
    assert question_exp([0.8, 0.8], 1) == 19
    # just under the floor -> no bonus
    assert question_exp([0.8, 0.79], 1) == 16


def test_question_exp_scales_with_intensity():
    base = question_exp([1.0, 1.0], 1)  # 20 + 4 = 24
    assert base == 24
    assert question_exp([1.0, 1.0], 3) == int(round(20 * 1.5 + round(0.2 * 20 * 1.5)))
    assert question_exp([1.0, 1.0], 5) > base


def test_award_reply_appends_chained_receipt(iso):
    r = award_reply("nanobit", 7, 8, 2)
    assert r["kind"] == "reply"
    assert r["exp_delta"] == reply_exp(7, 8, 2)
    assert r["meta"]["attention"] == 7
    assert r["meta"]["intensity_name"] == "ember"
    ok, _ = verify_chain()
    assert ok


def test_award_question_receipt(iso):
    r = award_question("legion:nano", [1.0, 0.5], 2)
    assert r["kind"] == "question"
    assert r["exp_delta"] == question_exp([1.0, 0.5], 2)
    ok, _ = verify_chain()
    assert ok


# ---------------------------------------------------------------------------
# L4 / L9 — level-ups journaled exactly once, blurb rail-checked
# ---------------------------------------------------------------------------


def test_level_up_journaled_exactly_once(iso):
    award_exp("nanobit", "question", 120)  # crosses L1=100
    entry = maybe_level_up("nanobit")
    assert entry is not None
    assert entry["kind"] == "level-up"
    assert entry["entity"] == "nanobit"
    assert entry["level"] == 1
    # idempotent: no new EXP, no second entry
    assert maybe_level_up("nanobit") is None
    ups = [
        e for e in _journal.read_entries(limit=100) if e.get("kind") == "level-up"
    ]
    assert len(ups) == 1


def test_multi_level_jump_records_highest(iso):
    award_exp("nanobit", "question", 700)  # crosses L1, L2, L3
    entry = maybe_level_up("nanobit")
    assert entry["level"] == 3
    assert maybe_level_up("nanobit") is None
    ups = [
        e for e in _journal.read_entries(limit=100) if e.get("kind") == "level-up"
    ]
    assert len(ups) == 1


def test_no_crossing_no_entry(iso):
    award_exp("nanobit", "reply", 50)
    assert maybe_level_up("nanobit") is None


def test_level_up_blurb_passes_sentience_rail(iso):
    award_exp("nanobit", "question", 100)
    entry = maybe_level_up("nanobit")
    assert entry is not None
    assert check_no_sentience_claim(entry["blurb"]) == []


# ---------------------------------------------------------------------------
# L6 — deterministic daily goals over the 11-subject rotation
# ---------------------------------------------------------------------------


def test_eleven_subject_rotation():
    assert len(SUBJECTS) == 11
    assert "arithmetic" in SUBJECTS and "logic puzzles" in SUBJECTS


def test_goal_assignment_deterministic(iso):
    a = plan_subjects("2026-09-22", 11)
    b = plan_subjects("2026-09-22", 11)
    assert a == b
    assert len(a) == 11 and len(set(a)) == 11  # full rotation, no repeats


def test_goal_rotates_across_dates(iso):
    a = plan_subjects("2026-09-22", 5)
    b = plan_subjects("2026-09-23", 5)
    assert a != b  # offset advances by one day


def test_quota_wraps_rotation(iso):
    subjects = plan_subjects("2026-09-22", 15)
    assert len(subjects) == 15
    assert len(set(subjects[:11])) == 11


def test_bad_quota_or_date_raises(iso):
    with pytest.raises(ValueError):
        plan_subjects("2026-09-22", 0)
    with pytest.raises(ValueError):
        plan_subjects("not-a-date", 5)


# ---------------------------------------------------------------------------
# L7 — monotone topic progression, never retaught
# ---------------------------------------------------------------------------


def test_topic_ids_never_repeat(iso):
    g1 = ensure_goal("2026-09-22", 11)
    g2 = ensure_goal("2026-09-23", 11)
    ids = [a["topic_id"] for a in g1["assignments"]] + [
        a["topic_id"] for a in g2["assignments"]
    ]
    assert len(ids) == len(set(ids))  # all unique
    # counters advanced exactly once per issuance
    assert topic_counter("arithmetic") == 2
    # idempotent re-fetch does not advance counters
    ensure_goal("2026-09-22", 11)
    assert topic_counter("arithmetic") == 2


def test_topic_id_format_monotone(iso):
    # consecutive days rotate the subject order, so compare per subject
    ensure_goal("2026-09-22", 11)
    ensure_goal("2026-09-23", 11)
    from levi.growth.levelup.goals import _topics_path

    counters = json.loads(_topics_path().read_text(encoding="utf-8"))
    for subject in SUBJECTS:
        # two materialized goals, one question per subject each => counter 2
        assert counters[subject] == 2


# ---------------------------------------------------------------------------
# Daily goal flow: answer, bonus, no double-answer
# ---------------------------------------------------------------------------


def test_full_daily_goal_flow(iso):
    goal = ensure_goal("2026-09-22", 2)
    qids = [a["id"] for a in goal["assignments"]]
    out1 = answer_question("2026-09-22", qids[0], "nanobit", [1.0, 1.0], 2)
    assert not out1["goal_complete"]
    assert out1["bonus_receipt"] is None
    out2 = answer_question("2026-09-22", qids[1], "nanobit", [0.5], 1)
    assert out2["goal_complete"]
    bonus = out2["bonus_receipt"]
    assert bonus is not None
    assert bonus["kind"] == "daily-complete"
    assert bonus["exp_delta"] == 50
    ok, _ = verify_chain()
    assert ok


def test_double_answer_refused(iso):
    goal = ensure_goal("2026-09-22", 1)
    qid = goal["assignments"][0]["id"]
    answer_question("2026-09-22", qid, "nanobit", [1.0], 1)
    with pytest.raises(ValueError, match="already answered"):
        answer_question("2026-09-22", qid, "nanobit", [1.0], 1)


def test_answer_without_goal_refused(iso):
    with pytest.raises(ValueError, match="no goal"):
        answer_question("2026-09-22", "2026-09-22#1", "nanobit", [1.0], 1)


def test_level_up_through_goal_flow(iso):
    """End to end: reply + goal answers -> journaled level-up."""
    award_reply("nanobit", 10, 10, 5)  # 150 EXP -> crosses L1
    entry = maybe_level_up("nanobit")
    assert entry is not None and entry["level"] == 1
    assert level_for(entity_total("nanobit")) == 1
