"""Tests for the warden run-skills (attest + redline)."""

from hashlib import sha256

from levi.skill.registry import SkillRisk
from levi.skill.warden_skills import WARDEN_SKILLS, expected_ids


def _link(prev_id: str, prev_body: str) -> str:
    return sha256(f"{prev_id}\n{prev_body}".encode("utf-8")).hexdigest()


def _skill(skill_id: str):
    for skill in WARDEN_SKILLS:
        if skill.id == skill_id:
            return skill
    raise AssertionError(f"missing skill {skill_id}")


def test_expected_ids_match_list():
    assert expected_ids() == [s.id for s in WARDEN_SKILLS]
    assert expected_ids() == ["warden.run-attest", "warden.run-redline"]


def test_skills_are_safe_by_construction():
    for skill in WARDEN_SKILLS:
        assert skill.risk_level == SkillRisk.INFO
        assert skill.permissions == []
        assert skill.requires_confirmation is False
        assert callable(skill.handler)
        assert skill.category == "warden"


def test_attest_skill_intact_chain():
    receipts = []
    prev = "genesis-anchor"
    for i in range(2):
        receipts.append({"id": f"r{i}", "body": f"body-{i}", "prev": prev})
        prev = _link(f"r{i}", f"body-{i}")
    out = _skill("warden.run-attest").handler(
        {"receipts": receipts, "genesis": "genesis-anchor"}
    )
    assert "[attest] INTACT" in out
    assert "confidence: 1.0" in out


def test_attest_skill_broken_chain():
    receipts = [{"id": "r0", "body": "b0", "prev": "WRONG"}]
    out = _skill("warden.run-attest").handler(
        {"receipts": receipts, "genesis": "genesis-anchor"}
    )
    assert "[attest] BROKEN at index 0" in out


def test_attest_skill_refuses_bad_input():
    out = _skill("warden.run-attest").handler({"receipts": []})
    assert "refused" in out  # missing genesis → engine refuses


def test_redline_skill_over():
    out = _skill("warden.run-redline").handler({"spent": 150, "cap": 100})
    assert "[redline] OVER" in out
    assert "by 50.0" in out


def test_redline_skill_would_breach_with_label():
    out = _skill("warden.run-redline").handler(
        {"spent": 80, "cap": 100, "pending": 30, "label": "test box"}
    )
    assert "[redline] [test box] WOULD-BREACH" in out
    assert "crosses the cap by 10.0" in out


def test_redline_skill_clear():
    out = _skill("warden.run-redline").handler({"spent": 20, "cap": 100})
    assert "[redline] CLEAR" in out


def test_redline_skill_refuses_negative():
    out = _skill("warden.run-redline").handler({"spent": -5, "cap": 100})
    assert "refused" in out
