"""Life-coach opportunity-engine tests: DemandPulse pattern, life-coach persona.

Chauncey's canon: "Life coach is somewhat DemandPulse as a different
persona — he was the opportunity engine, opportunity to improve your
life." DemandPulse = scan signals -> score opportunities -> surface them,
pointed inward at improving YOUR life.

Tests cover:

- ``opportunities()`` scans real curriculum signals (corpus entries,
  edition/team views, the prerequisite graph) and returns scored,
  deterministically ordered items;
- scoring is TRANSPARENT: ``score`` always equals the sum of
  ``score_breakdown``, every component has a human-readable reason;
- NO hallucinated signals: every surfaced entry_id resolves through the
  engine; no invented user data — the ``user_signals`` seam is defined,
  validated, and never faked when absent;
- the seam works: completed/avoid excluded, interests boost, bad shape
  raises;
- FOUNDER GATING (Chauncey's law): the deep DemandPulse-derived sensing
  (leverage, team_momentum, preparedness, interest) runs for the founder
  tier only, wired to the real ``levi.cybrus.identity.is_founder``;
  everyone else — and the default when no identity is known — gets the
  restricted surface (accessibility, foundation, refinement), with the
  boundary stated in the response. Basic refinement plans stay ungated;
- empty corpus behaves sanely;
- the learning-engine passthrough delegates identically, and the
  life-coach-voiced rendering stays warm and direct.

Run:  python3 tests/test_life_coach_opportunities.py   (has a real __main__ runner)
      python3 -m pytest tests/test_life_coach_opportunities.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.sidewinder.curriculum.corpus import Corpus  # noqa: E402
from levi.sidewinder.platform.api import CoursePlatform  # noqa: E402
from levi.sidewinder.platform.learning_engine import LearningEngine  # noqa: E402

_KNOWN_COMPONENTS = {
    "refinement",
    "foundation",
    "preparedness",
    "leverage",
    "accessibility",
    "team_momentum",
    "interest",
}


def _engine() -> LearningEngine:
    return LearningEngine()


def _founder_engine() -> LearningEngine:
    return LearningEngine(
        identity={
            "id": "founder-test-id",
            "name": "chauncey",
            "tier": "founder",
            "status": "active",
        }
    )


def _starter_engine() -> LearningEngine:
    return LearningEngine(
        identity={
            "id": "starter-test-id",
            "name": "someone",
            "tier": "starter",
            "status": "active",
        }
    )


# ── scan -> score -> surface ─────────────────────────────────────────

def test_opportunities_scored_and_ordered():
    engine = _engine()
    result = engine.opportunities(limit=5)
    assert result["kind"] == "opportunities"
    assert result["count"] == 5
    assert len(result["items"]) == 5
    scores = [i["score"] for i in result["items"]]
    assert scores == sorted(scores, reverse=True), "must be score-desc"
    # Deterministic tie-break: score desc, then entry id.
    keys = [(-i["score"], i["entry_id"]) for i in result["items"]]
    assert keys == sorted(keys)


def test_opportunities_deterministic():
    engine = _engine()
    first = engine.opportunities(limit=10)
    second = engine.opportunities(limit=10)
    assert first == second, "scoring must be fully deterministic"


def test_scoring_transparent():
    engine = _engine()
    result = engine.opportunities(limit=10)
    assert result["items"], "corpus must yield opportunities"
    for item in result["items"]:
        assert item["score"] == sum(item["score_breakdown"].values()), (
            f"score must equal breakdown sum for {item['entry_id']}"
        )
        assert set(item["score_breakdown"]) <= _KNOWN_COMPONENTS, (
            f"unknown scoring component in {item['entry_id']}"
        )
        assert item["reasons"], f"every point needs a stated reason ({item['entry_id']})"
        assert item["persona_line"], f"life-coach voice required ({item['entry_id']})"
        assert item["kind"] in {
            "foundation_leverage",
            "career_refinement",
            "preparedness",
            "quick_win",
            "team_signal",
        }


def test_no_hallucinated_signals():
    engine = _engine()
    result = engine.opportunities(limit=25)
    for item in result["items"]:
        entry = engine.get(item["entry_id"])
        assert entry is not None, f"surfaced unknown entry {item['entry_id']}"
        assert entry["title"] == item["title"]
        assert entry["domain"] == item["domain"]
        # Leverage claims must be backed by the real prerequisite graph.
        if "leverage" in item["score_breakdown"]:
            dependents = [
                e for e in engine.manual() if item["entry_id"] in e["prerequisites"]
            ]
            assert dependents, "leverage without real dependents is hallucination"


# ── the user_signals seam: defined, validated, never faked ───────────

def test_seam_absent_is_corpus_only():
    engine = _engine()
    result = engine.opportunities(limit=10)
    assert "corpus-derived only" in result["seam"]
    for item in result["items"]:
        assert "interest" not in item["score_breakdown"], (
            "no user data may be invented when the seam is absent"
        )


def test_user_signals_completed_and_avoid_excluded():
    engine = _engine()
    baseline = engine.opportunities(limit=50)
    victim = baseline["items"][0]["entry_id"]
    other = baseline["items"][1]["entry_id"]
    result = engine.opportunities(
        limit=50, user_signals={"completed": [victim], "avoid": [other]}
    )
    ids = {i["entry_id"] for i in result["items"]}
    assert victim not in ids and other not in ids
    assert "user_signals applied" in result["seam"]


def test_user_signals_interests_boost():
    # Interest personalization is deep sensing: founder tier only.
    engine = _founder_engine()
    plain = {i["entry_id"]: i["score"] for i in engine.opportunities(limit=50)["items"]}
    boosted = {
        i["entry_id"]: i
        for i in engine.opportunities(
            limit=50, user_signals={"interests": ["crisis"]}
        )["items"]
    }
    crisis_items = [i for i in boosted.values() if i["domain"] == "crisis"]
    assert crisis_items, "corpus must contain crisis entries for this test"
    for item in crisis_items:
        assert "interest" in item["score_breakdown"]
        assert item["score"] > plain[item["entry_id"]]


def test_user_signals_bad_shape_raises():
    engine = _engine()
    for bad in ("nope", {"completed": "sw-plumbing-001"}, {"interests": [42]}):
        try:
            engine.opportunities(user_signals=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"bad user_signals {bad!r} must raise ValueError")


# ── founder gating: DemandPulse's true potential is founder-only ─────

def test_gating_uses_real_cybrus_mechanism():
    from levi.cybrus.identity import is_founder

    assert is_founder({"tier": "founder", "name": "chauncey"})
    assert not is_founder({"tier": "starter", "name": "someone"})
    assert not is_founder(None)


def test_founder_gets_full_capability():
    engine = _founder_engine()
    result = engine.opportunities(limit=50)
    assert result["access"] == "full"
    assert "note" not in result, "full access states no restriction"
    deep_seen = set()
    for item in result["items"]:
        deep_seen |= set(item["score_breakdown"]) & {
            "leverage",
            "team_momentum",
            "preparedness",
            "interest",
        }
    assert deep_seen, "founder must see deep DemandPulse-derived components"


def test_non_founder_gets_restricted_surface():
    for engine in (_engine(), _starter_engine()):
        result = engine.opportunities(limit=50)
        assert result["access"] == "restricted"
        assert "founder-only" in result["note"]
        for item in result["items"]:
            assert set(item["score_breakdown"]) <= {
                "accessibility",
                "foundation",
                "refinement",
            }, f"deep component leaked to non-founder in {item['entry_id']}"


def test_default_no_identity_is_restricted():
    engine = LearningEngine()  # no identity -> restricted, never full
    assert engine.opportunities(limit=5)["access"] == "restricted"


def test_basic_refinement_plans_ungated():
    # refine_plan / career_refinement are not DemandPulse-derived:
    # every tier gets them.
    engine = _starter_engine()
    plan = engine.refine(entry_id="sw-plumbing-001")
    assert plan["kind"] == "refine_plan" and plan["drills"]
    program = engine.refine(edition="first-responder")
    assert program["kind"] == "career_refinement" and program["items"]


def test_restricted_still_deterministic_and_transparent():
    engine = _starter_engine()
    first = engine.opportunities(limit=10)
    second = engine.opportunities(limit=10)
    assert first == second
    for item in first["items"]:
        assert item["score"] == sum(item["score_breakdown"].values())
        assert item["reasons"]


# ── scoping and edge cases ───────────────────────────────────────────

def test_edition_scoped_opportunities():
    engine = _engine()
    result = engine.opportunities(edition="first-responder", limit=5)
    assert result["scope"]["edition"] == "first-responder"
    assert result["items"], "first-responder pack must yield opportunities"
    view_ids = {e["id"] for e in engine.edition_view("first-responder").entries}
    for item in result["items"]:
        assert item["entry_id"] in view_ids


def test_empty_corpus_sane():
    api = CoursePlatform()
    # NOTE: Corpus([]) is falsy (defines __len__), so the constructor's
    # `corpus or load_corpus()` would reload the full corpus — swap the
    # loaded corpus out directly for a truly empty view.
    api._corpus = Corpus([])
    engine = LearningEngine(platform=api)
    result = engine.opportunities()
    assert result["items"] == [] and result["count"] == 0
    assert "empty" in result["note"].lower()


# ── engine passthrough + life-coach voice ────────────────────────────

def test_engine_passthrough_delegates():
    engine = _engine()
    via_engine = engine.opportunities(limit=7)
    direct = engine.life_coach.opportunities(limit=7)
    assert via_engine == direct
    via_scoped = engine.opportunities(edition="first-responder", limit=3)
    assert via_scoped == engine.life_coach.opportunities(
        edition="first-responder", limit=3
    )


def test_format_opportunities_voice():
    engine = _engine()
    text = engine.format_opportunities(engine.opportunities(limit=3))
    assert "YOUR NEXT MOVES" in text
    assert "score:" in text, "transparent scoring must render"
    assert "(access: restricted)" in text
    assert "founder-only" in text, "the boundary must be stated, never silent"
    # Warm and direct life coach, never a market-demand scout.
    assert "market" not in text.lower()


# ── runner ───────────────────────────────────────────────────────────

def _run_all():
    fns = sorted(
        (n, f) for n, f in globals().items()
        if n.startswith("test_") and callable(f)
    )
    failed = 0
    for name, fn in fns:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
