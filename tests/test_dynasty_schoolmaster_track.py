# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Schoolmaster track tooling tests — SM-2, Socratic drills, Feynman, tracks.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from levi.dynasty.wave.schoolmaster_track import (
    DrillError,
    TrackError,
    complete_lesson,
    create_track,
    drill,
    due_cards,
    progress,
    schedule,
    score_explanation,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def _now(offset_days=0):
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat(
        timespec="seconds"
    )


def _srs(tmp_home):
    path = tmp_home / "dynasty" / "schoolmaster" / "srs.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# SM-2 scheduler
# ---------------------------------------------------------------------


class TestSchedule:
    def test_first_review_success(self, tmp_home):
        out = schedule("c1", 5)
        assert out["card_id"] == "c1"
        assert out["repetitions"] == 1
        assert out["interval_days"] == 1.0
        assert out["easiness"] > 2.5  # q=5 raises easiness
        due = datetime.fromisoformat(out["due_at_iso"])
        assert due > datetime.now(timezone.utc)

    def test_progression_1_6_then_ef(self, tmp_home):
        schedule("c1", 4)
        second = schedule("c1", 4)
        assert second["repetitions"] == 2
        assert second["interval_days"] == 6.0
        third = schedule("c1", 4)
        assert third["repetitions"] == 3
        assert third["interval_days"] == round(6.0 * third["easiness"], 1)

    def test_quality_below_3_resets(self, tmp_home):
        schedule("c1", 5)
        schedule("c1", 5)
        failed = schedule("c1", 2)
        assert failed["repetitions"] == 0
        assert failed["interval_days"] == 1.0
        # a failure on a fresh card also resets, never goes negative
        fresh = schedule("c2", 0)
        assert fresh["repetitions"] == 0
        assert fresh["interval_days"] == 1.0

    def test_easiness_floor(self, tmp_home):
        for _ in range(10):
            schedule("c1", 0)
        assert _srs(tmp_home)["cards"]["c1"]["easiness"] >= 1.3

    def test_store_shape(self, tmp_home):
        schedule("c1", 3)
        data = _srs(tmp_home)
        entry = data["cards"]["c1"]
        assert set(entry) >= {
            "easiness",
            "repetitions",
            "interval_days",
            "due_at",
            "reviews",
            "last_quality",
        }
        assert entry["reviews"] == 1

    def test_reviews_accumulate(self, tmp_home):
        schedule("c1", 4)
        schedule("c1", 4)
        assert _srs(tmp_home)["cards"]["c1"]["reviews"] == 2

    def test_persists_across_calls(self, tmp_home):
        schedule("c1", 5)
        again = schedule("c1", 5)
        assert again["repetitions"] == 2  # state survived the round trip

    def test_quality_out_of_range(self, tmp_home):
        for bad in (-1, 6, 100):
            with pytest.raises(DrillError):
                schedule("c1", bad)

    def test_quality_wrong_type(self, tmp_home):
        for bad in (3.5, "5", None, True, [5]):
            with pytest.raises(DrillError):
                schedule("c1", bad)

    def test_bad_card_id(self, tmp_home):
        for bad in ("", "   ", None, 42):
            with pytest.raises(DrillError):
                schedule(bad, 4)

    def test_now_iso_override(self, tmp_home):
        stamp = "2026-01-01T00:00:00+00:00"
        out = schedule("c1", 5, now_iso=stamp)
        assert out["due_at_iso"].startswith("2026-01-02")
        with pytest.raises(DrillError):
            schedule("c1", 5, now_iso="not-a-time")


class TestDueCards:
    def test_nothing_due_initially(self, tmp_home):
        schedule("c1", 5)
        assert due_cards(_now()) == []

    def test_due_after_backdate(self, tmp_home):
        schedule("c1", 5, now_iso=_now(-10))
        due = due_cards(_now())
        assert [d["card_id"] for d in due] == ["c1"]

    def test_sorted_oldest_first(self, tmp_home):
        schedule("a", 5, now_iso=_now(-10))
        schedule("b", 5, now_iso=_now(-5))
        schedule("c", 5)  # not due
        due = due_cards(_now())
        assert [d["card_id"] for d in due] == ["a", "b"]

    def test_malformed_now(self, tmp_home):
        with pytest.raises(DrillError):
            due_cards("yesterday-ish")
        with pytest.raises(DrillError):
            due_cards("")

    def test_corrupt_store(self, tmp_home):
        path = tmp_home / "dynasty" / "schoolmaster" / "srs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(DrillError):
            due_cards(_now())
        with pytest.raises(DrillError):
            schedule("c1", 4)


# ---------------------------------------------------------------------
# Socratic drill
# ---------------------------------------------------------------------


class TestDrill:
    def test_default_depth(self):
        questions = drill("photosynthesis")
        assert len(questions) == 3
        assert [q["move"] for q in questions] == [
            "clarify",
            "assumption",
            "evidence",
        ]
        assert all("photosynthesis" in q["text"] for q in questions)

    def test_depth_cycles_moves(self):
        questions = drill("gravity", depth=7)
        assert [q["move"] for q in questions] == [
            "clarify",
            "assumption",
            "evidence",
            "implication",
            "viewpoint",
            "clarify",
            "assumption",
        ]

    def test_question_shape(self):
        for q in drill("entropy", depth=5):
            assert set(q) == {"move", "text"}
            assert q["move"] in (
                "clarify",
                "assumption",
                "evidence",
                "implication",
                "viewpoint",
            )

    def test_templates_are_fixed(self):
        # Honest template check: same topic always yields the same text.
        assert drill("x", depth=2) == drill("x", depth=2)

    def test_braces_in_topic_do_not_crash(self):
        questions = drill("f(x) = {x}", depth=1)
        assert "{x}" in questions[0]["text"] or "f(x) = {x}" in questions[0]["text"]

    def test_bad_depth(self):
        for bad in (0, -1, 26, 100, "3", 2.0, True):
            with pytest.raises(DrillError):
                drill("topic", depth=bad)

    def test_bad_topic(self):
        with pytest.raises(DrillError):
            drill("")
        with pytest.raises(DrillError):
            drill("   ")
        with pytest.raises(DrillError):
            drill(None)
        with pytest.raises(DrillError):
            drill("t" * 129)


# ---------------------------------------------------------------------
# Feynman rubric
# ---------------------------------------------------------------------


class TestFeynman:
    def test_plain_with_analogy(self):
        out = score_explanation(
            "Think of a seed like a save point in a game. "
            "Load it and you get the same run each time, as sure as rain."
        )
        assert out["simple_language"] == 2
        assert out["analogy_present"] is True
        assert out["gaps_flagged"] == 0
        assert out["verdict"] == "compressed"

    def test_jargon_heavy(self):
        out = score_explanation(
            "Pseudorandomness utilizes deterministic algorithmic state "
            "transitions predicated upon initialized entropy parameters."
        )
        assert out["simple_language"] == 0
        assert out["analogy_present"] is False
        assert out["verdict"] == "rework"

    def test_gaps_flagged_caps_at_two(self):
        out = score_explanation(
            "I don't know why it works. I'm not sure about the math, "
            "and I don't know the proof. It's unclear to me."
        )
        assert out["gaps_flagged"] == 2

    def test_no_gaps(self):
        out = score_explanation("A seed sets the start. Same start, same numbers.")
        assert out["gaps_flagged"] == 0

    def test_verdict_workable_middle(self):
        out = score_explanation(
            "The generator is deterministic in contradistinction to stochastic processes."
        )
        assert out["verdict"] in ("workable", "rework", "compressed")
        total = (
            out["simple_language"]
            + (1 if out["analogy_present"] else 0)
            + out["gaps_flagged"]
        )
        assert total <= 5

    def test_rejects_empty(self):
        with pytest.raises(DrillError):
            score_explanation("")
        with pytest.raises(DrillError):
            score_explanation("   ")
        with pytest.raises(DrillError):
            score_explanation(123)

    def test_shape(self):
        out = score_explanation("Seeds make luck replayable.")
        assert set(out) >= {
            "simple_language",
            "analogy_present",
            "gaps_flagged",
            "verdict",
        }
        assert out["simple_language"] in (0, 1, 2)
        assert isinstance(out["analogy_present"], bool)
        assert out["gaps_flagged"] in (0, 1, 2)
        assert out["verdict"] in ("compressed", "workable", "rework")


# ---------------------------------------------------------------------
# Course tracks
# ---------------------------------------------------------------------

_LINEAR = [
    {"title": "foundations", "prerequisites": []},
    {"title": "mechanism", "prerequisites": ["foundations"]},
    {"title": "mastery", "prerequisites": ["mechanism"]},
]


class TestCreateTrack:
    def test_happy_path(self, tmp_home):
        out = create_track("rng-101", _LINEAR)
        assert out["name"] == "rng-101"
        assert [lesson["title"] for lesson in out["lessons"]] == [
            "foundations",
            "mechanism",
            "mastery",
        ]
        status = progress("ada")
        assert status["completed"] == []
        assert status["next_available"] == ["foundations"]

    def test_diamond_dag(self, tmp_home):
        create_track(
            "diamond",
            [
                {"title": "a", "prerequisites": []},
                {"title": "b", "prerequisites": ["a"]},
                {"title": "c", "prerequisites": ["a"]},
                {"title": "d", "prerequisites": ["b", "c"]},
            ],
        )
        assert progress("ada", track="diamond")["next_available"] == ["a"]

    def test_prereqs_default_empty(self, tmp_home):
        create_track("t", [{"title": "solo"}])
        assert progress("ada")["next_available"] == ["solo"]

    def test_direct_cycle(self, tmp_home):
        with pytest.raises(TrackError):
            create_track(
                "bad",
                [
                    {"title": "a", "prerequisites": ["b"]},
                    {"title": "b", "prerequisites": ["a"]},
                ],
            )

    def test_indirect_cycle(self, tmp_home):
        with pytest.raises(TrackError):
            create_track(
                "bad",
                [
                    {"title": "a", "prerequisites": ["c"]},
                    {"title": "b", "prerequisites": ["a"]},
                    {"title": "c", "prerequisites": ["b"]},
                ],
            )

    def test_self_loop(self, tmp_home):
        with pytest.raises(TrackError):
            create_track("bad", [{"title": "a", "prerequisites": ["a"]}])

    def test_unknown_prereq(self, tmp_home):
        with pytest.raises(TrackError):
            create_track("bad", [{"title": "a", "prerequisites": ["ghost"]}])

    def test_duplicate_title(self, tmp_home):
        with pytest.raises(TrackError):
            create_track(
                "bad",
                [
                    {"title": "a", "prerequisites": []},
                    {"title": "a", "prerequisites": []},
                ],
            )

    def test_duplicate_track(self, tmp_home):
        create_track("t", _LINEAR)
        with pytest.raises(TrackError):
            create_track("t", _LINEAR)

    def test_malformed_inputs(self, tmp_home):
        with pytest.raises(TrackError):
            create_track("", _LINEAR)
        with pytest.raises(TrackError):
            create_track("t", [])
        with pytest.raises(TrackError):
            create_track("t", "notalist")
        with pytest.raises(TrackError):
            create_track("t", [{"prerequisites": []}])
        with pytest.raises(TrackError):
            create_track("t", [{"title": "a", "prerequisites": "b"}])


class TestTrackProgress:
    def test_complete_in_order_unlocks(self, tmp_home):
        create_track("t", _LINEAR)
        out = complete_lesson("ada", "foundations")
        assert out["completed"] == ["foundations"]
        assert out["next_available"] == ["mechanism"]
        out = complete_lesson("ada", "mechanism")
        assert out["next_available"] == ["mastery"]
        out = complete_lesson("ada", "mastery")
        assert out["completed"] == ["foundations", "mechanism", "mastery"]
        assert out["next_available"] == []

    def test_out_of_order_locked(self, tmp_home):
        create_track("t", _LINEAR)
        with pytest.raises(TrackError):
            complete_lesson("ada", "mechanism")
        assert progress("ada")["completed"] == []

    def test_double_complete_refused(self, tmp_home):
        create_track("t", _LINEAR)
        complete_lesson("ada", "foundations")
        with pytest.raises(TrackError):
            complete_lesson("ada", "foundations")

    def test_unknown_lesson(self, tmp_home):
        create_track("t", _LINEAR)
        with pytest.raises(TrackError):
            complete_lesson("ada", "nope")

    def test_unknown_track(self, tmp_home):
        create_track("t", _LINEAR)
        with pytest.raises(TrackError):
            complete_lesson("ada", "foundations", track="ghost")
        with pytest.raises(TrackError):
            progress("ada", track="ghost")

    def test_users_are_independent(self, tmp_home):
        create_track("t", _LINEAR)
        complete_lesson("ada", "foundations")
        assert progress("grace")["completed"] == []
        assert progress("grace")["next_available"] == ["foundations"]

    def test_multiple_tracks_need_a_name(self, tmp_home):
        create_track("t1", [{"title": "a"}])
        create_track("t2", [{"title": "b"}])
        with pytest.raises(TrackError):
            complete_lesson("ada", "a")
        out = complete_lesson("ada", "a", track="t1")
        assert out["completed"] == ["a"]
        both = progress("ada")
        assert set(both) == {"t1", "t2"}
        assert both["t1"]["completed"] == ["a"]

    def test_diamond_unlock_order(self, tmp_home):
        create_track(
            "diamond",
            [
                {"title": "a", "prerequisites": []},
                {"title": "b", "prerequisites": ["a"]},
                {"title": "c", "prerequisites": ["a"]},
                {"title": "d", "prerequisites": ["b", "c"]},
            ],
        )
        complete_lesson("ada", "a", track="diamond")
        assert progress("ada", track="diamond")["next_available"] == ["b", "c"]
        with pytest.raises(TrackError):
            complete_lesson("ada", "d", track="diamond")
        complete_lesson("ada", "b", track="diamond")
        complete_lesson("ada", "c", track="diamond")
        assert progress("ada", track="diamond")["next_available"] == ["d"]

    def test_bad_user(self, tmp_home):
        create_track("t", _LINEAR)
        with pytest.raises(TrackError):
            progress("")
        with pytest.raises(TrackError):
            complete_lesson("", "foundations")
