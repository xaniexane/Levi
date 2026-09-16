"""Local-first CI — pipelines run on YOUR machine, not a cloud.

Pipeline format (JSON, ``ci/<name>/pipeline.json``)::

    {
      "version": 1,
      "name": "default",
      "steps": [
        {"name": "tests", "run": "python -m pytest -q",
         "shell": false, "timeout": 600, "env": {"FOO": "bar"}}
      ]
    }

* ``run`` is split with :mod:`shlex` unless ``"shell": true`` (your machine,
  your responsibility — documented in FORGE.md).
* Steps run in a fresh clone of the repo, sequentially, each with its own
  captured log. There is no minute metering, no queue, no cloud, no account.

Run records and logs live under ``ci/<name>/runs/`` and ride along in
exports, so a project's CI history is portable like everything else.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .gitx import GitError, run_git
from .home import forge_home, validate_name
from .jsonl import append_jsonl, read_json, read_jsonl, write_json
from .repos import repo_dir, repo_exists

DEFAULT_TIMEOUT = 300


def pipeline_path(home, name) -> Path:
    return forge_home(home) / "ci" / validate_name(name) / "pipeline.json"


def runs_path(home, name) -> Path:
    return forge_home(home) / "ci" / validate_name(name) / "runs.jsonl"


def _require_repo(home, name) -> str:
    name = validate_name(name)
    if not repo_exists(home, name):
        raise ValueError("no such repo: %r" % name)
    return name


def default_pipeline(name: str) -> dict:
    return {
        "version": 1,
        "name": "default",
        "steps": [
            {"name": "rev-parse", "run": "git rev-parse HEAD", "timeout": 60},
            {"name": "tree", "run": "git ls-tree -r --name-only HEAD", "timeout": 60},
        ],
    }


def init_pipeline(home, name, pipeline: "dict | None" = None) -> dict:
    """Write (or overwrite) the pipeline definition. Validates step shape."""
    name = _require_repo(home, name)
    pipe = pipeline if pipeline is not None else default_pipeline(name)
    _validate_pipeline(pipe)
    write_json(pipeline_path(home, name), pipe)
    return pipe


def load_pipeline(home, name) -> dict:
    name = _require_repo(home, name)
    pipe = read_json(pipeline_path(home, name), None)
    if pipe is None:
        raise ValueError(
            "no pipeline for repo %r — run `levi forge ci %s init` first" % (name, name)
        )
    _validate_pipeline(pipe)
    return pipe


def _validate_pipeline(pipe: dict) -> None:
    if not isinstance(pipe, dict) or not isinstance(pipe.get("steps"), list):
        raise ValueError("pipeline must be an object with a 'steps' list")
    if not pipe["steps"]:
        raise ValueError("pipeline needs at least one step")
    for s in pipe["steps"]:
        if not isinstance(s, dict) or not s.get("name") or not s.get("run"):
            raise ValueError("each step needs 'name' and 'run': %r" % (s,))
        if not isinstance(s["name"], str) or not isinstance(s["run"], str):
            raise ValueError("step 'name' and 'run' must be strings: %r" % (s,))


def list_runs(home, name):
    _require_repo(home, name)
    return list(reversed(read_jsonl(runs_path(home, name))))


def run_pipeline(home, name) -> dict:
    """Run the pipeline in a fresh clone. Returns the run record.

    Exit discipline: every step runs even if an earlier one fails (logs stay
    complete); ``ok`` is False if any step failed.
    """
    name = _require_repo(home, name)
    pipe = load_pipeline(home, name)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-%s" % os.getpid()
    run_dir = forge_home(home) / "ci" / name / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(run_dir, 0o700)

    tmp = Path(tempfile.mkdtemp(prefix="forge-ci-"))
    started = datetime.now(timezone.utc).isoformat()
    step_results = []
    commit = None
    try:
        run_git(["clone", "-q", str(repo_dir(home, name)), str(tmp / "work")])
        work = tmp / "work"
        try:
            commit = run_git(["rev-parse", "HEAD"], cwd=work).stdout.decode().strip()
        except GitError:
            commit = None
        for idx, step in enumerate(pipe["steps"], 1):
            result = _run_step(work, step, idx, run_dir)
            step_results.append(result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ended = datetime.now(timezone.utc).isoformat()
    ok = all(s["rc"] == 0 for s in step_results)
    record = {
        "id": run_id,
        "repo": name,
        "pipeline": pipe.get("name", ""),
        "started": started,
        "ended": ended,
        "commit": commit,
        "ok": ok,
        "steps": step_results,
    }
    write_json(run_dir / "run.json", record)
    append_jsonl(runs_path(home, name), record)
    return record


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "step"


def _run_step(work: Path, step: dict, idx: int, run_dir: Path) -> dict:
    log_name = "step-%02d-%s.log" % (idx, _slug(step["name"]))
    log_path = run_dir / log_name
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (step.get("env") or {}).items()})
    timeout = step.get("timeout", DEFAULT_TIMEOUT)
    if step.get("shell"):
        cmd = step["run"]
        shell = True
    else:
        cmd = shlex.split(step["run"])
        shell = False
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, shell=shell, cwd=str(work), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        rc, out = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as e:
        rc, out = 124, (e.stdout or b"") + b"\n[forge] step timed out after %ss\n" % str(timeout).encode()
    except FileNotFoundError as e:
        rc, out = 127, ("[forge] command not found: %s\n" % e).encode()
    elapsed = time.monotonic() - t0
    log_path.write_bytes(out)
    os.chmod(log_path, 0o600)
    return {
        "name": step["name"],
        "run": step["run"],
        "rc": rc,
        "elapsed": round(elapsed, 2),
        "log": log_name,
    }
