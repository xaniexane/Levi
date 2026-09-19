"""Tests for the Z-1 compressed-engine skill layer.

The six Z-1 compressed engines (Core, Context, Workflow, Simulation,
Governance, Stability) are rebuilt as advisory playbooks (auto-registered
``compressed.z1-*`` skills), and the two new engines as executable
``compressed.run-*`` runner skills.
"""

from levi.skill import compressed_skills
from levi.skill.compressed_skills import COMPRESSED_SKILLS
from levi.skill.registry import SkillRegistry

Z1_IDS = [
    "compressed.z1-core",
    "compressed.z1-context",
    "compressed.z1-workflow",
    "compressed.z1-simulation",
    "compressed.z1-governance",
    "compressed.z1-stability",
]

RUNNER_IDS = ["compressed.run-quietwatch", "compressed.run-handshake"]


def test_z1_playbooks_register():
    ids = {s.id for s in COMPRESSED_SKILLS}
    assert set(Z1_IDS) <= ids


def test_z1_skills_are_advisory_info():
    by_id = {s.id: s for s in COMPRESSED_SKILLS}
    for sid in Z1_IDS:
        skill = by_id[sid]
        assert skill.category == "compressed-engine"
        assert not skill.requires_confirmation
        assert skill.permissions == []
        assert skill.handler is None  # advisory: pattern, not execution


def test_new_runner_skills_register():
    ids = {s.id for s in COMPRESSED_SKILLS}
    assert set(RUNNER_IDS) <= ids


def test_quietwatch_runner_executes():
    skill = SkillRegistry().get("compressed.run-quietwatch")
    out = skill.handler(
        {
            "calls": [{"id": "alpha", "pattern": "alpha base"}],
            "transcript": ["static", "alpha base, come in"],
        }
    )
    assert "[quietwatch] verdict" in out
    assert "awake" in out


def test_handshake_runner_executes():
    skill = SkillRegistry().get("compressed.run-handshake")
    out = skill.handler(
        {
            "initiator": {"id": "a", "capabilities": ["x", "y"]},
            "responder": {"id": "b", "capabilities": ["y"]},
        }
    )
    assert "[handshake] verdict" in out
    assert "ack" in out


def test_runners_refuse_gracefully():
    reg = SkillRegistry()
    out = reg.get("compressed.run-quietwatch").handler({"calls": [], "transcript": []})
    assert "refused" in out
    out = reg.get("compressed.run-handshake").handler(
        {
            "initiator": {"id": "a", "capabilities": []},
            "responder": {"id": "b", "capabilities": ["x"]},
        }
    )
    assert "refused" in out


def test_pack_source_still_exports():
    assert compressed_skills is not None
