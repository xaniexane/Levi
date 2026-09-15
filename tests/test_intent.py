"""Intent map: the orchestration UNDERSTAND step is wired and pure.

Hermetic: build_intent_map / motivation_graph_for touch no disk, no network.
"""

from levi.orchestration.intent import (
    Direction,
    IntentMap,
    MotivationGraph,
    build_intent_map,
    direction_for,
    motivation_graph_for,
)
from levi.orchestration.loop import Orchestrator


def test_build_intent_map_records_literal():
    im = build_intent_map("build me an app")
    assert isinstance(im, IntentMap)
    assert im.literal_request == "build me an app"
    assert 0.0 <= im.confidence <= 1.0


def test_build_intent_map_why_hint():
    im = build_intent_map("why is the sky blue")
    assert im.why and "reason" in im.why.lower() or "motivation" in im.why.lower()


def test_build_intent_map_local_constraint():
    im = build_intent_map("summarize this file, offline please")
    assert any("local" in c for c in im.constraints)


def test_direction_for_hints():
    assert direction_for("why did it fail") == Direction.WHY
    assert direction_for("what is the next step") == Direction.NEXT
    assert direction_for("hello") == Direction.DIRECT


def test_motivation_graph_ranked():
    g = motivation_graph_for("build me an app", ["factory_create", "status"])
    assert isinstance(g, MotivationGraph)
    ranked = g.ranked()
    assert len(ranked) == 2
    assert ranked[0].description.startswith("route via skill")


def test_turn_carries_intent_map_metadata():
    orch = Orchestrator()
    result = orch.turn("help")
    im = result.metadata.get("intent_map")
    assert im, "turn() must attach intent_map metadata (wires orchestration.intent)"
    assert im["literal_request"] == "help"


def test_intent_skill_registered_and_runs():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    skill = reg.get("intent_map")
    assert skill is not None
    out = reg.invoke("intent_map", {"text": "plan my week"})
    assert "literal_request" in out
    assert "plan my week" in out
