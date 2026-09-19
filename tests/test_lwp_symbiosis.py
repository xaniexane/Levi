"""Tests for levi.lwp.symbiosis — Symbiotic Residue Ledger (hermetic)."""

import json
from pathlib import Path

import pytest

from levi.lwp.symbiosis import SymbioticLedger


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYMBIOSIS_DIR", str(tmp_path / "sym"))
    return SymbioticLedger()


def test_lock_and_current(ledger):
    r = ledger.lock("tone", "calm, no theater", {"scope": "chat"})
    assert r.version == 1
    cur = ledger.current("tone")
    assert cur is not None and cur.body["decision"] == "calm, no theater"


def test_lock_versions_never_rewritten(ledger):
    ledger.lock("tone", "v1")
    ledger.lock("tone", "v2")
    assert ledger.current("tone").body["decision"] == "v2"
    locks = [r for r in ledger.history("tone") if r.kind == "lock"]
    assert [r.version for r in locks] == [1, 2]


def test_supersede_keeps_phantom(ledger):
    ledger.lock("tone", "loud and hypey")
    new = ledger.supersede("tone", "calm, no theater", reason="keeper correction")
    assert new.body["decision"] == "calm, no theater"
    phantoms = ledger.phantoms("tone")
    assert len(phantoms) == 1
    assert phantoms[0].body["erased_decision"] == "loud and hypey"
    assert phantoms[0].body["reason"] == "keeper correction"


def test_supersede_without_lock_raises(ledger):
    with pytest.raises(KeyError):
        ledger.supersede("nope", "x", "why")


def test_compost_record_shape(ledger):
    r = ledger.compost(
        "draft-1",
        "tried purple prose",
        "purple prose failed the gate",
        retry_hint="plain diction",
    )
    assert r.kind == "compost"
    assert r.body["lesson_kind"] == "correction"
    assert "plain diction" in r.body["retry_hint"]


def test_pollen_keeps_only_scalars(ledger):
    r = ledger.pollen(
        "peer-a", {"avg_sentence_len": 14.2, "text": "SECRET DRAFT", "tags": ["x"]}
    )
    fp = r.body["fingerprint"]
    assert fp["avg_sentence_len"] == 14.2
    assert "text" not in fp and "tags" not in fp  # no manuscript data


def test_history_and_by_kind(ledger):
    ledger.lock("a", "1")
    ledger.compost("b", "fail", "analysis")
    ledger.pollen("c", {"w": 1.0})
    assert {r.key for r in ledger.history("a")} == {"a"}
    assert len(ledger.by_kind("lock")) == 1
    with pytest.raises(ValueError):
        ledger.by_kind("bogus")


def test_export_json_roundtrip(ledger):
    ledger.lock("a", "1")
    data = json.loads(ledger.export_json())
    assert data[0]["key"] == "a"


def test_unsafe_key_rejected(ledger):
    with pytest.raises(ValueError):
        ledger.lock("../evil", "x")
    with pytest.raises(ValueError):
        ledger.lock("", "x")


def test_default_dir_honors_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYMBIOSIS_DIR", str(tmp_path / "custom"))
    lg = SymbioticLedger()
    lg.lock("k", "v")
    assert (tmp_path / "custom" / "symbiosis.jsonl").exists()
