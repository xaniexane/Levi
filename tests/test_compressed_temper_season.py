"""Tests for the temper/season additions to the compressed skill pack."""

from levi.skill.compressed_skills import COMPRESSED_SKILLS, expected_ids
from levi.skill.registry import SkillRegistry


def test_new_playbooks_registered():
    assert "compressed.engine-temper" in expected_ids()
    assert "compressed.engine-season" in expected_ids()
    ids = {s.id for s in COMPRESSED_SKILLS}
    assert {"compressed.engine-temper", "compressed.engine-season"} <= ids


def test_run_skills_execute():
    skills = {s.id: s for s in COMPRESSED_SKILLS}
    out = skills["compressed.run-temper"].handler(
        {
            "claim": "rain is wet",
            "corroborations": 7,
            "contradictions": 0,
            "source_count": 7,
            "days_old": 1,
        }
    )
    assert "settled" in out
    out = skills["compressed.run-season"].handler({"daily_loads": [5] * 14})
    assert "rest" in out


def test_run_skill_refusal_is_text_not_exception():
    skills = {s.id: s for s in COMPRESSED_SKILLS}
    out = skills["compressed.run-temper"].handler({"claim": ""})
    assert "refused" in out


def test_pack_still_locks_to_filenames():
    assert set(expected_ids()) == {
        s.id for s in COMPRESSED_SKILLS if not s.id.startswith("compressed.run-")
    }


def test_registry_picks_up_new_skills():
    reg = SkillRegistry()
    ids = {s.id for s in reg.list()}
    assert {
        "compressed.engine-temper",
        "compressed.engine-season",
        "compressed.run-temper",
        "compressed.run-season",
    } <= ids
