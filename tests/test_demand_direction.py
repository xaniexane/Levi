"""Tests for the DemandPulse direction layer (law-guard-prove).

Guards the five invariants declared in levi.demand.direction:
  1. Deterministic: same text + same profile -> identical result.
  2. Transparent: every score carries >= 1 reason.
  3. Real signals only: scoring takes sensed records as input.
  4. Profile is data, not fate: editing the JSON changes scores,
     zero code change.
  5. No network in scoring: pure functions (no sockets used here;
     enforced by construction — the module imports only stdlib).
"""

import json

import pytest

from levi.demand.direction import (
    ALIGNED_FIT,
    DRIFT_FIT,
    DirectionItem,
    DirectionProfile,
    build_seed_profile,
    coach_brief,
    direction_fit,
    load_profile,
    verdict,
)


def _mini_profile() -> DirectionProfile:
    return DirectionProfile(
        items=(
            DirectionItem(
                id="a", name="Alpha work", weight=0.6,
                terms=("alpha", "deep"), why="test why a",
            ),
            DirectionItem(
                id="b", name="Beta work", weight=0.4,
                terms=("beta",), why="test why b",
            ),
        )
    )


# --- seed profile -----------------------------------------------------------

def test_seed_profile_valid():
    prof = build_seed_profile()
    assert len(prof.items) >= 4
    ids = [i.id for i in prof.items]
    assert len(set(ids)) == len(ids), "direction ids must be unique"
    total = sum(float(i.weight) for i in prof.items)
    assert abs(total - 1.0) < 1e-9, f"weights must sum to 1.0, got {total}"
    for item in prof.items:
        assert len(item.terms) >= 1
        assert item.why.strip(), f"{item.id} needs its stated why"


def test_seed_profile_matches_shipped_json():
    prof = build_seed_profile()
    on_disk = load_profile()
    assert on_disk.to_dict() == prof.to_dict(), (
        "data/direction.json must match build_seed_profile() — "
        "reseed after changing the seed"
    )


# --- invariant 1: determinism -----------------------------------------------

def test_direction_fit_deterministic():
    prof = _mini_profile()
    text = "alpha deep dive into the beta quadrant"
    first = json.dumps(direction_fit(text, prof).to_dict(), sort_keys=True)
    second = json.dumps(direction_fit(text, prof).to_dict(), sort_keys=True)
    assert first == second
    # and across separate profile objects with identical content
    again = json.dumps(direction_fit(text, _mini_profile()).to_dict(), sort_keys=True)
    assert first == again


def test_direction_fit_known_arithmetic():
    prof = build_seed_profile()
    # hits in levi-self-sufficiency: offline, train, brain, records, termux
    # -> 5/12 of the item's terms, weight 0.25 -> 0.25 * 5/12
    res = direction_fit(
        "train the offline brain on local records with termux builds", prof
    )
    assert res.score == round(0.25 * (5 / 12), 4) == 0.1042
    assert res.reasons[0]["item"] == "levi-self-sufficiency"
    assert res.reasons[0]["terms_matched"] == [
        "brain", "offline", "records", "termux", "train",
    ]


# --- invariant 2: transparency ----------------------------------------------

def test_direction_fit_always_has_reasons():
    prof = _mini_profile()
    for text in ["alpha work", "totally unrelated gibberish xyz", "BETA!"]:
        res = direction_fit(text, prof)
        assert len(res.reasons) >= 1, f"no reason for {text!r}"
        for r in res.reasons:
            assert r.get("item") is not None or r.get("note"), (
                f"reason must name an item or carry a note: {r}"
            )


def test_direction_fit_no_match_scores_zero_with_note():
    res = direction_fit("xylophone quantum pancakes", _mini_profile())
    assert res.score == 0.0
    assert res.reasons[0]["note"] == "no direction terms matched in signal text"


def test_verdict_shows_its_math():
    v = verdict(0.8, 0.6)
    assert v["math"] == "0.5*0.8000 + 0.5*0.6000 = 0.7000"
    assert v["combined"] == 0.7
    assert v["verdict"] == "pursue"


# --- bounds ------------------------------------------------------------------

def test_direction_fit_bounds():
    prof = build_seed_profile()
    texts = [
        "offline brain training on local records",
        "demandpulse signal scoring for the customer product",
        "legion creature nft universe launch",
        "grok chat history lineage recovery archive",
        "dynasty mvp production rollout wave",
        "baby levi growth harvest reflect consolidate journal",
        "",
        "   ",
        "a",
        "alpha beta gamma delta " * 50,
    ]
    for text in texts:
        if not text.strip():
            with pytest.raises(ValueError):
                direction_fit(text, prof)
            continue
        res = direction_fit(text, prof)
        assert 0.0 <= res.score <= 1.0, f"out of bounds for {text!r}"


def test_verdict_bands_and_boundaries():
    assert verdict(0.9, 0.9)["verdict"] == "pursue"
    assert verdict(0.65, 0.65)["verdict"] == "pursue"   # boundary: pursue
    assert verdict(0.6499, 0.6499)["verdict"] == "watch"
    assert verdict(0.5, 0.5)["verdict"] == "watch"
    assert verdict(0.4, 0.4)["verdict"] == "watch"      # boundary: watch
    assert verdict(0.3999, 0.3999)["verdict"] == "drop"
    assert verdict(0.1, 0.1)["verdict"] == "drop"
    assert verdict(0.0, 0.0)["verdict"] == "drop"
    assert verdict(1.0, 1.0)["verdict"] == "pursue"
    for bad in (-0.1, 1.1, float("nan"), "high", True, None):
        with pytest.raises(ValueError):
            verdict(bad, 0.5)
        with pytest.raises(ValueError):
            verdict(0.5, bad)


# --- invariant 4: profile is data, not fate -----------------------------------

def test_profile_editability_changes_scores_without_code_change(tmp_path):
    path = tmp_path / "direction.json"
    build_seed_profile().save(path)
    text = "train the offline brain on local records with termux builds"
    before = direction_fit(text, load_profile(path)).score
    assert before == 0.1042

    # His word changes the file: swap two weights, keep the sum at 1.0.
    raw = json.loads(path.read_text(encoding="utf-8"))
    weights = {i["id"]: i["weight"] for i in raw["items"]}
    weights["levi-self-sufficiency"], weights["dynasty-production"] = (
        weights["dynasty-production"], weights["levi-self-sufficiency"],
    )
    for i in raw["items"]:
        i["weight"] = weights[i["id"]]
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    after = direction_fit(text, load_profile(path)).score
    assert after == round(0.10 * (5 / 12), 4) == 0.0417
    assert after != before


def test_load_missing_profile_points_to_reseed(tmp_path):
    with pytest.raises(FileNotFoundError, match="reseed"):
        load_profile(tmp_path / "nope.json")


def test_profile_validation_rejects_garbage():
    good = build_seed_profile().to_dict()
    # weights not summing to 1.0
    bad = json.loads(json.dumps(good))
    bad["items"][0]["weight"] = 0.99
    with pytest.raises(ValueError, match="sum to 1.0"):
        DirectionProfile.from_dict(bad)
    # duplicate ids
    bad = json.loads(json.dumps(good))
    bad["items"][1]["id"] = bad["items"][0]["id"]
    with pytest.raises(ValueError, match="unique"):
        DirectionProfile.from_dict(bad)
    # empty terms
    bad = json.loads(json.dumps(good))
    bad["items"][0]["terms"] = []
    with pytest.raises(ValueError, match="terms"):
        DirectionProfile.from_dict(bad)
    # missing why
    bad = json.loads(json.dumps(good))
    bad["items"][0]["why"] = "  "
    with pytest.raises(ValueError, match="why"):
        DirectionProfile.from_dict(bad)


# --- coach brief ---------------------------------------------------------------

def test_coach_nudge_rule_picks_highest_fit_unpursued():
    prof = _mini_profile()
    signals = [
        {"id": "s1", "text": "alpha deep research project", "opportunity_score": 0.8},
        {"id": "s2", "text": "beta side quest", "opportunity_score": 0.9},
        {"id": "s4", "text": "alpha deep dive build", "opportunity_score": 0.85},
        {"id": "s5", "text": "alpha deep alpha work", "opportunity_score": 0.5},
    ]
    pursuits = [
        {"id": "p1", "title": "alpha deep research project", "opportunity_score": 0.8},
    ]
    brief = coach_brief(prof, signals, pursuits, as_of="2026-09-23")
    # s1 is pursued (same text) -> excluded; s4 and s5 tie at 0.6,
    # tie-break by id -> s4 wins the nudge.
    assert "Consider pursuing [s4]" in brief
    assert "highest direction-fit sensed signal with no active pursuit" in brief
    # s1 is aligned and shown, marked pursued only by exclusion from nudge
    assert "[s1] fit=0.60" in brief


def test_coach_nudge_links_pursuit_by_demand_id():
    prof = _mini_profile()
    signals = [
        {"id": "sig-9", "text": "alpha deep dive build", "opportunity_score": 0.85},
    ]
    pursuits = [
        {"id": "opp-1", "title": "Something else entirely",
         "demand_id": "sig-9", "opportunity_score": 0.2},
    ]
    brief = coach_brief(prof, signals, pursuits)
    assert "Consider pursuing [sig-9]" not in brief
    assert "nothing to add" in brief


def test_coach_empty_store_says_so_plainly():
    brief = coach_brief(_mini_profile(), [], [], as_of="2026-09-23")
    assert "nothing sensed right now" in brief
    assert "nothing to add" in brief
    assert "2026-09-23" in brief


def test_coach_drift_lists_low_fit_pursuits():
    prof = _mini_profile()
    pursuits = [
        {"id": "p1", "title": "completely unrelated errand", "opportunity_score": 0.9},
        {"id": "p2", "title": "alpha deep work session", "opportunity_score": 0.9},
    ]
    brief = coach_brief(prof, [], pursuits)
    assert "What's drift" in brief
    assert "completely unrelated errand" in brief
    assert "alpha deep work session" not in brief.split("What's drift")[1].split(
        "One refinement nudge")[0]


def test_coach_validates_inputs():
    prof = _mini_profile()
    with pytest.raises(ValueError):
        coach_brief(prof, [{"id": "x"}], [])
    with pytest.raises(ValueError):
        coach_brief(prof, [], [{"id": "x"}])
    with pytest.raises(ValueError):
        coach_brief("not-a-profile", [], [])


def test_coach_deterministic():
    prof = _mini_profile()
    signals = [{"id": "s1", "text": "alpha deep research", "opportunity_score": 0.8}]
    pursuits = [{"id": "p1", "title": "beta quest", "opportunity_score": 0.5}]
    assert coach_brief(prof, signals, pursuits, as_of="t") == coach_brief(
        prof, signals, pursuits, as_of="t"
    )


# --- invariant 3: real signals only ---------------------------------------------

def test_direction_fit_accepts_sensed_signal_records():
    from levi.demand.pulse import DemandSignal

    sig = DemandSignal(id="abc123", need="offline brain training on local records")
    prof = build_seed_profile()
    res = direction_fit(sig, prof)
    assert res.score > 0.0
    assert any(r.get("item") == "levi-self-sufficiency" for r in res.reasons)


# --- CLI smoke (no store reads) --------------------------------------------------

def test_cli_direction_shows_profile(capsys):
    from levi.demand.__main__ import _direction_main

    assert _direction_main(["direction"]) == 0
    out = capsys.readouterr().out
    assert "levi-self-sufficiency" in out
    assert "edit the JSON file" in out


def test_cli_direction_fit_scores_text(capsys):
    from levi.demand.__main__ import _direction_main

    assert _direction_main(["direction", "--fit", "offline brain training"]) == 0
    out = capsys.readouterr().out
    assert "direction-fit score=" in out
