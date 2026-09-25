"""CLI smoke for the torch-free model runner: ``levi brain models``.

Subprocess style (mirrors test_cli.py). ``levi brain run`` itself is
exercised through the runtime API in test_brain_runtime.py; the CLI is a
thin wrapper over runtime.run().
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _levi(*argv, timeout=60):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    # Never let CLI smoke tests write to the real observation log.
    env["LEVI_OBSERVATIONS_FILE"] = str(ROOT / "tests" / ".tmp-obs.jsonl")
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_brain_models_lists_levi_native():
    proc = _levi("brain", "models")
    assert proc.returncode == 0, proc.stderr
    assert "levi-native" in proc.stdout
    assert "char-gpt" in proc.stdout
    assert "LEVI native model" in proc.stdout


def test_brain_run_help_shows_runner_flags():
    proc = _levi("brain", "run", "--help")
    assert proc.returncode == 0, proc.stderr
    for flag in ("--model", "--prompt", "--temperature", "--seed", "--no-record"):
        assert flag in proc.stdout, flag
