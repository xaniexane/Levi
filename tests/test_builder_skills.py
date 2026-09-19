"""Tests for the builder skill library (data-driven playbook registration)."""

import levi.skill.builder_skills as builder
from levi.skill.registry import SkillRisk

EXPECTED_IDS = {
    "builder.ship_small",
    "builder.review_own_diff",
    "builder.name_the_pattern",
    "builder.keep_receipts",
    "builder.leave_trails",
    "builder.timebox_hard",
}


def test_all_builder_playbooks_registered():
    ids = {skill.id for skill in builder.BUILDER_SKILLS}
    assert EXPECTED_IDS == ids


def test_category_and_risk():
    for skill in builder.BUILDER_SKILLS:
        assert skill.category == "builder"
        assert skill.risk_level == SkillRisk.INFO
        assert skill.requires_confirmation is False
        assert skill.name.strip()
        assert skill.description.strip()


def test_every_playbook_file_has_valid_frontmatter():
    for path in sorted(builder.PLAYBOOK_DIR.glob("*.md")):
        meta = builder._parse_frontmatter(path)
        assert meta is not None, f"{path.name} has no frontmatter"
        assert all(k in meta for k in builder.FRONTMATTER_KEYS), path.name
        assert meta["skill_id"] == "builder." + path.stem.replace("-", "_")


def test_handlers_return_the_playbook_text():
    by_id = {skill.id: skill for skill in builder.BUILDER_SKILLS}
    text = by_id["builder.ship_small"].handler({})
    assert "Ship Small" in text
    assert "builder.ship_small" in text


def test_dynamic_scan_picks_up_new_playbooks(tmp_path, monkeypatch):
    new = tmp_path / "fresh-eyes.md"
    new.write_text(
        "---\n"
        "skill_id: builder.fresh_eyes\n"
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
    monkeypatch.setattr(builder, "PLAYBOOK_DIR", tmp_path)
    skills = builder._load_builder_skills()
    assert {s.id for s in skills} == {"builder.fresh_eyes"}


def test_broken_frontmatter_never_crashes_import(tmp_path, monkeypatch):
    bad = tmp_path / "broken.md"
    bad.write_text("no frontmatter here\n", encoding="utf-8")
    monkeypatch.setattr(builder, "PLAYBOOK_DIR", tmp_path)
    assert builder._load_builder_skills() == []
