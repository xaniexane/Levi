"""Tests for the routing skill pack (levi.skill.routing_skills)."""

from levi.skill.registry import Skill, SkillRisk
from levi.skill.routing_skills import ROUTING_SKILLS

EXPECTED_IDS = ["engine.canon", "engine.escalate", "engine.list"]


def _by_id(skill_id):
    return {s.id: s for s in ROUTING_SKILLS}[skill_id]


def test_pack_shape():
    assert [s.id for s in sorted(ROUTING_SKILLS, key=lambda s: s.id)] == EXPECTED_IDS
    for skill in ROUTING_SKILLS:
        assert isinstance(skill, Skill)
        assert skill.category == "routing"
        assert skill.risk_level == SkillRisk.INFO
        assert skill.handler is not None
        assert not skill.requires_confirmation
        assert skill.tags


def test_engine_list_skill():
    out = _by_id("engine.list").handler({})
    assert "escalate" in out
    assert "triage" in out


def test_engine_escalate_skill_routes():
    out = _by_id("engine.escalate").handler(
        {"confidence": 0.95, "stakes": "low", "reversible": True}
    )
    assert "handle_local" in out
    out = _by_id("engine.escalate").handler(
        {"confidence": 0.9, "stakes": "critical", "reversible": True}
    )
    assert "ask_operator" in out


def test_engine_escalate_skill_refuses_bad_input():
    out = _by_id("engine.escalate").handler({"confidence": 2.0})
    assert "refused" in out


def test_engine_canon_skill_is_advisory():
    out = _by_id("engine.canon").handler({})
    assert "compute, never act" in out
    assert "queue" in out
