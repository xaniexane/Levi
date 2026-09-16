"""Tests for the LEVI doors contract (drop files, turn ledger, oracle).

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path.
No network, no sleeps.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import date

import pytest

from levi.doors import doors


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


TODAY = date(2026, 9, 16)
TOMORROW = date(2026, 9, 17)


# ---------------------------------------------------------------- drop files


def test_drop_roundtrip(home):
    path = home / "drops" / "node1.drop"
    path.parent.mkdir()
    out = doors.write_drop(
        path,
        node="node1",
        handle="chauncey",
        time_left_s=600,
        level=5,
        door="oracle",
        extra={"quest": "x"},
    )
    doc = doors.read_drop(out)
    assert doc["format"] == doors.DROP_FORMAT
    assert doc["node"] == "node1"
    assert doc["handle"] == "chauncey"
    assert doc["time_left_s"] == 600
    assert doc["level"] == 5
    assert doc["door"] == "oracle"
    assert doc["extra"] == {"quest": "x"}
    assert doc["issued_at"]  # UTC ISO timestamp present


def test_read_drop_rejects_wrong_format(home):
    path = home / "bad.drop"
    path.write_text(json.dumps({"format": "DOOR.SYS", "handle": "x"}))
    with pytest.raises(ValueError):
        doors.read_drop(path)


def test_read_drop_rejects_missing_keys(home):
    path = home / "thin.drop"
    path.write_text(json.dumps({"format": doors.DROP_FORMAT, "node": "n"}))
    with pytest.raises(ValueError):
        doors.read_drop(path)


def test_drop_file_is_owner_only(home):
    path = home / "perm.drop"
    doors.write_drop(
        path, node="n", handle="h", time_left_s=60, level=1, door="oracle"
    )
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


# ------------------------------------------------- daily-turn scarcity


def test_ledger_grants_per_day_then_refuses(home):
    ledger = doors.TurnLedger()
    assert ledger.turns_left("p", "oracle", 2, today=TODAY) == 2
    assert ledger.spend_turn("p", "oracle", 2, today=TODAY) is True
    assert ledger.turns_left("p", "oracle", 2, today=TODAY) == 1
    assert ledger.spend_turn("p", "oracle", 2, today=TODAY) is True
    assert ledger.turns_left("p", "oracle", 2, today=TODAY) == 0
    assert ledger.spend_turn("p", "oracle", 2, today=TODAY) is False


def test_ledger_resets_on_next_utc_day(home):
    ledger = doors.TurnLedger()
    for _ in range(2):
        assert ledger.spend_turn("p", "oracle", 2, today=TODAY) is True
    assert ledger.turns_left("p", "oracle", 2, today=TODAY) == 0
    # UTC midnight: fresh budget
    assert ledger.turns_left("p", "oracle", 2, today=TOMORROW) == 2
    assert ledger.spend_turn("p", "oracle", 2, today=TOMORROW) is True


def test_ledger_tracks_players_and_doors_separately(home):
    ledger = doors.TurnLedger()
    assert ledger.spend_turn("p1", "oracle", 1, today=TODAY) is True
    assert ledger.turns_left("p1", "oracle", 1, today=TODAY) == 0
    assert ledger.turns_left("p2", "oracle", 1, today=TODAY) == 1
    assert ledger.turns_left("p1", "other", 1, today=TODAY) == 1


def test_ledger_rejects_bad_per_day(home):
    ledger = doors.TurnLedger()
    with pytest.raises(ValueError):
        ledger.turns_left("p", "oracle", 0, today=TODAY)
    with pytest.raises(ValueError):
        ledger.spend_turn("p", "oracle", -3, today=TODAY)


def test_ledger_state_file_is_owner_only(home):
    ledger = doors.TurnLedger()
    ledger.spend_turn("p", "oracle", 3, today=TODAY)
    mode = stat.S_IMODE(os.stat(ledger.path).st_mode)
    assert mode == 0o600


# ------------------------------------------------------- sample door


def test_oracle_deterministic_same_day_same_handle(home):
    r1 = doors.play_oracle("chauncey", 50, per_day=10, today=TODAY)
    r2 = doors.play_oracle("chauncey", 50, per_day=10, today=TODAY)
    assert r1["outcome"] == r2["outcome"]
    # and matches the documented hash recipe
    assert r1["outcome"] in ("higher", "lower", "correct")


def test_oracle_higher_lower_correct(home):
    target = doors.oracle_target("hermetic", TODAY)
    low = doors.play_oracle("hermetic", 1, per_day=10, today=TODAY)
    assert low["outcome"] == ("correct" if target == 1 else "higher")
    high = doors.play_oracle("hermetic", 100, per_day=10, today=TODAY)
    assert high["outcome"] == ("correct" if target == 100 else "lower")
    hit = doors.play_oracle("hermetic", target, per_day=10, today=TODAY)
    assert hit["outcome"] == "correct"


def test_oracle_prompt_spends_no_turn(home):
    res = doors.play_oracle("peeker", None, per_day=3, today=TODAY)
    assert res == {"outcome": "prompt", "range": [1, 100], "turns_left": 3}
    ledger = doors.TurnLedger()
    assert ledger.turns_left("peeker", "oracle", 3, today=TODAY) == 3


def test_oracle_no_turns_after_per_day_spends(home):
    for i in range(3):
        res = doors.play_oracle("greedy", 50, per_day=3, today=TODAY)
        assert res["outcome"] in ("higher", "lower", "correct")
        assert res["turns_left"] == 2 - i
    res = doors.play_oracle("greedy", 50, per_day=3, today=TODAY)
    assert res == {"outcome": "no-turns", "turns_left": 0}


def test_oracle_bad_guess_raises(home):
    with pytest.raises(ValueError):
        doors.play_oracle("p", 0, per_day=3, today=TODAY)
    with pytest.raises(ValueError):
        doors.play_oracle("p", 101, per_day=3, today=TODAY)
    # a rejected guess spends nothing
    ledger = doors.TurnLedger()
    assert ledger.turns_left("p", "oracle", 3, today=TODAY) == 3
