"""Tests for wave-006 verify additions: bulla chains and trial balances."""

import json

import pytest

from levi.verify import append_record, trial_balance, verify_chain
from levi.verify.bulla import GENESIS_PREV


def _chain(payloads):
    lines = []
    prev = ""
    for p in payloads:
        line = append_record(prev, p)
        lines.append(line)
        prev = line
    return lines


def test_chain_intact():
    lines = _chain([{"a": 1}, {"b": 2}, {"c": 3}])
    ok, problems = verify_chain(lines)
    assert ok and problems == []


def test_genesis_prev_hash():
    line = append_record("", {"a": 1})
    assert json.loads(line)["prev_hash"] == GENESIS_PREV


def test_edit_detected():
    lines = _chain([{"a": 1}, {"b": 2}])
    tampered = json.loads(lines[1])
    tampered["payload"] = {"b": 999}
    lines[1] = json.dumps(tampered)
    ok, problems = verify_chain(lines)
    assert not ok and any("edited" in p for p in problems)


def test_gap_detected():
    lines = _chain([{"a": 1}, {"b": 2}, {"c": 3}])
    del lines[1]
    ok, problems = verify_chain(lines)
    assert not ok and any("breaks the chain" in p for p in problems)


def test_reorder_detected():
    lines = _chain([{"a": 1}, {"b": 2}])
    lines.reverse()
    ok, _ = verify_chain(lines)
    assert not ok


def test_malformed_line():
    ok, problems = verify_chain(['{"not": "a bulla"}'])
    assert not ok and problems


def test_empty_chain_ok():
    assert verify_chain([]) == (True, [])


def test_trial_balance_ok():
    journal = {"j1": "x", "j2": "y", "j3": "z"}
    index = {"t1": ["j1", "j2"], "t2": ["j2", "j3"]}
    tb = trial_balance(journal, index)
    assert tb.ok and tb.journal_count == 3 and tb.index_count == 3


def test_journal_orphan():
    tb = trial_balance({"j1": 1, "j2": 2}, {"t": ["j1"]})
    assert not tb.ok and tb.journal_orphans == ["j2"]


def test_index_orphan():
    tb = trial_balance({"j1": 1}, {"t": ["j1", "ghost"]})
    assert not tb.ok and tb.index_orphans == ["ghost"]


def test_empty_balances():
    assert trial_balance({}, {}).ok


def test_bad_inputs():
    with pytest.raises(TypeError):
        trial_balance([1, 2], {})
    with pytest.raises(TypeError):
        trial_balance({}, {"t": "j1"})
