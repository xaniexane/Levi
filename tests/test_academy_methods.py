"""Academy methods tests — home-scoped, deterministic, no network."""

from __future__ import annotations

import pytest

from levi.academy import methods
from levi.academy.differentiators import compost, decay


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# --- spaced repetition ---------------------------------------------------------

def test_next_review_layers_on_decay(home):
    now = 1_700_000_000.0
    # unseen skill: due now
    r = methods.next_review("ada", "threat-intel:objective-0", home=home, now=now)
    assert r["review_in_days"] == 0.0 and r["current_strength"] == 0.0
    assert "due now" in r["note"]
    # freshly touched: review lands just before the 0.8 threshold
    decay.touch_skill("ada", "threat-intel:objective-0", home=home, now=now)
    r = methods.next_review("ada", "threat-intel:objective-0", home=home, now=now)
    assert r["current_strength"] == 1.0
    assert 9.6 < r["review_in_days"] < 9.7  # 30 * log2(1/0.8)
    with pytest.raises(ValueError):
        methods.next_review("ada", "s", threshold=1.5)


# --- interleaving ---------------------------------------------------------------

def test_interleave_round_robin(home):
    session = methods.interleave([
        {"subject_id": "a", "items": ["a1", "a2"]},
        {"subject_id": "b", "items": ["b1", "b2"]},
    ], per_subject=2)
    assert [(s["subject_id"], s["item"]) for s in session] == [
        ("a", "a1"), ("b", "b1"), ("a", "a2"), ("b", "b2")]
    assert [s["position"] for s in session] == [0, 1, 2, 3]
    with pytest.raises(ValueError):
        methods.interleave([])
    with pytest.raises(ValueError):
        methods.interleave([{"subject_id": "a", "items": []}])


# --- Feynman drills ---------------------------------------------------------------

def test_feynman_grade_pass_and_fail(home):
    drill = methods.feynman_drill("hashing", ["hashing maps data to fixed digests",
                                              "digests verify integrity"])
    assert "Teach" in drill["prompt"]
    good = ("Hashing maps data to fixed digests. You use digests to verify "
            "integrity: recompute and compare.")
    g = methods.grade_explanation(good, drill["key_points"])
    assert g["passed"] is True and g["score"] >= 0.6
    bad = methods.grade_explanation("I like cryptography a lot, it is neat.",
                                    drill["key_points"])
    assert bad["passed"] is False
    with pytest.raises(ValueError):
        methods.grade_explanation("   ", drill["key_points"])


# --- shadow mode --------------------------------------------------------------------

def test_shadow_observe_takeover_pass(home):
    a = methods.shadow_assignment("ada", "grad-7")
    assert a["phase"] == "observing"
    with pytest.raises(ValueError):
        methods.complete_observation("ada", a["shadow_id"], "watched")  # too short
    methods.complete_observation(
        "ada", a["shadow_id"],
        "Watched the graduate sort the alert queue: header kept first, body sorted.")
    out = methods.takeover("ada", a["shadow_id"], {"lines": ["b", "a"]})
    assert out["phase"] == "takeover_passed"
    assert out["receipt_id"]


def test_shadow_takeover_fail_composts(home):
    a = methods.shadow_assignment("ada", "grad-7")
    methods.complete_observation("ada", a["shadow_id"],
                                 "Watched closely and took detailed notes here.")
    out = methods.takeover("ada", a["shadow_id"], {"wrong": "payload"})
    assert out["phase"] == "takeover_failed"
    assert out["compost_drill_id"]
    drills = compost.list_drills("ada")
    assert any(d["drill_id"] == out["compost_drill_id"] for d in drills)
    with pytest.raises(ValueError):
        methods.takeover("ada", a["shadow_id"], {"lines": ["a"]})  # already resolved


def test_takeover_requires_observation(home):
    a = methods.shadow_assignment("ada", "grad-7")
    with pytest.raises(ValueError):
        methods.takeover("ada", a["shadow_id"], {"lines": ["a"]})


# --- pressure drills ------------------------------------------------------------------

def test_pressure_pass(home):
    d = methods.pressure_drill("ir-1", "Ransomware on a file server. First 3 actions?",
                               60.0, ["isolate", "backup", "notify"])
    out = methods.submit_pressure("ada", d["drill_id"],
                                  "Isolate the host, check backup integrity, notify the IR lead.",
                                  42.0)
    assert out["passed"] is True and out["on_time"] is True


def test_pressure_overtime_fails_and_composts(home):
    d = methods.pressure_drill("ir-1", "Be quick.", 60.0, ["isolate"])
    out = methods.submit_pressure("ada", d["drill_id"], "isolate the host", 61.0)
    assert out["passed"] is False and out["on_time"] is False
    assert "overtime" in out["reason"]
    assert out["compost_drill_id"]
    assert compost.list_drills("ada", status="assigned")


def test_pressure_wrong_fails(home):
    d = methods.pressure_drill("ir-1", "Be quick.", 60.0, ["isolate", "backup"])
    out = methods.submit_pressure("ada", d["drill_id"], "have some coffee", 10.0)
    assert out["passed"] is False
    with pytest.raises(KeyError):
        methods.submit_pressure("ada", "nope", "x", 1.0)


# --- Socratic interrogation --------------------------------------------------------------

def test_interrogate_generates_five_per_claim(home):
    q = methods.interrogate("encryption", ["AES is sufficient for data at rest"])
    assert len(q["rounds"]) == 5
    assert all("AES is sufficient" in r["question"] for r in q["rounds"])
    kinds = {r["question"].split(":")[0] for r in q["rounds"]}
    assert len(kinds) == 5  # five distinct cross-examination angles


def test_grade_cross_examination(home):
    q = "What evidence would change your mind about key rotation schedules?"
    good = ("I would change my mind if incident data showed that breaches came "
            "from stale keys rather than phishing; the evidence I trust is "
            "post-incident reports with key-age analysis.")
    g = methods.grade_cross_examination(q, good)
    assert g["passed"] is True
    bad = methods.grade_cross_examination(q, "idk lol")
    assert bad["passed"] is False
