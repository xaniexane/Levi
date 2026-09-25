"""Tests for the append-only tag-team round ledger."""

import json

import pytest

from levi.brain.tagteam import ledger


def _entry(round_n, **kw):
    return ledger.new_entry(round_n, **kw)


def test_new_entry_sets_schema_round_ts():
    e = _entry(3, stages={})
    assert e["schema"] == ledger.SCHEMA
    assert e["round"] == 3
    assert e["ts"]


def test_append_and_read_roundtrip(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    ledger.append_entry(lp, _entry(1, stages={"a": 1}))
    ledger.append_entry(lp, _entry(2, stages={"a": 2}))
    entries = ledger.read_entries(lp)
    assert [e["round"] for e in entries] == [1, 2]
    # append-only: two lines, never rewritten
    assert len(lp.read_text(encoding="utf-8").strip().split("\n")) == 2


def test_read_missing_ledger_is_empty(tmp_path):
    assert ledger.read_entries(tmp_path / "nope.jsonl") == []
    assert ledger.last_entry(tmp_path / "nope.jsonl") is None


def test_read_corrupt_ledger_raises(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    lp.write_text('{"round": 1}\nNOT JSON\n', encoding="utf-8")
    with pytest.raises(ValueError, match="ledger corrupt at line 2"):
        ledger.read_entries(lp)


def test_append_rejects_wrong_schema_or_missing_fields(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="wrong schema"):
        ledger.append_entry(lp, {"schema": "bogus", "round": 1, "ts": "x"})
    with pytest.raises(ValueError, match="'round' and 'ts'"):
        ledger.append_entry(lp, {"schema": ledger.SCHEMA})


def test_last_entry_prev_scores_and_teacher_history(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    ledger.append_entry(
        lp,
        _entry(
            1,
            eval={"ran": True, "scores": {"arith-1": 0.8}},
            teacher_history={"arithmetic": ["qwen", "grok"]},
        ),
    )
    ledger.append_entry(lp, _entry(2, eval={"ran": False}))
    assert ledger.last_entry(lp)["round"] == 2
    # prev_scores walks back past the scoreless round
    assert ledger.prev_scores(lp) == {"arith-1": 0.8}
    assert ledger.teacher_history(lp) == {"arithmetic": ["qwen", "grok"]}


def test_prev_scores_empty_when_nothing_scored(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    ledger.append_entry(lp, _entry(1, eval={"ran": False}))
    assert ledger.prev_scores(lp) == {}
    assert ledger.teacher_history(lp) == {}
