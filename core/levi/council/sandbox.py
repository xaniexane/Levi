"""Jailed candidate execution for the council.

Conventions reused from ``levi.agent.tools`` ``python_exec``: the
candidate runs in a subprocess with cwd confined to a per-run scratch
directory, a scrubbed environment (no proxy vars, no secret-looking
vars — candidates must never see the council's API keys), stdin closed,
and a hard timeout.

Honest scope (same as ``python_exec``): process isolation, not a
seccomp sandbox. Treat as untrusted-code containment, not a security
boundary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_RUNNER = '''\
"""Council test runner: imports candidate + tests, runs test_* callables."""
import json
import sys
import traceback

sys.path.insert(0, ".")

results = {"passed": [], "failed": [], "error": ""}

try:
    import candidate
except Exception:
    results["error"] = "candidate import failed:\\n" + traceback.format_exc(limit=5)
    print(json.dumps(results))
    raise SystemExit(0)

try:
    import tests as t
except Exception:
    results["error"] = "tests import failed:\\n" + traceback.format_exc(limit=5)
    print(json.dumps(results))
    raise SystemExit(0)

names = [n for n in sorted(dir(t)) if n.startswith("test_")]
if not names:
    results["error"] = "no test_* callables found in tests module"
    print(json.dumps(results))
    raise SystemExit(0)

for name in names:
    fn = getattr(t, name)
    if not callable(fn):
        continue
    try:
        fn()
        results["passed"].append(name)
    except Exception:
        results["failed"].append(
            {"name": name, "error": traceback.format_exc(limit=4)}
        )

print(json.dumps(results))
'''


@dataclass
class ExecResult:
    ok: bool  # runner itself completed (not: tests passed)
    passed: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    error: str = ""  # runner/import/timeout level failure
    elapsed_s: float = 0.0
    timed_out: bool = False

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed)

    @property
    def pass_rate(self) -> float:
        return (len(self.passed) / self.total) if self.total else 0.0

    def summary(self) -> str:
        if self.timed_out:
            return f"timed out after {self.elapsed_s:.1f}s"
        if self.error:
            return f"runner error: {self.error.splitlines()[0][:160]}"
        return f"{len(self.passed)} passed, {len(self.failed)} failed"


def _scrubbed_env() -> dict[str, str]:
    """Copy of os.environ minus proxy vars and anything secret-shaped.

    Council API keys live in this process's environment; candidate code
    must never be able to read them.
    """
    drop_substrings = (
        "_proxy",
        "key",
        "token",
        "secret",
        "password",
        "credential",
        "auth",
    )
    env = {}
    for k, v in os.environ.items():
        kl = k.lower()
        if any(s in kl for s in drop_substrings):
            continue
        env[k] = v
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    return env


def council_root() -> Path:
    return Path.home() / ".levi" / "council" / "runs"


def run_candidate(
    code: str,
    tests_code: str,
    timeout: float = 30.0,
    run_id: str | None = None,
    seat: str = "unknown",
) -> ExecResult:
    """Execute ``code`` against ``tests_code`` in a jailed subprocess.

    Returns an ExecResult; never raises on candidate misbehavior
    (timeouts and crashes become structured results).
    """
    if timeout <= 0 or timeout > 120:
        raise ValueError("timeout must be in (0, 120]")
    run_id = run_id or uuid.uuid4().hex[:12]
    scratch = council_root() / run_id / "seats" / seat
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "candidate.py").write_text(code, encoding="utf-8")
    (scratch / "tests.py").write_text(tests_code, encoding="utf-8")
    runner = scratch / "_runner.py"
    runner.write_text(_RUNNER, encoding="utf-8")

    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(runner)],
            cwd=str(scratch),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=_scrubbed_env(),
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return ExecResult(
            ok=False,
            timed_out=True,
            elapsed_s=time.time() - t0,
            error=f"timed out after {timeout}s",
        )
    except OSError as exc:
        return ExecResult(ok=False, error=f"failed to run: {exc}")
    elapsed = time.time() - t0

    out = (proc.stdout or "").strip()
    # The runner prints exactly one JSON line last; tolerate stray output.
    payload: dict | None = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                break
            except Exception:
                continue
    if payload is None:
        err = (proc.stderr or "").strip().splitlines()
        detail = err[-1][:300] if err else "no JSON output from runner"
        return ExecResult(ok=False, error=detail, elapsed_s=elapsed)
    return ExecResult(
        ok=True,
        passed=list(payload.get("passed", [])),
        failed=list(payload.get("failed", [])),
        error=str(payload.get("error", "")),
        elapsed_s=elapsed,
    )
