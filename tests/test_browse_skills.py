"""Tests for the browse-layer construction skill (data-driven playbook registration)."""

import levi.skill.browse_skills as browse
from levi.skill.registry import SkillRisk

EXPECTED_IDS = {
    "browse.eight_laws",
    "browse.agent_laws",
    "browse.deny_closed_default",
    "browse.phased_plan",
    "browse.phase_gates",
    "browse.file_ownership",
    "browse.quality_gates",
    "browse.honest_claims",
    "browse.plugin_api_contract",
    "browse.pipeline_order",
    "browse.decision_gates",
}


def test_all_browse_playbooks_registered():
    ids = {skill.id for skill in browse.BROWSE_SKILLS}
    assert EXPECTED_IDS == ids


def test_expected_ids_helper_matches():
    assert set(browse.expected_ids()) == EXPECTED_IDS


def test_category_and_risk():
    for skill in browse.BROWSE_SKILLS:
        assert skill.category == "browse"
        assert skill.risk_level == SkillRisk.INFO
        assert skill.requires_confirmation is False
        assert skill.permissions == []
        assert skill.name.strip()
        assert skill.description.strip()


def test_every_playbook_file_has_valid_frontmatter():
    for path in sorted(browse.PLAYBOOK_DIR.glob("*.md")):
        meta = browse._parse_frontmatter(path)
        assert meta is not None, f"{path.name} has no frontmatter"
        assert all(k in meta for k in browse.FRONTMATTER_KEYS), path.name
        assert meta["skill_id"] == "browse." + path.stem.replace("-", "_")


def test_handlers_return_the_playbook_text():
    by_id = {skill.id for skill in browse.BROWSE_SKILLS}
    assert by_id == EXPECTED_IDS
    skills = {skill.id: skill for skill in browse.BROWSE_SKILLS}
    text = skills["browse.eight_laws"].handler({})
    assert "Eight Laws" in text
    assert "Deny-closed plugins" in text


def test_dynamic_scan_picks_up_new_playbooks(tmp_path, monkeypatch):
    new = tmp_path / "fresh-eyes.md"
    new.write_text(
        "---\n"
        "skill_id: browse.fresh_eyes\n"
        "name: Fresh Eyes\n"
        "description: Step away, then re-read the diff.\n"
        "risk: info\n"
        "permissions: []\n"
        "requires_confirmation: false\n"
        "tags: [review]\n"
        "version: 1.0.0\n"
        "---\n\n# Fresh Eyes\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(browse, "PLAYBOOK_DIR", tmp_path)
    skills = browse._load_browse_skills()
    assert {s.id for s in skills} == {"browse.fresh_eyes"}


def test_broken_frontmatter_never_crashes_import(tmp_path, monkeypatch):
    bad = tmp_path / "broken.md"
    bad.write_text("no frontmatter here\n", encoding="utf-8")
    monkeypatch.setattr(browse, "PLAYBOOK_DIR", tmp_path)
    assert browse._load_browse_skills() == []
