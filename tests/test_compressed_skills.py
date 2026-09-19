"""Tests for the compressed-engines skill pack."""

from levi.skill import compressed_skills
from levi.skill.compressed_skills import COMPRESSED_SKILLS, expected_ids
from levi.skill.registry import SkillRegistry


def test_pack_has_playbooks_and_runners():
    ids = {s.id for s in COMPRESSED_SKILLS}
    assert len(expected_ids()) >= 6
    assert set(expected_ids()) <= ids
    assert {"compressed.run-triage", "compressed.run-cadence",
            "compressed.run-weigh"} <= ids


def test_ids_lock_to_filenames():
    for s in COMPRESSED_SKILLS:
        if s.id.startswith("compressed.run-"):
            continue
        assert s.id == f"compressed.{s.id.split('.', 1)[1]}"
    assert set(expected_ids()) == {
        s.id for s in COMPRESSED_SKILLS if not s.id.startswith("compressed.run-")
    }


def test_category_and_risk_tags():
    for s in COMPRESSED_SKILLS:
        assert s.category == "compressed-engine"
        assert not s.requires_confirmation
        assert s.permissions == []


def test_registry_registers_pack():
    reg = SkillRegistry()
    ids = {s.id for s in reg.list()}
    assert set(expected_ids()) <= ids
    assert "compressed.run-triage" in ids


def test_engine_runner_skill_executes():
    reg = SkillRegistry()
    skill = reg.get("compressed.run-weigh")
    out = skill.handler(
        {
            "proposition": "Pack tonight?",
            "for_evidence": [{"point": "momentum", "weight": 2.0}],
            "against_evidence": [{"point": "hour is late", "weight": 1.0}],
        }
    )
    assert "[weigh] verdict" in out
    assert "confidence" in out


def test_engine_runner_skill_refuses_gracefully():
    reg = SkillRegistry()
    skill = reg.get("compressed.run-triage")
    out = skill.handler({"options": []})
    assert "refused" in out
