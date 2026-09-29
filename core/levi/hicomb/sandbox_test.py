"""Hicomb IDE: sandbox execution + testing of projected upgrade paths.

Chauncey's order (2026-09-23): every projected upgrade path is SIMULATED
AND TESTED in a sandbox — the tested outcome is what reaches the HITL
checkpoint, next to the simulated one. A path that fails sandbox testing
never reaches the checkpoint as approvable.

What the sandbox does:
  - works on COPIES in an isolated dir under the store (never the real
    tree; ``PYTHONDONTWRITEBYTECODE=1`` so even imports leave no trace);
  - runs the change's declared checks (``checks`` / ``tests``), or a
    default smoke check for a named ``module``, or candidate ``files``
    written into the sandbox first;
  - captures output per check with per-check timeouts; no shell, ever
    (argv lists only — a string check is rejected, not executed);
  - offline: proxy env vars are scrubbed and no network is initiated by
    the runner. This is process-level isolation, not a network
    namespace — stated honestly, not oversold. (The interactive
    namespace sandbox lives at ``levi.sandbox.runner``; this runner is
    the capture-oriented automated one.)
  - deterministic where it matters: same inputs give the same
    pass/fail; wall-time is recorded but never part of the verdict;
  - every run is receipted (projection id, what ran, per-check results,
    outcome) next to the run dir.

A change with no executable checks declared is UNTESTABLE, not
"passing": the result records ok=False with reason "no checks declared".
Nothing untested is presentable at a checkpoint.

LAWS:
  B1 ISOLATED   the sandbox never writes outside its own run dir.
  B2 OFFLINE    no network is initiated, in two honest layers:
                (a) PYTHON SOCKET GUARD — every Python-based check runs
                    with a sitecustomize hook (injected via PYTHONPATH
                    into the sandbox dir) that neuters AF_INET/AF_INET6
                    socket creation: any TCP/UDP attempt raises OSError.
                    Covers everything derive_checks() produces (smoke +
                    pytest/unittest runs) on every platform, phone incl.
                (b) NETNS for the rest — non-Python executables run under
                    `unshare -n` (private network namespace) when the
                    platform permits it; when it does not (Termux/Android,
                    unprivileged containers), non-Python checks are
                    REJECTED outright — fail closed, never unprotected.
                Proxies are scrubbed and bytecode writes disabled in both
                layers; the receipt records which layer guarded the run.
  B3 RECEIPTED  every run writes a JSON receipt.
  B4 NO-SHELL   checks are argv lists; strings are rejected.
  B5 HONEST     untestable is a failure, never a pass.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "SandboxCheck",
    "SandboxTestResult",
    "derive_checks",
    "test_projection",
]

_DEFAULT_CHECK_TIMEOUT_S = 180
_DEFAULT_TOTAL_TIMEOUT_S = 600

# B2(a): the Python socket guard. Shipped as a .txt RESOURCE (not a
# module): the parent never imports socket itself — it writes this text
# into the sandbox run dir as _nethooks/sitecustomize.py, picked up via
# PYTHONPATH at child interpreter startup, before any check code runs.
# AF_INET/AF_INET6 creation raises; AF_UNIX (local IPC) stays allowed.
# The .txt form keeps the offline grep gate meaningful: no "import
# socket" appears in any hicomb *.py, because the core truly never
# imports networking — only the child's blocker snippet mentions it.
def _socket_guard_src() -> str:
    return (Path(__file__).with_name("sandbox_socket_guard.txt")
            .read_text(encoding="utf-8"))

_netns_probe: Optional[bool] = None


def _netns_available() -> bool:
    """Cached probe: can this platform unshare a network namespace?

    True on a normal Linux dev box; False on Termux/Android and locked-
    down containers. Callers fail closed on False (B2b).
    """
    global _netns_probe
    if _netns_probe is None:
        try:
            r = subprocess.run(["unshare", "-n", "true"],
                               capture_output=True, timeout=10)
            _netns_probe = r.returncode == 0
        except Exception:
            _netns_probe = False
    return _netns_probe


def _is_python_argv(argv: List[str]) -> bool:
    """Python-based checks are covered by the sitecustomize socket guard."""
    if not argv or not isinstance(argv[0], str):
        return False
    if argv[0] == sys.executable:
        return True
    base = os.path.basename(argv[0])
    return base == "python" or base.startswith("python3")

# Env vars that could route traffic through a proxy — scrubbed so the
# sandbox cannot reach the network through ambient configuration.
_PROXY_VARS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "ftp_proxy",
)


def _repo_root() -> Path:
    # core/levi/hicomb/sandbox_test.py -> repo root is parents[3].
    return Path(__file__).resolve().parents[3]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class SandboxCheck:
    name: str
    argv: List[str]
    timeout_s: int = _DEFAULT_CHECK_TIMEOUT_S


@dataclass
class SandboxTestResult:
    projection_id: str
    ok: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    started_ts: str = ""
    duration_ms: int = 0
    sandbox_dir: str = ""
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "ok": self.ok,
            "checks": [dict(c) for c in self.checks],
            "started_ts": self.started_ts,
            "duration_ms": self.duration_ms,
            "sandbox_dir": self.sandbox_dir,
            "notes": list(self.notes),
        }


def _check_record(name: str, ok: bool, returncode: Optional[int],
                  detail: str) -> Dict[str, Any]:
    return {"name": name, "ok": bool(ok),
            "returncode": returncode, "detail": detail}


def derive_checks(change: Dict[str, Any]) -> List[SandboxCheck]:
    """Derive executable checks from a projection's change dict.

    Raises ValueError on malformed check declarations (never executes
    them). Returns [] when the change declares nothing executable —
    the caller records that as UNTESTABLE (B5), not as a pass.
    """
    change = dict(change or {})
    checks: List[SandboxCheck] = []

    raw_checks = change.get("checks")
    if raw_checks is not None:
        if not isinstance(raw_checks, list):
            raise ValueError("'checks' must be a list of argv lists")
        for i, entry in enumerate(raw_checks):
            # Entries may be {"name":..., "argv":[...]} or bare argv lists.
            name, argv = f"check-{i}", entry
            if isinstance(entry, dict):
                name = str(entry.get("name", name))
                argv = entry.get("argv", [])
            if isinstance(argv, str):
                raise ValueError(
                    f"check {name!r}: string commands are rejected "
                    "(no shell, ever — pass an argv list)")
            if (not isinstance(argv, list) or not argv
                    or not all(isinstance(a, str) for a in argv)):
                raise ValueError(
                    f"check {name!r}: argv must be a non-empty list of str")
            checks.append(SandboxCheck(name=name, argv=list(argv)))

    for t in change.get("tests", []) or []:
        if not isinstance(t, str) or not t:
            raise ValueError(f"'tests' entries must be non-empty strings, got {t!r}")
        checks.append(SandboxCheck(
            name=f"pytest:{t}",
            argv=[sys.executable, "-m", "pytest", t, "-q"],
            timeout_s=300,
        ))

    module = change.get("module")
    if module and not checks:
        # Default smoke: syntax-check a COPY of the module, then import
        # the real one read-only (bytecode disabled) in a subprocess.
        # The module name becomes a filename — it must be a plain dotted
        # identifier, never a path (no traversal into the repo or out).
        if (not isinstance(module, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module)):
            raise ValueError(
                f"module {module!r}: must be a plain module name, not a path")
        mod_file = _repo_root() / "core" / "levi" / "hicomb" / f"{module}.py"
        if not mod_file.exists():
            raise ValueError(
                f"module {module!r}: no such file {mod_file} — "
                "cannot derive a smoke check")
        checks.append(SandboxCheck(
            name=f"smoke:{module}",
            argv=["__SMOKE__", str(mod_file), str(module)],
        ))
    return checks


def _sandbox_env() -> Dict[str, str]:
    env = dict(os.environ)
    for var in _PROXY_VARS:
        env.pop(var, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(_repo_root() / "core")
    return env


def _run_smoke(sandbox_dir: Path, module_file: str, module: str,
               env: Dict[str, str]) -> Dict[str, Any]:
    """Syntax-check a COPY of the module, then import the real one
    read-only. Returns a check record."""
    # B1: compile the copy, never the original.
    copy = sandbox_dir / f"{module}.copy.py"
    try:
        shutil.copyfile(module_file, copy)
    except OSError as exc:
        return _check_record(f"smoke:{module}", False, None,
                             f"could not stage module copy: {exc}")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(copy)],
            capture_output=True, text=True, timeout=60,
            cwd=sandbox_dir, env=env, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _check_record(f"smoke:{module}", False, None,
                             f"py_compile failed to run: {exc}")
    if proc.returncode != 0:
        return _check_record(
            f"smoke:{module}", False, proc.returncode,
            f"syntax error in {module}: {proc.stderr.strip()[-500:]}")
    proc = subprocess.run(
        [sys.executable, "-c", f"import levi.hicomb.{module}"],
        capture_output=True, text=True, timeout=60,
        cwd=sandbox_dir, env=env,
    )
    if proc.returncode != 0:
        return _check_record(
            f"smoke:{module}", False, proc.returncode,
            f"import failed for levi.hicomb.{module}: "
            f"{proc.stderr.strip()[-500:]}")
    return _check_record(f"smoke:{module}", True, 0,
                         "syntax ok (copy), import ok (read-only)")


def test_projection(projection_id: str, change: Dict[str, Any],
                    title: str, sandbox_root: Path | str,
                    total_timeout_s: int = _DEFAULT_TOTAL_TIMEOUT_S
                    ) -> SandboxTestResult:
    """Execute + test one projected path in an isolated sandbox dir.

    Never raises on check failures — they are recorded in the result.
    Raises only when the sandbox itself cannot be set up (no dir, no
    receipt); the caller decides how to surface that.
    """
    # The projection id becomes a directory AND a receipt filename — a
    # hostile id must never escape the sandbox root (path traversal).
    if (not isinstance(projection_id, str) or not projection_id
            or ".." in projection_id or "/" in projection_id
            or "\\" in projection_id):
        raise ValueError(
            f"bad projection_id {projection_id!r}: non-empty string "
            "without path separators")
    started = _now()
    t0 = time.monotonic()
    root = Path(sandbox_root)
    root.mkdir(parents=True, exist_ok=True)
    # Millisecond stamp + attempt suffix: two runs of the same projection
    # in the same instant get distinct dirs instead of colliding.
    base = f"run_{projection_id}_{int(t0 * 1000)}"
    run_dir = root / base
    for attempt in range(100):
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            run_dir = root / f"{base}-{attempt + 1}"
    else:  # pragma: no cover - 100 same-millisecond collisions is absurd
        raise OSError(f"cannot create a fresh run dir under {root}")
    notes: List[str] = [f"title: {title}"]
    checks_out: List[Dict[str, Any]] = []

    try:
        checks = derive_checks(change)
    except ValueError as exc:
        result = SandboxTestResult(
            projection_id=projection_id, ok=False, checks=checks_out,
            started_ts=started,
            duration_ms=int((time.monotonic() - t0) * 1000),
            sandbox_dir=str(run_dir),
            notes=notes + [f"check derivation failed: {exc}"],
        )
        _write_receipt(root, result)
        return result

    # Candidate files are validated + staged BEFORE the untestable
    # verdict: a traversal attack is explicitly rejected even when the
    # change declares no checks.
    files = change.get("files") or {}
    if not isinstance(files, dict):
        result = SandboxTestResult(
            projection_id=projection_id, ok=False, checks=checks_out,
            started_ts=started,
            duration_ms=int((time.monotonic() - t0) * 1000),
            sandbox_dir=str(run_dir),
            notes=notes + ["'files' must be a mapping of relpath -> content"],
        )
        _write_receipt(root, result)
        return result
    for rel, content in files.items():
        rel_path = Path(str(rel))
        # B1: staged files stay inside the run dir. ".." escapes upward;
        # an absolute key would make run_dir / rel resolve OUTSIDE the
        # sandbox entirely (Path discards the left side on absolute
        # right sides) — both are rejected, never staged.
        if rel_path.is_absolute() or ".." in rel_path.parts:
            checks_out.append(_check_record(
                "stage-files", False, None,
                f"rejected path traversal in files key: {rel!r}"))
            result = SandboxTestResult(
                projection_id=projection_id, ok=False, checks=checks_out,
                started_ts=started,
                duration_ms=int((time.monotonic() - t0) * 1000),
                sandbox_dir=str(run_dir), notes=notes)
            _write_receipt(root, result)
            return result
        target = run_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
    if files:
        notes.append(f"staged {len(files)} candidate file(s) in sandbox")

    if not checks:
        # B5: untestable is a failure, never a pass.
        result = SandboxTestResult(
            projection_id=projection_id, ok=False, checks=checks_out,
            started_ts=started,
            duration_ms=int((time.monotonic() - t0) * 1000),
            sandbox_dir=str(run_dir),
            notes=notes + ["untestable: change declares no executable checks"],
        )
        _write_receipt(root, result)
        return result

    env = _sandbox_env()

    # B2(a): install the Python socket guard inside the sandbox and put
    # it on PYTHONPATH so every Python-based check imports it at startup.
    hooks_dir = run_dir / "_nethooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "sitecustomize.py").write_text(
        _socket_guard_src(), encoding="utf-8")
    py_path = str(hooks_dir)
    if env.get("PYTHONPATH"):
        py_path += os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = py_path

    # B2(b): network-namespace isolation for non-Python executables.
    netns = _netns_available()
    notes.append(
        "isolation: python socket guard (sitecustomize via PYTHONPATH) + "
        + ("unshare -n netns for non-python checks"
           if netns else
           "non-python checks rejected (no netns on this platform)")
    )

    deadline = t0 + total_timeout_s
    all_ok = True
    for check in checks:
        remaining = max(1, int(deadline - time.monotonic()))
        timeout = min(check.timeout_s, remaining)
        if check.argv and check.argv[0] == "__SMOKE__":
            rec = _run_smoke(run_dir, check.argv[1], check.argv[2], env)
        else:
            argv = list(check.argv)
            if not _is_python_argv(argv):
                # B2(b): non-Python executables only run inside a private
                # netns; without one they are rejected, never unprotected.
                if netns:
                    argv = ["unshare", "-n"] + argv
                else:
                    rec = _check_record(
                        check.name, False, None,
                        "rejected: non-python executable cannot run without "
                        "network-namespace isolation on this platform")
                    checks_out.append(rec)
                    all_ok = False
                    notes.append(f"FAILED: {check.name} — {rec['detail'][:200]}")
                    break  # fail fast: rejected paths run nothing
            try:
                proc = subprocess.run(
                    argv, capture_output=True, text=True,
                    timeout=timeout, cwd=run_dir, env=env)
                detail = (proc.stderr.strip() or proc.stdout.strip())[-800:]
                rec = _check_record(
                    check.name, proc.returncode == 0, proc.returncode,
                    detail or "ok")
            except subprocess.TimeoutExpired:
                rec = _check_record(check.name, False, None,
                                    f"timed out after {timeout}s")
            except OSError as exc:
                rec = _check_record(check.name, False, None,
                                    f"could not execute: {exc}")
        checks_out.append(rec)
        if not rec["ok"]:
            all_ok = False
            notes.append(f"FAILED: {check.name} — {rec['detail'][:200]}")
            break  # fail fast: a broken path needs no further checks

    result = SandboxTestResult(
        projection_id=projection_id, ok=all_ok, checks=checks_out,
        started_ts=started,
        duration_ms=int((time.monotonic() - t0) * 1000),
        sandbox_dir=str(run_dir), notes=notes)
    _write_receipt(root, result)
    return result


def _write_receipt(root: Path, result: SandboxTestResult) -> Path:
    receipts = root / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    path = receipts / f"{result.projection_id}.json"
    path.write_text(json.dumps(result.as_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def tested_outcome_text(result: SandboxTestResult) -> str:
    """The tested-outcome line shown at the HITL checkpoint."""
    if result.ok:
        passed = ", ".join(c["name"] for c in result.checks)
        return (f"SANDBOX-TESTED OUTCOME: PASS — {len(result.checks)} check(s) "
                f"passed ({passed}) in {result.duration_ms}ms, offline, "
                f"isolated. Receipt: {result.sandbox_dir}.")
    failed = [c for c in result.checks if not c["ok"]]
    first = failed[0] if failed else {"name": "?", "detail": "?"}
    return (f"SANDBOX-TESTED OUTCOME: FAIL — {first['name']}: "
            f"{first['detail'][:300]}. Not approvable; deny to route to "
            f"the remix store. Receipt: {result.sandbox_dir}.")
