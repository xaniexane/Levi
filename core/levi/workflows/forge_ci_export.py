"""forge-ci-export: local CI run -> full one-command export.

LEV Forge's own loop, in its own honest terms (not the factory line):
take a repo in the forge, run its CI pipeline locally (no minute metering,
no network), and — only on a green run — export the whole repo
(code bundle, issues, PRs, stars, CI records) to a portable directory.

Steps:
  init    — validate the repo name, create the repo when it does not exist
            (reused honestly when it does), write the CI pipeline
            (custom ``pipeline=`` dict, or the default git-only pipeline)
  ci_run  — run_pipeline in a fresh clone; a red run fails the workflow
            honestly with the failed step names (no export off a red build)
  export  — export_repo to a fresh destination dir (defaults under
            <home>/forge-exports/<repo>-<run-id>); verified by the
            presence of the git bundle

Adapters only: every call goes to the real forge.* APIs. stdlib-only,
local-first, offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.forge import ci as _ci
from levi.forge import export as _export
from levi.forge import repos as _repos
from levi.forge.gitx import GitError

from ._common import (
    emit,
    finish_step,
    new_step,
    resolve_home,
    workflow_env,
    workflow_result,
)

NAME = "forge-ci-export"
SUMMARY = (
    "Local CI gate then full one-command export: run a Forge repo's "
    "pipeline locally (fresh clone, no network), and on a green run export "
    "everything (code bundle, issues, PRs, stars, CI records) to a "
    "portable directory. A red CI run fails honestly — no export off a "
    "red build."
)
STEP_NAMES = ["init", "ci_run", "export"]


def run(home=None, repo: Optional[str] = None, description: str = "",
        pipeline: Optional[Dict[str, Any]] = None,
        dest: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    levi_home = resolve_home(home)
    fhome = str(levi_home / "forge")  # the forge's own home, explicit
    emit("workflow.start", {"workflow": NAME, "home": str(levi_home),
                            "repo": repo})
    steps: List[Dict[str, Any]] = []
    artifacts: Dict[str, Any] = {}
    run_id: Optional[str] = None

    # -- init --------------------------------------------------------------
    step = new_step("init")
    try:
        if not repo:
            raise ValueError("forge-ci-export: 'repo' name is required")
        with workflow_env(levi_home, growth=False):
            if _repos.repo_exists(fhome, repo):
                created = False
            else:
                _repos.create_repo(fhome, repo, description=description)
                created = True
            pipe = _ci.init_pipeline(fhome, repo, pipeline=pipeline)
        finish_step(step, True, {"repo": repo, "created": created,
                                 "pipeline": pipe.get("name", ""),
                                 "pipeline_steps": len(pipe.get("steps", []))})
        artifacts["repo"] = repo
        artifacts["repo_created"] = created
    except (ValueError, GitError) as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- ci_run ------------------------------------------------------------
    step = new_step("ci_run")
    try:
        with workflow_env(levi_home, growth=False):
            record = _ci.run_pipeline(fhome, repo)
        run_id = record.get("id")
        if not record.get("ok"):
            failed = [s.get("name") for s in record.get("steps", [])
                      if s.get("rc") != 0]
            raise RuntimeError("CI run %s failed at: %s"
                               % (run_id, ", ".join(failed) or "unknown"))
        finish_step(step, True, {"run_id": run_id,
                                 "steps": len(record.get("steps", []))})
        artifacts["ci_run_id"] = run_id
        artifacts["ci_record"] = record
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- export ------------------------------------------------------------
    step = new_step("export")
    try:
        out = (dest or str(
            levi_home / "forge-exports" / ("%s-%s" % (repo, run_id))))
        with workflow_env(levi_home, growth=False):
            export_path = _export.export_repo(fhome, repo, out)
        if not (export_path / "repo.bundle").is_file():
            raise RuntimeError("export finished but repo.bundle is missing: %s"
                               % export_path)
        finish_step(step, True, {"dest": str(export_path),
                                 "run_id": run_id})
        artifacts["export_path"] = str(export_path)
        artifacts["exported_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    emit("workflow.done", {"workflow": NAME, "ok": True, "repo": repo,
                           "run_id": run_id})
    return workflow_result(NAME, steps, artifacts)
