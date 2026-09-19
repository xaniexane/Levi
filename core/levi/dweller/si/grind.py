"""Dweller tending engine — the labor law, run for real.

The grind queue is the Dweller's tending labor in the depths: the slow,
patient work of purgatory, not generic background work. Every grind
follows the law:

- Sandbox first: every path in the job's params must resolve inside
  the job's ``sandbox_root``. A job with no sandbox root, or with a
  path outside it, is REFUSED — the Dweller never acts on the world
  beyond its sandbox.
- Permission: a HITL-style approval gate (``levi.automation.hitl``
  public classes) before any step runs. Denial ends the job; the job
  stays queued and the receipt says denied.
- Execute: steps run in order through the built-in runners
  (``levi.dweller.runners``) — read-only, hermetic, no network.
- Receipt: ALWAYS produced — executed, dry-run, refused, denied, or
  failed. Saved under the queue's ``receipts/`` dir.

Resuming: :func:`grind` works on a job's pending steps, so a resumed
failed job continues from its first incomplete step. stdlib only;
never imports the AI counterpart bridge.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.automation.hitl import GateKind, GateRequest

from ..jobs import Job, JobStep
from ..queue import get_job, save_job, save_receipt
from .. import runners


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


#: A responder answers a GateRequest without a real human present.
Responder = Callable[[GateRequest], Dict[str, Any]]


def _ask_begin(job: Job, responder: Optional[Responder]) -> Dict[str, Any]:
    req = GateRequest(
        minion_id="dweller",
        kind=GateKind.APPROVAL,
        prompt="Begin grind job %s (%s)?" % (job.id, job.kind),
        context={
            "job_id": job.id,
            "kind": job.kind,
            "steps": [s.to_dict() for s in job.steps],
        },
    )
    if responder is None:
        return {
            "decision": "denied",
            "note": "no responder: fail-closed (grind refused)",
        }
    try:
        out = responder(req)
    except Exception as exc:
        return {"decision": "denied", "note": "responder error: %s" % exc}
    decision = str(out.get("decision", "denied"))
    if decision not in ("approved", "edited", "acknowledged", "noted"):
        decision = "denied"
    return {"decision": decision, "note": str(out.get("note", ""))}


def _job_paths(job: Job) -> List[str]:
    """Every filesystem path the job's params touch, by kind."""
    p = job.params
    if job.kind == "repo-sweep":
        return [str(p.get("root", ""))] if p.get("root") else []
    if job.kind == "crossref":
        return [str(x) for x in list(p.get("set_a", [])) + list(p.get("set_b", []))]
    if job.kind == "watch":
        return [str(p.get("probe_path", ""))] if p.get("probe_path") else []
    return []


def _sandbox_ok(job: Job) -> Optional[str]:
    """None when the sandbox holds; otherwise the refusal reason."""
    if not job.sandbox_root:
        return "no sandbox root: the Dweller does not grind without one"
    root = os.path.realpath(os.path.abspath(job.sandbox_root))
    for path in _job_paths(job):
        target = os.path.realpath(os.path.abspath(path))
        if target != root and not target.startswith(root + os.sep):
            return "path outside sandbox %r: %r" % (job.sandbox_root, path)
    return None


def _probe_condition(probe_path: str, probe_contains: str) -> Callable[[], bool]:
    def condition() -> bool:
        try:
            with open(probe_path, "r", encoding="utf-8", errors="replace") as fh:
                return probe_contains in fh.read()
        except OSError:
            return False

    return condition


def _run_step(
    step: JobStep, job: Job, watch_sleep: Optional[Callable[[float], None]]
) -> Dict[str, Any]:
    """Dispatch one step to its runner. Raises RunnerError on failure."""
    if step.kind == "repo-sweep":
        return runners.run_repo_sweep(
            job.params.get("root", job.sandbox_root),
            sandbox_root=job.sandbox_root,
            include_tests=bool(job.params.get("include_tests", True)),
        )
    if step.kind == "crossref":
        return runners.run_crossref(
            list(job.params.get("set_a", [])),
            list(job.params.get("set_b", [])),
            sandbox_root=job.sandbox_root,
        )
    if step.kind == "watch":
        kwargs: Dict[str, Any] = {
            "times": int(job.params.get("times", 3)),
            "initial_delay_s": float(job.params.get("initial_delay_s", 1.0)),
            "factor": float(job.params.get("factor", 2.0)),
        }
        if watch_sleep is not None:
            kwargs["sleep"] = watch_sleep
        return runners.run_watch(
            _probe_condition(
                str(job.params.get("probe_path", "")),
                str(job.params.get("probe_contains", "")),
            ),
            **kwargs,
        )
    raise runners.RunnerError("unknown runner kind: %r" % step.kind)


def _receipt(
    job: Job, decision: str, note: str = "", extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    r = {
        "organ": "dweller",
        "job_id": job.id,
        "kind": job.kind,
        "decision": decision,  # dry-run|executed|refused|denied|failed
        "state": job.state,
        "steps": [s.to_dict() for s in job.steps],
        "note": note,
        "ts": _utcnow(),
    }
    if extra:
        r.update(extra)
    return r


def default_steps(kind: str, params: Dict[str, Any]) -> List[JobStep]:
    """The canonical step list for a grind kind."""
    if kind == "repo-sweep":
        return [
            JobStep(id="sweep-1", label="sweep and index modules", kind="repo-sweep")
        ]
    if kind == "crossref":
        return [
            JobStep(id="xref-1", label="exhaustive cross-reference", kind="crossref")
        ]
    if kind == "watch":
        return [JobStep(id="watch-1", label="monitor with backoff", kind="watch")]
    raise runners.RunnerError("unknown grind kind: %r" % kind)


def grind(
    job: Job,
    *,
    home: Optional[Path] = None,
    responder: Optional[Responder] = None,
    dry_run: bool = False,
    watch_sleep: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """Grind a job through the labor law. Always returns (and saves) a receipt."""
    # -- Sandbox check: refuse before asking permission ---------------------
    violation = _sandbox_ok(job)
    if violation:
        receipt = _receipt(job, "refused", "sandbox: " + violation)
        save_receipt(job.id, receipt, home=home)
        save_job(job, home=home, event="refused")
        return receipt

    if dry_run:
        receipt = _receipt(
            job,
            "dry-run",
            "dry-run: %d pending step(s) not executed" % len(job.pending_steps()),
            extra={"sandbox_root": job.sandbox_root},
        )
        save_receipt(job.id, receipt, home=home)
        return receipt

    # -- Permission gate ------------------------------------------------------
    gate = _ask_begin(job, responder)
    if gate["decision"] != "approved":
        receipt = _receipt(
            job, "denied", "permission denied: %s" % gate["note"], extra={"gate": gate}
        )
        save_receipt(job.id, receipt, home=home)
        save_job(job, home=home, event="denied")
        return receipt

    # -- Execute --------------------------------------------------------------
    try:
        job.mark_running()
    except ValueError as exc:
        receipt = _receipt(job, "refused", str(exc))
        save_receipt(job.id, receipt, home=home)
        return receipt
    save_job(job, home=home, event="started")

    for step in job.pending_steps():
        step.state = "running"
        step.attempts += 1
        save_job(job, home=home, event="step-running")
        try:
            step.result = _run_step(step, job, watch_sleep)
            step.state = "done"
            step.error = ""
        except Exception as exc:
            step.state = "failed"
            step.error = "%s: %s" % (type(exc).__name__, exc)
            step.result = {}
        save_job(job, home=home, event="step-" + step.state)
        if step.state == "failed":
            job.mark_failed("step failed: %s (%s)" % (step.id, step.error))
            receipt = _receipt(job, "failed", job.note)
            save_receipt(job.id, receipt, home=home)
            save_job(job, home=home, event="failed")
            return receipt

    job.mark_done("ground %d step(s)" % len(job.steps))
    receipt = _receipt(job, "executed", job.note)
    save_receipt(job.id, receipt, home=home)
    save_job(job, home=home, event="done")
    return receipt


def grind_dry_run(job: Job, home: Optional[Path] = None) -> Dict[str, Any]:
    """Convenience: preview a grind without executing or gating."""
    return grind(job, home=home, dry_run=True)


def grind_job_id(
    job_id: str,
    *,
    home: Optional[Path] = None,
    responder: Optional[Responder] = None,
    dry_run: bool = False,
    watch_sleep: Optional[Callable[[float], None]] = None,
    resume: bool = False,
) -> Dict[str, Any]:
    """Load a job by id from the queue and grind it.

    With ``resume=True``, a failed job is resumed first (continues from
    its first incomplete step).
    """
    job = get_job(job_id, home=home)
    if resume:
        job.resume()
        save_job(job, home=home, event="resumed")
    return grind(
        job, home=home, responder=responder, dry_run=dry_run, watch_sleep=watch_sleep
    )
