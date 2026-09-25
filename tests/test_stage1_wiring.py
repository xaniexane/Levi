"""Smoke: Stage-1 lineage skill packs register + CLI dispatches.

Hermetic: subprocesses only run ``--help``/list paths; nothing executes
automation or writes outside tmp paths.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return env


def _run(*argv):
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_lists_surgeon_and_automation():
    proc = _run("--help")
    assert proc.returncode == 0, proc.stderr
    assert "surgeon" in proc.stdout
    assert "automation" in proc.stdout


def test_cli_surgeon_help():
    proc = _run("surgeon", "--help")
    assert proc.returncode == 0, proc.stderr
    for sub in ("snapshot", "cleanup", "propose", "gate"):
        assert sub in proc.stdout


def test_cli_automation_help():
    proc = _run("automation", "--help")
    assert proc.returncode == 0, proc.stderr
    for sub in ("plan", "emit", "primitives", "match", "safety"):
        assert sub in proc.stdout


def test_cli_automation_safety():
    proc = _run("automation", "safety")
    assert proc.returncode == 0, proc.stderr
    assert "never silent execution" in proc.stdout


def test_cli_brain_seed_stage1_flag():
    proc = _run("brain", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--seed-stage1" in proc.stdout


def test_cli_automation_plan_and_emit(tmp_path):
    # plan/emit are pure text — safe to run in-process here via the CLI fn.
    proc = _run(
        "automation",
        "plan",
        "--goal",
        "extract the title",
        "--url",
        "https://example.com",
    )
    assert proc.returncode == 0, proc.stderr
    assert "## Browser Automation Plan" in proc.stdout
    proc2 = _run("automation", "emit", "--goal", "g", "--url", "https://example.com")
    assert proc2.returncode == 0, proc2.stderr
    assert "Plan id" in proc2.stdout


def test_stage1_skill_packs_register():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    got = {s.id for s in reg.list()}
    expected = {
        "surgeon_snapshot",
        "surgeon_cleanup",
        "surgeon_propose",
        "surgeon_apply_advancement",
        "surgeon_sandbox_analyze",
        "surgeon_sandbox_apply",
        "factory_writebuild",
        "automation_browser_plan",
        "automation_browser_emit",
        "automation_primitives",
        "automation_nl_match",
        "automation_cdp",
        "security_fingerprint",
        "security_gate_pack",
        "agent_solve",
        "agent_mode_style",
    }
    missing = expected - got
    assert not missing, f"missing skill packs: {missing}"


def test_consequential_stage1_skills_require_confirmation():
    from levi.skill.registry import SkillRegistry, SkillRisk

    reg = SkillRegistry()
    by_id = {s.id: s for s in reg.list()}
    # Anything that writes or drives a browser is HIGH/MODERATE + HITL.
    assert by_id["surgeon_sandbox_apply"].requires_confirmation is True
    assert by_id["factory_writebuild"].requires_confirmation is True
    assert by_id["automation_cdp"].risk_level == SkillRisk.HIGH
    assert by_id["automation_cdp"].requires_confirmation is True
    # Pure plans/descriptions stay INFO without confirmation.
    assert by_id["automation_browser_plan"].risk_level == SkillRisk.INFO
    assert by_id["automation_browser_plan"].requires_confirmation is False
