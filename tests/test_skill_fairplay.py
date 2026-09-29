"""Tests for the fairplay skill library (levi.skill.fairplay_skills).

- All three playbooks load with valid frontmatter, fairplay id scheme,
  and INFO risk.
- The audit_offer handler runs the real detector on a passed offer,
  refuses non-mapping offers honestly, and returns the advisory
  playbook when no offer is passed.
"""

from levi.skill.fairplay_skills import FAIRPLAY_SKILLS, PLAYBOOK_DIR
from levi.skill.registry import SkillRisk

EXPECTED_IDS = [
    "fairplay.audit_offer",
    "fairplay.pattern_catalog",
    "fairplay.write_honest_offer",
]

SLY_OFFER = {
    "name": "test loot box",
    "paid_random_draws": True,  # odds not published -> opaque-odds (sly)
}

CLEAN_OFFER = {
    "name": "test honest pass",
    "paid_random_draws": True,
    "odds_published": True,
    "pity_ceiling_declared": True,
    "worst_case_spend_declared": True,
    "progress_expiry": "never",
    "inventory_exportable": True,
}


def _by_id(skill_id):
    for skill in FAIRPLAY_SKILLS:
        if skill.id == skill_id:
            return skill
    raise AssertionError(f"skill {skill_id} not registered")


def test_all_three_playbooks_load():
    assert sorted(s.id for s in FAIRPLAY_SKILLS) == EXPECTED_IDS
    assert PLAYBOOK_DIR.is_dir()


def test_frontmatter_contract():
    for skill in FAIRPLAY_SKILLS:
        assert skill.category == "fairplay"
        assert skill.risk_level == SkillRisk.INFO
        assert skill.requires_confirmation is False
        assert skill.permissions == []
        assert skill.name and skill.description
        assert skill.handler is not None
        stem = skill.id.split(".", 1)[1]
        assert (PLAYBOOK_DIR / f"{stem}.md").is_file()


def test_audit_handler_runs_detector_on_sly_offer():
    out = _by_id("fairplay.audit_offer").handler({"offer": SLY_OFFER})
    assert "verdict: predatory" in out
    assert "opaque-odds" in out
    assert "honest alternative" in out


def test_audit_handler_clean_offer():
    out = _by_id("fairplay.audit_offer").handler({"offer": CLEAN_OFFER})
    assert "verdict: honest" in out


def test_audit_handler_refuses_non_mapping_offer():
    out = _by_id("fairplay.audit_offer").handler({"offer": ["not", "a", "mapping"]})
    assert "refused" in out
    assert "nothing was audited" in out


def test_audit_handler_without_offer_returns_playbook():
    out = _by_id("fairplay.audit_offer").handler({})
    assert "## Procedure" in out


def test_catalog_handler_lists_patterns():
    out = _by_id("fairplay.pattern_catalog").handler({})
    assert "opaque-odds" in out
    assert "time-fenced-grind" in out
    assert "euphemism" in out
