"""Tests for the twin-pair skill pack (expander canon, LEVI-native originals)."""

from levi.skill import twinpair_skills
from levi.skill.registry import SkillRisk


def test_four_playbooks_registered():
    assert twinpair_skills.expected_ids() == [
        "twinpair.circuit-breaker",
        "twinpair.echo-mandella",
        "twinpair.point-inward",
        "twinpair.reim-riem",
    ]
    assert {s.id for s in twinpair_skills.TWINPAIR_SKILLS} == set(
        twinpair_skills.expected_ids()
    )


def test_category_and_risk_locked():
    for skill in twinpair_skills.TWINPAIR_SKILLS:
        assert skill.category == "twin-pair"
        assert skill.risk_level == SkillRisk.INFO
        assert skill.requires_confirmation is False
        assert skill.permissions == []
        assert skill.name and skill.description
        assert "twin-pair" in skill.tags


def test_ids_match_filenames():
    for skill in twinpair_skills.TWINPAIR_SKILLS:
        assert skill.id == f"twinpair.{skill.id.split('.', 1)[1]}"
        assert skill.id.startswith("twinpair.")


def test_lookup():
    skill = twinpair_skills.get_skill("twinpair.circuit-breaker")
    assert skill is not None
    assert "veto" in skill.name.lower()
    assert twinpair_skills.get_skill("twinpair.nope") is None


def test_bad_frontmatter_refused(tmp_path, monkeypatch):
    bad = tmp_path / "not-a-skill.md"
    bad.write_text("# No frontmatter at all\n")
    monkeypatch.setattr(twinpair_skills, "PLAYBOOK_DIR", tmp_path)
    assert twinpair_skills._load_skills() == []


def test_mismatched_id_refused(tmp_path, monkeypatch):
    bad = tmp_path / "wrong.md"
    bad.write_text(
        "---\n"
        "skill_id: twinpair.someone-else\n"
        "name: Wrong\n"
        "description: id does not match the filename.\n"
        "risk: info\n"
        "permissions: []\n"
        "requires_confirmation: false\n"
        "tags: []\n"
        "version: 1.0.0\n"
        "---\n"
    )
    monkeypatch.setattr(twinpair_skills, "PLAYBOOK_DIR", tmp_path)
    assert twinpair_skills._load_skills() == []


def test_interop_self_registration():
    # The module declares "skill-twinpair" to the default registry at
    # import; verify the declared capabilities through the public API.
    from levi.interop import registry as interop

    assert "skill-twinpair" in interop.modules()
    declared = interop.check("skill-twinpair")
    provided = declared["provides"]
    for skill_id in twinpair_skills.expected_ids():
        assert f"skill.{skill_id}" in provided
