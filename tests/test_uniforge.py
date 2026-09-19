"""Tests for UniForge — the forge that unifies hybrid builds.

Hermetic: no network, no HOME writes. Live-execution tests use
tmp_path fixtures with real ``python3`` subprocesses only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from levi.automation.hitl import auto_approve, auto_deny
from levi.uniforge import BuildPlan, Step, TARGETS, target_ids
from levi.uniforge.ai import (
    BRIDGE_LABEL,
    BridgeError,
    completion_to_plan_request,
    plan_to_completion,
    tool_schemas,
)
from levi.uniforge.cli import cmd_uniforge, register_uniforge_parser
from levi.uniforge.si import assemble_plan, forge, forge_dry_run, plan_readiness
from levi.uniforge import targets as targets_mod


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pkg_root(tmp_path):
    """A minimal honest python package tree."""
    root = tmp_path / "mypkg-src"
    root.mkdir()
    (root / "setup.py").write_text("from setuptools import setup\nsetup()\n")
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("VALUE = 42\n")
    return root


@pytest.fixture()
def site_root(tmp_path):
    root = tmp_path / "site-src"
    root.mkdir()
    (root / "hello.md").write_text("# Hello\n\nWorld.\n")
    (root / "notes.txt").write_text("plain notes\n")
    return root


def _step(tool="python3", sid="s1", depends_on=(), artifacts=(), consequential=False):
    return Step(
        id=sid,
        label="step " + sid,
        target="t",
        tool=tool,
        argv=[tool, "-c", "pass"],
        workdir=".",
        depends_on=list(depends_on),
        artifacts=list(artifacts),
        consequential=consequential,
    )


# ---------------------------------------------------------------------------
# plan assembly + ordering
# ---------------------------------------------------------------------------


def test_targets_registered():
    assert target_ids() == ["android-apk-scaffold", "python-package", "static-site"]
    for tid in target_ids():
        t = TARGETS[tid]
        assert t["required_tools"], tid
        assert t["honesty_note"], tid
        assert callable(t["make_steps"])


def test_assemble_plan_known_targets(pkg_root):
    plan = assemble_plan(["python-package", "static-site"], str(pkg_root))
    assert plan.targets == ["python-package", "static-site"]
    assert len(plan.steps) == 5  # 3 + 2
    ids = plan.step_ids()
    assert len(set(ids)) == len(ids)  # unique across targets
    # dependency order holds
    order = [s.id for s in plan.ordered_steps()]
    assert (
        order.index("python-package:1-verify-layout")
        < order.index("python-package:2-compile")
        < order.index("python-package:3-manifest")
    )


def test_assemble_plan_unknown_target_raises(pkg_root):
    with pytest.raises(ValueError, match="unknown target"):
        assemble_plan(["warp-drive"], str(pkg_root))


def test_ordering_cycle_raises():
    plan = BuildPlan(
        name="cycle",
        targets=["t"],
        steps=[_step(sid="a", depends_on=["b"]), _step(sid="b", depends_on=["a"])],
    )
    with pytest.raises(ValueError, match="cycle"):
        plan.ordered_steps()


def test_unknown_dependency_raises():
    plan = BuildPlan(
        name="bad", targets=["t"], steps=[_step(sid="a", depends_on=["ghost"])]
    )
    with pytest.raises(ValueError, match="unknown step"):
        plan.ordered_steps()


def test_plan_round_trip(pkg_root):
    plan = assemble_plan(["python-package"], str(pkg_root))
    clone = BuildPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
    assert clone.name == plan.name
    assert clone.step_ids() == plan.step_ids()


# ---------------------------------------------------------------------------
# the forge law: dry-run default, refusal, permission, execute, verify
# ---------------------------------------------------------------------------


def test_dry_run_is_default_and_side_effect_free(pkg_root):
    plan = assemble_plan(["python-package"], str(pkg_root))
    receipt = forge(plan)  # live defaults to False
    assert receipt["decision"] == "dry-run"
    assert receipt["organ"] == "uniforge"
    assert not (pkg_root / "dist").exists()
    assert receipt["stages"]["permission"]["decision"] == "not-requested"


def test_forge_dry_run_helper(pkg_root):
    plan = assemble_plan(["static-site"], str(pkg_root))
    receipt = forge_dry_run(plan)
    assert receipt["decision"] == "dry-run"


def test_missing_tool_refuses_before_permission(pkg_root):
    plan = BuildPlan(
        name="refuse",
        targets=["t"],
        steps=[_step(tool="definitely-not-a-real-tool-xyz")],
    )

    def _boom(request):
        raise AssertionError("permission must not be asked on refusal")

    receipt = forge(plan, live=True, responder=_boom)
    assert receipt["decision"] == "refused"
    assert "definitely-not-a-real-tool-xyz" in receipt["note"]
    assert "permission" not in receipt["stages"]


def test_permission_denied_executes_nothing(pkg_root):
    plan = assemble_plan(["python-package"], str(pkg_root))
    receipt = forge(plan, live=True, responder=auto_deny)
    assert receipt["decision"] == "denied"
    assert not (pkg_root / "dist").exists()
    assert receipt["stages"]["permission"]["decision"] == "denied"


def test_live_execute_python_package(pkg_root):
    plan = assemble_plan(["python-package"], str(pkg_root))
    assert plan_readiness(plan)["ready"]
    receipt = forge(plan, live=True, responder=auto_approve, workdir=str(pkg_root))
    assert receipt["decision"] == "executed", receipt
    assert receipt["verified"] is True
    manifest = pkg_root / "dist" / "BUILD_MANIFEST.txt"
    assert manifest.exists()
    assert "modules: 2" in manifest.read_text()


def test_failed_step_receipt():
    plan = BuildPlan(
        name="fail",
        targets=["t"],
        steps=[
            Step(
                id="s1",
                label="boom",
                target="t",
                tool="python3",
                argv=["python3", "-c", "import sys; sys.exit(3)"],
                workdir=".",
            )
        ],
    )
    receipt = forge(plan, live=True, responder=auto_approve)
    assert receipt["decision"] == "failed"
    assert "s1" in receipt["note"]
    assert receipt["steps"][0]["status"] == "failed"
    assert receipt["steps"][0]["result"]["returncode"] == 3


def test_verify_failure_recorded_not_hidden():
    plan = BuildPlan(
        name="unverifiable",
        targets=["t"],
        steps=[_step(sid="s1", artifacts=["dist/never-written.txt"])],
    )
    receipt = forge(plan, live=True, responder=auto_approve)
    assert receipt["decision"] == "executed"
    assert receipt["verified"] is False
    finding = receipt["stages"]["verify"]["steps"][0]["findings"][0]
    assert finding["artifact"] == "dist/never-written.txt"
    assert finding["exists"] is False


def test_consequential_step_gets_own_gate():
    # Run-level gate approves; the consequential step's own gate denies.
    calls = {"n": 0}

    def split_responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"decision": "approved", "note": "run approved"}
        return {"decision": "denied", "note": "step refused"}

    plan = BuildPlan(
        name="conseq",
        targets=["t"],
        steps=[_step(sid="s1", consequential=True)],
    )
    denied = forge(plan, live=True, responder=split_responder)
    assert denied["decision"] == "failed"
    assert denied["steps"][0]["status"] == "denied"
    assert denied["steps"][0]["gate"]["decision"] == "denied"
    approved = forge(plan, live=True, responder=auto_approve)
    assert approved["steps"][0]["status"] == "done"
    assert approved["steps"][0]["gate"]["decision"] == "approved"


def test_android_target_honesty():
    steps = targets_mod.make_steps("android-apk-scaffold", "/tmp/x", "n")
    assert any(s.tool == "gradle" for s in steps)
    assert any(s.consequential for s in steps)
    assert "--offline" in steps[-1].argv  # never silently hits the network


# ---------------------------------------------------------------------------
# SI / AI separation + bridge labels
# ---------------------------------------------------------------------------


def test_si_never_imports_ai():
    # Clean-interpreter check: importing the SI core must not pull the
    # AI bridge in. (The test module itself imports the bridge, so we
    # cannot use sys.modules of this process.)
    import subprocess

    code = (
        "import sys; sys.path.insert(0, 'core');"
        "import levi.uniforge.si, levi.uniforge.si.planner,"
        " levi.uniforge.si.executor;"
        "assert 'levi.uniforge.ai' not in sys.modules, 'si imported ai';"
        "print('clean')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "clean" in proc.stdout
    # Source check: no *import statement* in si/ may reference the ai
    # package (docstrings may mention it — that is not an import).
    import re as _re

    _import_ai = _re.compile(r"^\s*(from|import)\s+[\w.]*\bai\b")
    si_dir = Path(targets_mod.__file__).parent / "si"
    for path in si_dir.glob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert not _import_ai.match(line), (path, lineno, line)


def test_bridge_carries_its_label():
    expected = (
        "AI counterpart bridge for uniforge — conventional-protocol "
        "interface; the SI core is authoritative; this bridge claims nothing"
    )
    assert BRIDGE_LABEL == expected
    bridge_src = Path(targets_mod.__file__).parent / "ai" / "bridge.py"
    assert expected in bridge_src.read_text()


def test_bridge_tool_schemas():
    schemas = tool_schemas()
    names = [s["name"] for s in schemas]
    assert names == ["uniforge.plan", "uniforge.build"]
    for s in schemas:
        assert "SI core is authoritative" in s["description"]


def test_bridge_completion_round_trip(pkg_root):
    plan = assemble_plan(["python-package"], str(pkg_root))
    completion = plan_to_completion(plan.to_dict())
    assert completion["object"] == "chat.completion"
    assert completion["bridge"] == BRIDGE_LABEL
    assert completion["choices"][0]["message"]["role"] == "assistant"
    req = completion_to_plan_request(completion)
    assert req["targets"] == ["python-package"]
    assert req["bridge"] == BRIDGE_LABEL


def test_bridge_refuses_unmarked_completion():
    with pytest.raises(BridgeError, match="marker"):
        completion_to_plan_request(
            {"choices": [{"message": {"content": "Targets: python-package"}}]}
        )
    with pytest.raises(BridgeError, match="chat-completions"):
        completion_to_plan_request({})


def test_no_network_imports_in_uniforge():
    base = Path(targets_mod.__file__).parent
    banned = ("import socket", "urllib", "requests", "http.client")
    for path in list(base.glob("*.py")) + list((base / "si").glob("*.py")):
        src = path.read_text()
        for token in banned:
            assert token not in src, (path, token)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def _parser():
    p = argparse.ArgumentParser(prog="levi")
    sub = p.add_subparsers(dest="_top")
    register_uniforge_parser(sub)
    return p


def test_cli_plan_parses_and_previews(pkg_root, capsys):
    args = _parser().parse_args(
        ["uniforge", "plan", "--target", "python-package", "--workdir", str(pkg_root)]
    )
    assert cmd_uniforge(args) == 0
    out = capsys.readouterr().out
    assert "BuildPlan" in out
    assert "byte-compile all modules" in out


def test_cli_plan_unknown_target_fails(capsys):
    args = _parser().parse_args(["uniforge", "plan", "--target", "warp-drive"])
    assert cmd_uniforge(args) == 2


def test_cli_build_dry_run(pkg_root, capsys):
    args = _parser().parse_args(
        ["uniforge", "build", "--target", "static-site", "--workdir", str(pkg_root)]
    )
    assert cmd_uniforge(args) == 0
    assert "dry-run" in capsys.readouterr().out


def test_cli_build_live_yes_executes(pkg_root, tmp_path, capsys):
    receipt_path = tmp_path / "receipt.json"
    args = _parser().parse_args(
        [
            "uniforge",
            "build",
            "--target",
            "python-package",
            "--workdir",
            str(pkg_root),
            "--live",
            "--yes",
            "--receipt",
            str(receipt_path),
        ]
    )
    assert cmd_uniforge(args) == 0
    receipt = json.loads(receipt_path.read_text())
    assert receipt["decision"] == "executed"
    assert receipt["verified"] is True
