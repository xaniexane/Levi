"""ops.errors: structured error surface, wired into the CLI dispatch.

Hermetic: no network. The subprocess test redirects HOME to a temp dir.
"""
import os
import subprocess
import sys
from pathlib import Path

from levi.ops.errors import GateError, LeviError, PersistError, safe_call

ROOT = Path(__file__).resolve().parents[1]


def test_levi_error_format():
    err = LeviError(code="cli:status", message="boom", recoverable=True)
    line = err.format()
    assert "[LEVI:cli:status]" in line
    assert "recoverable" in line
    assert "boom" in line


def test_levi_error_fatal_flag():
    err = LeviError(code="x", message="y", recoverable=False)
    assert "FATAL" in err.format()


def test_safe_call_returns_default_and_logs():
    log = []
    out = safe_call("demo", lambda: 1 / 0, default="fallback", log=log)
    assert out == "fallback"
    assert len(log) == 1
    assert log[0].code == "demo"


def test_safe_call_passthrough_on_success():
    assert safe_call("demo", lambda: 42) == 42


def test_error_classes_are_exceptions():
    assert issubclass(PersistError, Exception)
    assert issubclass(GateError, Exception)


def test_cli_dispatch_reports_structured_error():
    # End-to-end through the real CLI: an unknown story id raises KeyError
    # inside the handler; the dispatch catch-all must print a structured
    # LeviError line (not a raw traceback) and exit 1. Hermetic: HOME is
    # redirected to a temp dir.
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ)
        env["HOME"] = home
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
        proc = subprocess.run(
            [sys.executable, "-m", "levi.cli.main", "story", "--expand", "no-such-story"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert proc.returncode == 1, proc.stderr
    assert "[LEVI:cli:story]" in proc.stderr, proc.stderr
    assert "Traceback" not in proc.stderr
