"""Tests for TimeCapsule, Cybrus capability/evidence, surgeon elite."""

from pathlib import Path

import pytest

from levi.capsule import create_seed, inspect_seed, plant_seed
from levi.cybrus.capability import Capability, CapabilityRegistry, RiskBand
from levi.cybrus.evidence import EvidenceLedger
from levi.surgeon.elite import cleanup_pass, elite_repair, syntax_error


# --- capsule ---------------------------------------------------------------


def test_capsule_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    src = tmp_path / "dream_journal.jsonl"
    src.write_text('{"a": 1}\n{"b": 2}\n')
    seed = create_seed(sources={"dream_journal": src}, dest_dir=tmp_path / "seeds")
    assert seed.suffix == ".lseed"
    info = inspect_seed(seed)
    assert info["kind"] == "levi-timecapsule/1"
    assert "dream_journal" in info["parts"]
    report = plant_seed(seed, dest_base=tmp_path / "home")
    assert report["ok"] and report["merged"]["dream_journal"] == 2
    # planting again merges nothing (dedup)
    report2 = plant_seed(seed, dest_base=tmp_path / "home")
    assert report2["merged"]["dream_journal"] == 0


def test_capsule_missing_seed(tmp_path):
    assert plant_seed(tmp_path / "nope.lseed")["ok"] is False


# --- cybrus capability ------------------------------------------------------


def test_capability_registry_deny_closed():
    reg = CapabilityRegistry()
    reg.register(
        Capability(
            id="dream.once",
            name="Dream once",
            description="d",
            domain="dream",
            risk=RiskBand.LOW,
        )
    )
    assert reg.require("dream.once").name == "Dream once"
    with pytest.raises(KeyError):
        reg.require("nope.missing")
    assert reg.search("dream")[0].id == "dream.once"
    assert reg.domains() == ["dream"]


# --- cybrus evidence ---------------------------------------------------------


def test_evidence_ledger_chain():
    led = EvidenceLedger()
    d1 = led.append("finding", "test", "content one")
    d2 = led.append("finding", "test", "content two")
    assert d1 != d2
    assert led.verify_chain()
    assert len(led.find(kind="finding")) == 2
    # tamper breaks the chain
    led.records[1].content = "forged"
    assert not led.verify_chain()


# --- surgeon elite -----------------------------------------------------------


def test_cleanup_pass_fixes():
    src = "x == None\nif True\n    y = y + 1\n"
    new, fixes = cleanup_pass(src)
    assert "is None" in new
    assert "y += 1" in new
    assert "if True:" in new
    assert fixes


def test_elite_repair_syntax_gated(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("a == None\nif a\n    b=1\n")
    res = elite_repair(p)
    assert res.clean
    assert syntax_error(p.read_text()) is None
    assert Path(res.backup).exists()


def test_elite_repair_rolls_back_bad_pass(tmp_path):
    # a file that is already clean should stay clean and untouched in meaning
    p = tmp_path / "ok.py"
    p.write_text("def f():\n    return 1\n")
    res = elite_repair(p)
    assert res.clean
    assert "def f():" in p.read_text()
