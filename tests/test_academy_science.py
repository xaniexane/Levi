"""Academy learning-science tests — home-scoped, deterministic, no network."""

from __future__ import annotations

import pytest

from levi.academy import science


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# --- retrieval practice ----------------------------------------------------------

def test_retrieval_recall_scoring(home):
    d = science.create_retrieval_drill("ada", "hashing",
                                       ["SHA-256 produces a 256-bit digest",
                                        "Digests verify integrity by recomputation"])
    assert "No notes" in d["prompt"] and d["fact_count"] == 2
    full = science.score_recall("ada", d["drill_id"],
                                "SHA-256 produces a 256-bit digest. Digests verify "
                                "integrity by recomputation of the data.")
    assert full["coverage"] == 1.0 and full["passed"] is True
    none = science.score_recall("ada", d["drill_id"], "I remember nothing about fish.")
    assert none["coverage"] == 0.0 and none["passed"] is False
    with pytest.raises(KeyError):
        science.score_recall("ada", "nope", "x")


# --- elaboration -------------------------------------------------------------------

def test_elaboration_scoring(home):
    p = science.elaboration_prompt("encryption", "key management")
    assert "mechanism" in p["prompt"]
    good = ("Encryption connects to key management because the strongest cipher "
            "fails when keys leak; therefore key rotation and storage are the "
            "real security boundary.")
    g = science.score_elaboration(good, "encryption", "key management")
    assert g["score"] == 1.0 and g["passed"] is True
    thin = "Encryption and key management are related topics in security."
    g2 = science.score_elaboration(thin, "encryption", "key management")
    assert g2["score"] == round(2 / 3, 3) and g2["passed"] is True  # no causal language
    missing = "Encryption is neat."
    g3 = science.score_elaboration(missing, "encryption", "key management")
    assert g3["passed"] is False


# --- dual coding ---------------------------------------------------------------------

def test_dual_code_scoring(home):
    verbal = ("A hash function maps arbitrary input to a fixed-size digest. "
              "It is one-way: the digest reveals nothing usable about the input.")
    diagram = "[input] -> [SHA-256] -> [digest]\n[digest] -> [compare] -> [integrity?]"
    g = science.score_dual_code(verbal, diagram)
    assert g["passed"] is True and g["labeled_lines"] >= 2
    bad_diagram = "hashing is cool\ntrust me"
    g2 = science.score_dual_code(verbal, bad_diagram)
    assert g2["passed"] is False


# --- desirable difficulty ----------------------------------------------------------------

def test_difficulty_escalation(home):
    assert science.recommend_tier("ada", "hashing") == "guided"
    science.record_tier_attempt("ada", "hashing", "guided", True)
    assert science.recommend_tier("ada", "hashing") == "guided"  # one pass: stay
    science.record_tier_attempt("ada", "hashing", "guided", True)
    assert science.recommend_tier("ada", "hashing") == "unassisted"  # two: escalate
    science.record_tier_attempt("ada", "hashing", "unassisted", True)
    science.record_tier_attempt("ada", "hashing", "unassisted", True)
    assert science.recommend_tier("ada", "hashing") == "degraded"
    science.record_tier_attempt("ada", "hashing", "degraded", False)
    assert science.recommend_tier("ada", "hashing") == "unassisted"  # fail steps down
    with pytest.raises(ValueError):
        science.record_tier_attempt("ada", "hashing", "nightmare", True)


def test_difficulty_tiers_described(home):
    t = science.difficulty_tiers("hashing")
    assert [x["tier"] for x in t["tiers"]] == ["guided", "unassisted", "degraded"]


# --- metacognition ------------------------------------------------------------------------

def test_metacognition_grading(home):
    science.rate_confidence("ada", "a1", 1.0)
    science.resolve_answer("ada", "a1", True)    # perfect confidence, right
    science.rate_confidence("ada", "a2", 0.0)
    science.resolve_answer("ada", "a2", False)   # perfect humility, right call
    rep = science.metacognition_report("ada")
    assert rep["brier"] == 0.0 and rep["grade"] == "A" and rep["n"] == 2


def test_metacognition_poor_calibration(home):
    science.rate_confidence("ada", "a1", 1.0)
    science.resolve_answer("ada", "a1", False)   # certain and wrong
    rep = science.metacognition_report("ada")
    assert rep["brier"] == 1.0 and rep["grade"] == "F"


def test_metacognition_guards(home):
    with pytest.raises(ValueError):
        science.rate_confidence("ada", "a1", 1.5)
    science.rate_confidence("ada", "a1", 0.5)
    with pytest.raises(ValueError):
        science.rate_confidence("ada", "a1", 0.5)  # open rating exists
    with pytest.raises(KeyError):
        science.resolve_answer("ada", "ghost", True)
    rep = science.metacognition_report("nobody")
    assert rep["n"] == 0 and rep["grade"] is None
