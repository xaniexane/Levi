"""Tests for the verdict ledger (append-only hash-chained audit log)."""

import json
from pathlib import Path

import pytest

from levi.automation.verdict_ledger import (
    GENESIS_HASH,
    LedgerError,
    VerdictLedger,
)


def sample_verdict(ruling="upheld", prevailing="ship"):
    return {"ruling": ruling, "prevailing": prevailing, "engine_id": "gavel"}


def test_record_appends_with_dense_seq():
    ledger = VerdictLedger()
    first = ledger.record(sample_verdict(), source="gavel")
    second = ledger.record(sample_verdict("split", None), source="gavel")
    assert first.seq == 0
    assert second.seq == 1
    assert len(ledger) == 2


def test_genesis_links_to_genesis_hash():
    ledger = VerdictLedger()
    entry = ledger.record(sample_verdict())
    assert entry.prev_hash == GENESIS_HASH


def test_chain_links_each_entry_to_previous():
    ledger = VerdictLedger()
    first = ledger.record(sample_verdict())
    second = ledger.record(sample_verdict())
    assert second.prev_hash == first.entry_hash


def test_verify_clean_ledger():
    ledger = VerdictLedger()
    for _ in range(5):
        ledger.record(sample_verdict())
    ok, problems = ledger.verify()
    assert ok is True
    assert problems == []


def test_verify_empty_ledger_ok():
    ok, problems = VerdictLedger().verify()
    assert ok is True
    assert problems == []


def test_tampering_breaks_verification(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    ledger = VerdictLedger(path=path)
    ledger.record(sample_verdict())
    ledger.record(sample_verdict("overturned", "hold"))

    # Tamper with the stored file: change a verdict in entry 0.
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    raw = json.loads(lines[0])
    raw["verdict"]["ruling"] = "forged"
    lines[0] = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(LedgerError, match="corrupt"):
        VerdictLedger(path=path)


def test_non_dict_verdict_refused():
    ledger = VerdictLedger()
    with pytest.raises(LedgerError):
        ledger.record(["not", "a", "dict"])


def test_non_serializable_verdict_refused():
    ledger = VerdictLedger()
    with pytest.raises(LedgerError):
        ledger.record({"ruling": object()})


def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    ledger = VerdictLedger(path=path)
    ledger.record(sample_verdict(), source="gavel")
    ledger.record(sample_verdict("remanded", None), source="gavel")

    reopened = VerdictLedger(path=path)
    assert len(reopened) == 2
    assert reopened.get(0).verdict["ruling"] == "upheld"
    assert reopened.get(1).verdict["prevailing"] is None
    ok, _ = reopened.verify()
    assert ok is True


def test_get_out_of_range_refused():
    ledger = VerdictLedger()
    ledger.record(sample_verdict())
    with pytest.raises(LedgerError):
        ledger.get(7)


def test_tail_returns_last_n():
    ledger = VerdictLedger()
    for i in range(5):
        ledger.record(sample_verdict(prevailing=f"claim-{i}"))
    tail = ledger.tail(2)
    assert [e.seq for e in tail] == [3, 4]
    assert ledger.tail(0) == []


def test_find_by_ruling():
    ledger = VerdictLedger()
    ledger.record(sample_verdict("upheld", "ship"))
    ledger.record(sample_verdict("split", None))
    ledger.record(sample_verdict("upheld", "hold"))
    found = ledger.find("upheld")
    assert [e.verdict["prevailing"] for e in found] == ["ship", "hold"]


def test_hash_scheme_is_deterministic():
    from levi.automation.verdict_ledger import _entry_hash

    verdict = sample_verdict()
    args = (0, "2026-09-25T00:00:00+00:00", "gavel", verdict, GENESIS_HASH)
    first = _entry_hash(*args)
    second = _entry_hash(*args)
    assert first == second
    assert len(first) == 64


def test_entry_is_immutable():
    import dataclasses

    ledger = VerdictLedger()
    entry = ledger.record(sample_verdict())
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.seq = 99  # frozen dataclass: no mutation


def test_no_edit_or_delete_api_exists():
    ledger = VerdictLedger()
    for name in ("edit", "update", "delete", "remove", "pop", "clear"):
        assert not hasattr(ledger, name), f"ledger must not expose {name}"


def test_malformed_file_refused(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="not valid JSON"):
        VerdictLedger(path=str(path))
