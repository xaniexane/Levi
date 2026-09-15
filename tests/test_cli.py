"""Smoke: the ``levi`` CLI module parses and lists its subcommands.

Runs ``python -m levi.cli.main --help`` as a subprocess (mirrors how the
console script boots: ``levi.cli.main:main``), hermetic — no config touched.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Key subcommands every operator expects to see in --help.
EXPECTED_SUBCOMMANDS = ["init", "ask", "status", "memory-hierarchy", "vault", "serve-ui"]


def _run_help():
    env = dict(os.environ)
    # sys.path is set up by conftest for this process; the subprocess needs it too.
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_help_exits_zero():
    proc = _run_help()
    assert proc.returncode == 0, proc.stderr


def test_cli_help_lists_subcommands():
    proc = _run_help()
    out = proc.stdout
    for sub in EXPECTED_SUBCOMMANDS:
        assert sub in out, f"subcommand {sub!r} missing from --help"


def test_cli_help_shows_usage():
    proc = _run_help()
    assert "usage:" in proc.stdout


def _run_agent_tools():
    env = dict(os.environ)
    # sys.path is set up by conftest for this process; the subprocess needs it too.
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "agent", "tools"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_agent_tools_exits_zero():
    proc = _run_agent_tools()
    assert proc.returncode == 0, proc.stderr


def test_cli_agent_tools_names_key_tools():
    # Keep this hermetic: `agent tools` only lists tools, it never runs
    # the loop or touches the network. (Live `agent run` coverage happens
    # in the manual verification pass, not in pytest.)
    proc = _run_agent_tools()
    out = proc.stdout
    for name in ("file_write", "shell_exec"):
        assert name in out, f"tool {name!r} missing from `levi agent tools`"
    assert "requires confirmation" in out
