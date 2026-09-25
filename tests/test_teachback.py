"""Hermetic tests for ``levi.teachback`` — teach-back goal model.

Tmp LEVI_HOME, no network, no real ``~/.levi``.

Run:  python3 -m pytest tests/test_teachback.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.teachback import (  # noqa: E402
    TeachbackModel,
    add_statement,
    affirm,
    correct,
    model,
    note_evidence,
    render_brief,
)


@pytest.fixture()
def tm(tmp_path, monkeypatch):
    h = tmp_path / "levi_home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return TeachbackModel()


def test_empty_model_is_honest(tm):
    assert tm.model() == []
    brief = tm.render_brief()
    assert "don't have a model" in brief


def test_add_and_render_brief(tm):
    tm.add_statement("ship", "Ship the Levi book by year end", confidence=0.7)
    tm.add_statement("fit", "Stay fit with morning runs", confidence=0.6)
    rows = tm.model()
    assert [r["id"] for r in rows] == ["fit", "ship"]
    brief = tm.render_brief()
    assert "what I believe your goals are" in brief
    assert "Ship the Levi book" in brief
    assert "0.70" in brief
    with pytest.raises(ValueError):
        tm.add_statement("ship", "duplicate")


def test_correction_updates_model_and_lowers_confidence(tm):
    tm.add_statement("ship", "Ship the book by year end", confidence=0.7)
    doc = tm.correct("ship", "Ship the book — deadline moved to March")
    assert doc["statement"] == "Ship the book — deadline moved to March"
    assert doc["confidence"] < 0.7
    assert abs(doc["confidence"] - 0.55) < 1e-9
    assert doc["corrections"] == 1
    kinds = [h["kind"] for h in tm.history("ship")]
    assert "add" in kinds and "correct" in kinds
    # History preserves the original wording for audit.
    correct_entry = next(h for h in tm.history("ship") if h["kind"] == "correct")
    assert correct_entry["old"] == "Ship the book by year end"
    assert correct_entry["new"] == "Ship the book — deadline moved to March"


def test_confidence_never_below_floor(tm):
    tm.add_statement("x", "weak belief", confidence=0.1)
    doc = tm.correct("x", "corrected once")
    assert doc["confidence"] == 0.05
    doc = tm.correct("x", "corrected twice")
    assert doc["confidence"] == 0.05  # floor holds


def test_affirm_raises_confidence(tm):
    tm.add_statement("fit", "Stay fit", confidence=0.5)
    doc = tm.affirm("fit")
    assert abs(doc["confidence"] - 0.6) < 1e-9
    doc2 = tm.affirm("fit")
    assert doc2["confidence"] > doc["confidence"]
    assert "affirm" in [h["kind"] for h in tm.history("fit")]


def test_evidence_bumps_counter_and_confidence_not_certainty(tm):
    tm.add_statement("fit", "Stay fit", confidence=0.9)
    doc = tm.note_evidence("fit", "ran 5k on Tuesday")
    assert doc["evidence_count"] == 1
    assert doc["confidence"] < 1.0  # evidence alone never reaches certainty
    assert abs(doc["confidence"] - 0.95) < 1e-9  # 0.95 cap
    doc = tm.note_evidence("fit", "ran again Thursday")
    assert doc["evidence_count"] == 2
    assert doc["confidence"] == 0.95


def test_correction_moves_confidence_in_right_direction(tm):
    # Regression guard: correction must LOWER, affirm RAISE, evidence RAISE
    # — never the reverse.
    tm.add_statement("a", "belief a", confidence=0.6)
    tm.add_statement("b", "belief b", confidence=0.6)
    tm.add_statement("c", "belief c", confidence=0.6)
    assert tm.correct("a", "fixed a")["confidence"] < 0.6
    assert tm.affirm("b")["confidence"] > 0.6
    assert tm.note_evidence("c", "saw it happen")["confidence"] > 0.6


def test_unknown_ids_raise(tm):
    with pytest.raises(KeyError):
        tm.correct("nope", "x")
    with pytest.raises(KeyError):
        tm.affirm("nope")
    with pytest.raises(KeyError):
        tm.note_evidence("nope", "x")
    with pytest.raises(KeyError):
        tm.history("nope")


def test_module_level_wrappers(tm):
    add_statement("m1", "module-level add")
    rows = model()
    assert len(rows) == 1 and rows[0]["id"] == "m1"
    correct("m1", "module-level correction")
    assert model()[0]["corrections"] == 1
    affirm("m1")
    note_evidence("m1", "seen in the wild")
    brief = render_brief()
    assert "module-level correction" in brief
    assert "evidence: 1" in brief


def test_history_preserved_across_reload(tmp_path, monkeypatch):
    h = tmp_path / "levi_home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    TeachbackModel().add_statement("s", "v1", confidence=0.5)
    TeachbackModel().correct("s", "v2")
    fresh = TeachbackModel()
    assert len(fresh.history("s")) == 2
    assert fresh.model()[0]["statement"] == "v2"
