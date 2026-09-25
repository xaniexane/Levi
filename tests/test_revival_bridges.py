"""Tests for the revival bridges — thin glue to DemandPulse, jobs, skills.

Every test runs against the real organs with isolated state
(tmp dirs, in-memory registries). No network, no user data touched.
"""

from levi.revival import bridges
from levi.revival.omega import blueprint as bp


def _blueprint(prompt="build a habit tracker cli for my morning routine"):
    return bp.build_blueprint(prompt)


# ---- score_blueprint --------------------------------------------------


def test_score_blueprint_registers_hypothesis_signal(tmp_path):
    from levi.demand.pulse import DemandPulse

    pulse = DemandPulse(path=tmp_path / "demand.json")
    result = bridges.score_blueprint(_blueprint(), pulse=pulse)
    assert result["ok"] is True
    assert result["signal_id"]
    assert result["pulse"] == "DemandPulse"
    assert result["signal"]["kind"] == "HYPOTHESIS"
    assert result["signal"]["segment"] == "revival"
    assert any(s.id == result["signal_id"] for s in pulse.signals)


def test_score_blueprint_never_invents_five_factor_cards(tmp_path):
    from levi.demand.pulse import DemandPulse

    pulse = DemandPulse(path=tmp_path / "demand.json")
    result = bridges.score_blueprint(_blueprint(), pulse=pulse)
    assert result["ok"] is True
    assert pulse.score_cards == []
    assert pulse.opportunities == []


def test_score_blueprint_invalid_input_degrades(tmp_path):
    from levi.demand.pulse import DemandPulse

    pulse = DemandPulse(path=tmp_path / "demand.json")
    assert bridges.score_blueprint({"nope": 1}, pulse=pulse)["ok"] is False
    assert bridges.score_blueprint(None, pulse=pulse)["ok"] is False
    reason = bridges.score_blueprint({}, pulse=pulse)["reason"]
    assert "invalid blueprint" in reason


# ---- blueprint_to_job -------------------------------------------------


def test_blueprint_to_job_lands_in_draft_state(tmp_path):
    from levi.jobs.tracker import JobTracker

    tracker = JobTracker(path=tmp_path / "jobs.json")
    result = bridges.blueprint_to_job(_blueprint(), tracker=tracker)
    assert result["ok"] is True
    assert result["created"] is True
    assert result["status"] == "new"  # draft; never auto-approved
    job = tracker.get(result["job_id"])
    assert job.source == "revival-echo"
    assert any("HITL" in n.text for n in job.notes)


def test_blueprint_to_job_is_idempotent(tmp_path):
    from levi.jobs.tracker import JobTracker

    tracker = JobTracker(path=tmp_path / "jobs.json")
    first = bridges.blueprint_to_job(_blueprint(), tracker=tracker)
    second = bridges.blueprint_to_job(_blueprint(), tracker=tracker)
    assert first["ok"] and second["ok"]
    assert first["job_id"] == second["job_id"]
    assert second["created"] is False
    assert len(tracker.list()) == 1


def test_blueprint_to_job_invalid_input_degrades(tmp_path):
    from levi.jobs.tracker import JobTracker

    tracker = JobTracker(path=tmp_path / "jobs.json")
    assert bridges.blueprint_to_job({"bad": True}, tracker=tracker)["ok"] is False


# ---- hand_skill_to_registry -------------------------------------------

_FILES = {
    "habit-skill/SKILL.md": "# Habit skill\n",
    "habit-skill/main.py": "print('hi')\n",
}


def test_hand_skill_to_registry_registers_plan_skill():
    from levi.skill.registry import SkillRegistry, SkillRisk

    registry = SkillRegistry()
    result = bridges.hand_skill_to_registry(
        dict(_FILES), registry=registry, name="Habit Skill"
    )
    assert result["ok"] is True
    assert result["registered"] is True
    skill = registry.get(result["skill_id"])
    assert skill is not None
    assert skill.category == "revival"
    assert skill.risk_level == SkillRisk.INFO
    assert skill.requires_confirmation is True
    assert "needs-review" in skill.tags
    # handler presents the plan, never runs generated code
    out = registry.invoke(result["skill_id"], {})
    assert "NOT auto-executed" in out
    assert "habit-skill/SKILL.md" in out


def test_hand_skill_to_registry_without_registry_returns_plan():
    result = bridges.hand_skill_to_registry(dict(_FILES), registry=None)
    assert result["ok"] is True
    assert result["registered"] is False
    plan = result["plan"]
    assert plan["skill_id"]
    assert sorted(plan["files"]) == sorted(_FILES)
    assert plan["steps"] and len(plan["steps"]) >= 2


def test_hand_skill_to_registry_rejects_bad_input():
    assert bridges.hand_skill_to_registry({}, registry=None)["ok"] is False
    assert bridges.hand_skill_to_registry(None, registry=None)["ok"] is False
    assert (
        bridges.hand_skill_to_registry({"../evil.py": "x"}, registry=None)["ok"]
        is False
    )
    assert (
        bridges.hand_skill_to_registry({"/abs/path.py": "x"}, registry=None)["ok"]
        is False
    )
    assert bridges.hand_skill_to_registry({"a.py": 123}, registry=None)["ok"] is False


def test_hand_skill_to_registry_rejects_non_registry():
    result = bridges.hand_skill_to_registry(dict(_FILES), registry=object())
    assert result["ok"] is False
    assert "register" in result["reason"]


# ---- orchestration entry points (documented) --------------------------


def test_orchestration_entry_points_documented():
    eps = bridges.orchestration_entry_points()
    assert "levi.orchestration.loop" in eps
    assert any("turn(user_text" in e for e in eps["levi.orchestration.loop"])
    assert "levi.orchestration.nl_ir" in eps
