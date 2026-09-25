"""LEVI learning-engine tests: engine shape, life-coach sub-engine nesting,
delegation, and the additive CoursePlatform wiring.

Chauncey's canon: "life coach was sub engine of learning engine."

Tests cover:

- LearningEngine wraps a CoursePlatform and exposes the learning layer as
  one surface: curriculum delivery (parity with the query API), the team
  learning loop, and the growth pipeline;
- LifeCoach is a NESTED sub-engine: reachable only as
  ``engine.life_coach`` under
  ``levi.sidewinder.platform.learning_engine.life_coach`` — never
  standalone, never a platform sibling;
- delegation: ``engine.refine(...)`` goes through the sub-engine and
  returns identical results to calling it directly;
- refine plans: drills from steps, safety checklist from stop conditions,
  prerequisites ordered first; career refinement over edition packs;
- CoursePlatform gains the engine additively: ``api.learning_engine`` and
  ``api.refine(...)`` work, the existing query API is untouched.

Run:  python3 tests/test_learning_engine.py     (has a real __main__ runner)
      python3 -m pytest tests/test_learning_engine.py -q
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import levi.sidewinder.platform as platform_pkg  # noqa: E402
from levi.sidewinder.platform.api import CoursePlatform  # noqa: E402
from levi.sidewinder.platform.learning_engine import LearningEngine  # noqa: E402
from levi.sidewinder.platform.learning_engine.life_coach import LifeCoach  # noqa: E402


def _engine() -> LearningEngine:
    return LearningEngine()


# ── engine shape ────────────────────────────────────────────────────

def test_engine_wraps_platform():
    engine = _engine()
    assert isinstance(engine.platform, CoursePlatform)
    hits = engine.search("tub spout")
    assert hits and hits[0]["id"] == "sw-plumbing-001"
    assert engine.get("sw-plumbing-001")["title"]
    assert engine.get("sw-nope-999") is None


def test_engine_delivery_parity_with_api():
    api = CoursePlatform()
    engine = LearningEngine(platform=api)
    assert engine.platform is api
    assert [e["id"] for e in engine.progression("improvise")] == [
        e["id"] for e in api.progression("improvise")
    ]
    assert engine.track_counts() == api.track_counts()
    assert [e["id"] for e in engine.manual(track="improvise")] == [
        e["id"] for e in api.manual(track="improvise")
    ]
    assert engine.edition_ids() == api.edition_ids()
    assert [t.id for t in engine.list_teams()] == [t.id for t in api.list_teams()]


def test_loop_and_growth_reachable_through_engine():
    engine = _engine()
    with tempfile.TemporaryDirectory() as tmp:
        intake = Path(tmp) / "intake"
        report = engine.harvest(
            "field-crew",
            [{"id": "bogus", "title": "not a real entry"}],
            intake_dir=intake,
        )
        assert report["team"] == "field-crew"
        assert report["valid"] == 0 and report["invalid"] == 1
        review = engine.review_intake("field-crew", intake_dir=intake)
        assert review["team"] == "field-crew"
    assert callable(engine.grow) and callable(engine.emit_stubs)


# ── nesting: life coach is a sub-engine, not a sibling ──────────────

def test_life_coach_nested_sub_engine():
    engine = _engine()
    coach = engine.life_coach
    assert isinstance(coach, LifeCoach)
    assert type(coach).__module__ == "levi.sidewinder.platform.learning_engine.life_coach"
    # Nested boundary: the platform package must not re-export it.
    assert not hasattr(platform_pkg, "LifeCoach")


# ── delegation ──────────────────────────────────────────────────────

def test_refine_plan_delegates_to_sub_engine():
    engine = _engine()
    via_engine = engine.refine(entry_id="sw-plumbing-001")
    direct = engine.life_coach.refine_plan("sw-plumbing-001")
    assert via_engine == direct
    assert via_engine["kind"] == "refine_plan"
    assert via_engine["entry_id"] == "sw-plumbing-001"
    assert via_engine["drills"], "steps must become drills"
    assert via_engine["safety_checklist"], "stop conditions ride along"
    assert isinstance(via_engine["prerequisites"], list)
    assert any("sw-foundations-007" == p["id"] for p in via_engine["prerequisites"])


def test_refine_plan_unknown_entry():
    engine = _engine()
    try:
        engine.refine(entry_id="sw-nope-999")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown entry must raise KeyError")


def test_refine_needs_a_target():
    engine = _engine()
    try:
        engine.refine()
    except ValueError:
        pass
    else:
        raise AssertionError("refine() with no target must raise ValueError")


def test_career_refinement_over_edition_pack():
    engine = _engine()
    program = engine.refine(edition="first-responder")
    assert program == engine.life_coach.career_refinement("first-responder")
    assert program["kind"] == "career_refinement"
    assert program["edition"] == "first-responder"
    assert program["items"], "pack must yield refinement items"
    for item in program["items"]:
        assert item["drills"] and item["safety_checklist"]
    text = engine.format_plan(program)
    assert "REFINEMENT PROGRAM" in text and "STOP:" in text


def test_format_plan_entry():
    engine = _engine()
    text = engine.format_plan(engine.refine(entry_id="sw-plumbing-001"))
    assert "REFINE PLAN" in text
    assert "DRILLS:" in text and "SAFETY:" in text


# ── additive platform wiring ────────────────────────────────────────

def test_api_learning_engine_additive():
    api = CoursePlatform()
    engine = api.learning_engine
    assert isinstance(engine, LearningEngine)
    assert engine.platform is api  # bound to the same platform
    assert api.learning_engine is engine  # cached, not rebuilt
    plan = api.refine(entry_id="sw-plumbing-001")
    assert plan["kind"] == "refine_plan"
    # Existing query API untouched.
    assert api.search("tub spout")[0]["id"] == "sw-plumbing-001"


# ── runner ──────────────────────────────────────────────────────────

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
