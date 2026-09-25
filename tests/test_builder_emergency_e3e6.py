"""Regression tests for the E3-E6 EmergencyBuilder (core/levi/builder/emergency.py).

Hermetic: temp HOME for the whole module, HITLGate pointed at a temp file.
No network, no writes outside tmp_path.

Laws under test:
- L1: plan() validates the tier; unknown tiers raise (never silent coercion).
- L2: E3/E4 plan without HITL; E5/E6 plan WITH HITL and await approval.
- L3: E5/E6 apply is fail-closed: no approval -> refusal, nothing written.
- L4: every generated Python file compiles; generated smoke tests pass.
- L5: project names are never paths and never break generated imports
      (hyphens become underscores in package directories).
- L6: E3 apply produces a patch kit (PATCH_PLAN.md + docs/ + tests/),
      never a new importable package.
"""

from __future__ import annotations

import os
import py_compile
import site
import subprocess
import sys
from pathlib import Path

import pytest

import levi.project.hitl as hitl_mod
from levi.builder.emergency import (
    BuildTier,
    EmergencyBuilder,
    TIER_META,
    _package_name,
    _sanitize_name,
)

# pytest itself lives in the user site (~/.local), which disappears when the
# hermetic fixture repoints HOME. Capture it now so generated-suite children
# can still import pytest.
_USER_SITE = site.getusersitepackages()


@pytest.fixture()
def hermetic(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(hitl_mod, "DEFAULT_PATH", home / ".levi" / "hitl.json")
    ws = tmp_path / "ws"
    return home, ws


def _builder(ws: Path) -> EmergencyBuilder:
    return EmergencyBuilder(workspace=ws)


def _run_generated_pytest(testdir: Path, cwd: Path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _USER_SITE + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(testdir), "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
        env=env,
    )


# ---- L1: tier validation ----------------------------------------------------


@pytest.mark.parametrize("tier", ["E3", "E4", "E5", "E6", "e3", " e4 "])
def test_plan_accepts_valid_tiers(hermetic, tier):
    _, ws = hermetic
    job = _builder(ws).plan(goal="g", tier=tier, project_name="p")
    assert job.tier == tier.strip().upper()


@pytest.mark.parametrize("tier", ["X9", "", "E33", "E2", "e7", "MVP"])
def test_plan_rejects_invalid_tier(hermetic, tier):
    _, ws = hermetic
    with pytest.raises(ValueError, match="tier must be one of"):
        _builder(ws).plan(goal="g", tier=tier, project_name="p")


def test_plan_rejects_empty_goal(hermetic):
    _, ws = hermetic
    with pytest.raises(ValueError):
        _builder(ws).plan(goal="   ", tier="E4", project_name="p")


def test_plan_rejects_empty_project_name(hermetic):
    _, ws = hermetic
    with pytest.raises(ValueError):
        _builder(ws).plan(goal="g", tier="E4", project_name="  ")


# ---- L2: HITL flags per tier --------------------------------------------------


@pytest.mark.parametrize("tier", ["E3", "E4", "E5", "E6"])
def test_plan_hitl_flags_match_tier_contract(hermetic, tier):
    _, ws = hermetic
    job = _builder(ws).plan(goal="g", tier=tier, project_name="p")
    assert job.requires_hitl == TIER_META[BuildTier(tier)]["hitl_default"]
    if tier in ("E5", "E6"):
        assert job.status == "awaiting_hitl"
        assert job.hitl_id
    else:
        assert job.status == "planned"
        assert not job.hitl_id


def test_plan_steps_e3_is_patch_kit_not_scaffold(hermetic):
    _, ws = hermetic
    job = _builder(ws).plan(goal="g", tier="E3", project_name="p")
    text = "\n".join(job.plan_steps)
    assert "PATCH_PLAN.md" in text
    assert "No new package" in text


# ---- L5: names -----------------------------------------------------------------


def test_sanitize_name_never_a_path():
    assert _sanitize_name("../../etc/passwd") == "etc_passwd"
    assert _sanitize_name("") == "new_project"
    assert _sanitize_name("  ") == "new_project"


def test_package_name_is_import_safe():
    assert _package_name("my-app") == "my_app"
    assert _package_name("my-app").isidentifier()
    assert _package_name("Hello World!").isidentifier()


def test_apply_never_writes_outside_workspace(hermetic):
    home, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="g", tier="E4", project_name="../../evil")
    b.apply(job.id)
    # everything landed under ws; nothing escaped
    assert (ws / "evil").is_dir()
    assert not (home / "evil").exists()


# ---- L4/L6: E4 scaffold ----------------------------------------------------------


def test_apply_e4_scaffold_end_to_end(hermetic):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="scaffold e2e", tier="E4", project_name="e4app")
    out = b.apply(job.id)
    assert "Applied job" in out
    root = ws / "e4app"
    for rel in (
        "README.md",
        "src/e4app/__init__.py",
        "src/e4app/main.py",
        "pyproject.toml",
        "tests/test_smoke.py",
        "HANDOFF.md",
    ):
        assert (root / rel).is_file(), rel
    for f in (root / "src").rglob("*.py"):
        py_compile.compile(str(f), doraise=True)
    r = _run_generated_pytest(root / "tests", root / "src")
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "e4app.main", "status"],
        capture_output=True,
        text=True,
        cwd=str(root / "src"),
        timeout=60,
    )
    assert r.returncode == 0 and "scaffold OK" in r.stdout


def test_apply_hyphen_name_generates_importable_package(hermetic):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="hyphen", tier="E4", project_name="my-app")
    b.apply(job.id)
    root = ws / "my-app"
    # human name on the directory; import-safe name in src/
    assert (root / "src" / "my_app" / "__init__.py").is_file()
    assert not (root / "src" / "my-app").exists()
    r = _run_generated_pytest(root / "tests", root / "src")
    assert r.returncode == 0, r.stdout + r.stderr


# ---- L6: E3 patch kit --------------------------------------------------------------


def test_apply_e3_produces_patch_kit_not_package(hermetic):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="stabilize login", tier="E3", project_name="e3app")
    out = b.apply(job.id)
    assert "Applied job" in out
    assert job.stage == "stabilize"
    root = ws / "e3app"
    for rel in (
        "README.md",
        "PATCH_PLAN.md",
        "docs/NOTES.md",
        "tests/test_smoke.py",
        "HANDOFF.md",
    ):
        assert (root / rel).is_file(), rel
    assert not (root / "src").exists()
    plan_text = (root / "PATCH_PLAN.md").read_text(encoding="utf-8")
    assert "Non-goals" in plan_text and "No new features" in plan_text
    r = _run_generated_pytest(root / "tests", root)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- L3: E5/E6 fail-closed ------------------------------------------------------------


@pytest.mark.parametrize("tier", ["E5", "E6"])
def test_apply_e5_e6_refuses_without_approval(hermetic, tier):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="mvp", tier=tier, project_name=f"nope_{tier.lower()}")
    out = b.apply(job.id)
    assert "Applied job" not in out
    assert not (ws / f"nope_{tier.lower()}").exists()


@pytest.mark.parametrize("tier", ["E5", "E6"])
def test_apply_e5_e6_after_approval(hermetic, tier):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="mvp", tier=tier, project_name=f"ok_{tier.lower()}")
    gate = hitl_mod.HITLGate()
    assert job.hitl_id in gate.pending
    gate.decide(job.hitl_id, "approve", note="regression test")
    # fresh instance = fresh process: the approval must survive the reload
    out = _builder(ws).apply(job.id)
    assert "Applied job" in out, out[:200]
    root = ws / f"ok_{tier.lower()}"
    r = _run_generated_pytest(root / "tests", root / "src")
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-m", f"ok_{tier.lower()}.main", "status"],
        capture_output=True,
        text=True,
        cwd=str(root / "src"),
        timeout=60,
    )
    assert r.returncode == 0 and "MVP OK" in r.stdout


@pytest.mark.parametrize("tier", ["E5", "E6"])
def test_apply_e5_e6_denied_stays_refused(hermetic, tier):
    _, ws = hermetic
    b = _builder(ws)
    job = b.plan(goal="mvp", tier=tier, project_name=f"deny_{tier.lower()}")
    hitl_mod.HITLGate().decide(job.hitl_id, "deny", note="regression test")
    out = _builder(ws).apply(job.id)
    assert "Applied job" not in out
    assert not (ws / f"deny_{tier.lower()}").exists()


def test_job_survives_reload_across_instances(hermetic):
    _, ws = hermetic
    b1 = _builder(ws)
    job = b1.plan(goal="reload", tier="E4", project_name="rl")
    b2 = _builder(ws)  # fresh instance, same HOME
    out = b2.apply(job.id)
    assert "Applied job" in out
