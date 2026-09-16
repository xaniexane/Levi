"""Tests for thread-sense state: threads, entities, pronouns, loops, facts."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from levi.convo.state import DialogueState


def _s():
    return DialogueState()


def test_topic_shift_creates_new_thread():
    s = _s()
    s.update("user", "I'm migrating our server this weekend, nginx needs reconfiguring")
    names_before = set(s.threads)
    assert len(names_before) == 1
    s.update("user", "Also I need a backup plan for the postgres database")
    assert len(s.threads) == 2, "topic shift should open a second thread"


def test_callback_reignites_old_thread():
    s = _s()
    s.update("user", "I'm migrating our server this weekend, nginx needs reconfiguring")
    s.update("user", "Also I need a backup plan for the postgres database")
    s.update("levi", "For postgres, nightly pg_dump to the backup drive works well.")
    # let the server thread decay over a couple of unrelated turns
    s.update("user", "How often should pg_dump run?")
    s.update("levi", "Nightly is fine for most workloads.")
    server = [
        t for t in s.threads.values() if "migrat" in t["name"] or "server" in t["name"]
    ]
    assert server, "server thread should exist"
    before = server[0]["salience"]
    changed = s.update("user", "back to the server thing — when is the migration?")
    assert changed.get("reignited"), "callback should reignite, got %r" % changed
    assert server[0]["salience"] == 1.0 and server[0]["salience"] >= before


def test_entity_tracked_across_turns_with_pronoun_resolution():
    s = _s()
    s.update("user", "The Nginx config is getting complicated")
    s.update("levi", "Nginx configs do tend to grow wild.")
    changed = s.update("user", "Can you restart it after the change?")
    assert changed.get("resolved"), "pronoun should resolve, got %r" % changed
    assert changed["resolved"]["entity"] == "Nginx", changed["resolved"]


def test_open_loop_opens_and_closes():
    s = _s()
    s.update("levi", "I'll check the drive space before the weekend.")
    loops = s.open_loops()
    assert len(loops) == 1 and loops[0]["kind"] == "promise"
    s.update("user", "thanks")
    assert len(s.open_loops()) == 1, "unrelated turn must not close the loop"
    s.update("levi", "Drive space is fine — 42GB free, the migration can proceed.")
    assert len(s.open_loops()) == 0, "delivering the substance should close the loop"


def test_question_loop_opens():
    s = _s()
    s.update("levi", "What time is the migration window on Saturday?")
    assert any(loop["kind"] == "question" for loop in s.open_loops())


def test_facts_recorded_from_levi_claims():
    s = _s()
    s.update("levi", "Yes — nginx runs on port 8080.")
    assert any("8080" in f["text"] for f in s.facts)


def test_state_round_trip():
    s = _s()
    s.update("user", "migrating the server, nginx needs reconfiguring")
    s.update("levi", "I'll check the drive space first.")
    d = s.to_dict()
    s2 = DialogueState.from_dict(d)
    assert s2.turn_count == s.turn_count
    assert set(s2.threads) == set(s.threads)
    assert len(s2.open_loops()) == len(s.open_loops())


def test_update_never_raises_on_weird_input():
    s = _s()
    s.update("user", "")
    s.update("user", "!!! ??? ...")
    s.update("???", "nonsense speaker still fine")
    assert s.turn_count == 3
