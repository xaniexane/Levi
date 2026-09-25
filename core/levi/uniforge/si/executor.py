"""UniForge native executor — the forge law, run for real.

Every forge run walks the law:

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

- Dry-run is the default: preview is shown, permission is recorded as
  "not requested (dry-run)", nothing executes, and the receipt says so.
- A plan whose tools are missing refuses BEFORE the permission gate,
  with a receipt naming the missing tools.
- Live runs ask explicit permission through a HITL-style approval gate
  (``levi.automation.hitl`` public classes only — GateRequest/GateKind).
  A denied gate ends the run; the receipt records it.
- Every step runs for real via subprocess (captured output, timeout).
  Consequential steps pass their own gate inside a live run.
- Verify re-checks each step's declared artifacts; findings are
  recorded whether they pass or not.

A receipt is produced for EVERY run, including refusals, denials, and
failures. stdlib only; never imports the AI counterpart bridge.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from levi.automation.hitl import GateKind, GateRequest

from ..plan import BuildPlan

#: Hard timeout per step so a hung build can never hang the forge.
_STEP_TIMEOUT_S = 300


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


#: A responder answers a GateRequest without a real human present.
Responder = Callable[[GateRequest], Dict[str, Any]]


def _resolve(request: GateRequest, responder: Optional[Responder]) -> Dict[str, Any]:
    """Run the permission gate; fail closed when nobody can answer."""
    if responder is None:
        return {
            "decision": "denied",
            "note": "no responder: fail-closed (live run refused)",
        }
    try:
        out = responder(request)
    except Exception as exc:  # a broken responder denies, never approves
        return {"decision": "denied", "note": "responder error: %s" % exc}
    decision = str(out.get("decision", "denied"))
    if decision not in ("approved", "edited", "acknowledged", "noted"):
        decision = "denied"
    return {"decision": decision, "note": str(out.get("note", ""))}


def _ask(
    prompt: str,
    context: Dict[str, Any],
    responder: Optional[Responder],
    minion_id: str = "uniforge",
) -> Dict[str, Any]:
    req = GateRequest(
        minion_id=minion_id, kind=GateKind.APPROVAL, prompt=prompt, context=context
    )
    result = _resolve(req, responder)
    return {
        "prompt": prompt,
        "kind": GateKind.APPROVAL.value,
        "decision": result["decision"],
        "note": result["note"],
        "resolved_ts": _utcnow(),
    }


def _run_step(step_argv: List[str], workdir: str) -> Dict[str, Any]:
    """Run one step's command for real; capture everything."""
    try:
        proc = subprocess.run(
            step_argv,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=_STEP_TIMEOUT_S,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "returncode": 127,
            "stdout": "",
            "stderr": "tool not found on PATH: %s" % step_argv[0],
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "step timed out after %ds" % _STEP_TIMEOUT_S,
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _verify_step(step, workdir: str) -> Dict[str, Any]:
    """Verify a step's declared artifacts exist (hermetic, local)."""
    findings = []
    for art in step.artifacts:
        path = os.path.join(workdir, art)
        findings.append({"artifact": art, "exists": os.path.exists(path)})
    return {
        "verified": all(f["exists"] for f in findings),
        "findings": findings,
    }


def _receipt(
    plan: BuildPlan,
    decision: str,
    stages: Dict[str, Any],
    steps_log: List[Dict[str, Any]],
    verified: Optional[bool],
    note: str = "",
) -> Dict[str, Any]:
    return {
        "organ": "uniforge",
        "plan": plan.name,
        "targets": list(plan.targets),
        "decision": decision,  # dry-run | executed | refused | denied | failed
        "note": note,
        "stages": stages,
        "steps": steps_log,
        "verified": verified,
        "ts": _utcnow(),
    }


def forge(
    plan: BuildPlan,
    *,
    live: bool = False,
    responder: Optional[Responder] = None,
    workdir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the forge law over a plan. Returns the receipt (always)."""
    stages: Dict[str, Any] = {"plan": {"name": plan.name, "ts": _utcnow()}}
    steps_log: List[Dict[str, Any]] = []

    # -- Preview ------------------------------------------------------------
    preview_text = plan.preview()
    stages["preview"] = {"text": preview_text, "ts": _utcnow()}

    # -- Tool honesty check: refuse before asking permission ----------------
    tools = plan.tool_status()
    if tools["missing"]:
        return _receipt(
            plan,
            "refused",
            stages,
            steps_log,
            None,
            note="missing tools: %s (refused: never fake a build)"
            % ", ".join(tools["missing"]),
        )
    stages["tools"] = {"present": tools["present"], "ts": _utcnow()}

    # -- Permission ----------------------------------------------------------
    if not live:
        stages["permission"] = {
            "decision": "not-requested",
            "note": "dry-run default: nothing executes without --live",
            "ts": _utcnow(),
        }
        return _receipt(
            plan,
            "dry-run",
            stages,
            steps_log,
            None,
            note="dry-run: preview only, %d step(s) not executed" % len(plan.steps),
        )

    permission = _ask(
        "Execute forge plan %r (%d steps across %s)?"
        % (plan.name, len(plan.steps), ", ".join(plan.targets)),
        {
            "plan": plan.name,
            "targets": plan.targets,
            "steps": [s.to_dict() for s in plan.steps],
        },
        responder,
    )
    stages["permission"] = permission
    if permission["decision"] != "approved":
        return _receipt(
            plan,
            "denied",
            stages,
            steps_log,
            None,
            note="permission denied: %s" % permission["note"],
        )

    # -- Execute -------------------------------------------------------------
    root = os.path.abspath(workdir or ".")
    failed: Optional[Dict[str, Any]] = None
    for step in plan.ordered_steps():
        entry: Dict[str, Any] = {
            "id": step.id,
            "label": step.label,
            "target": step.target,
        }
        step_dir = os.path.abspath(os.path.join(root, step.workdir))
        if step.consequential:
            gate = _ask(
                "Run consequential step %r (%s)?" % (step.label, " ".join(step.argv)),
                {"step": step.to_dict()},
                responder,
            )
            entry["gate"] = gate
            if gate["decision"] != "approved":
                entry["status"] = "denied"
                entry["note"] = gate["note"]
                steps_log.append(entry)
                failed = entry
                break
        result = _run_step(step.argv, step_dir)
        entry["result"] = result
        entry["status"] = "done" if result["ok"] else "failed"
        steps_log.append(entry)
        if not result["ok"]:
            failed = entry
            break
    stages["execute"] = {"ran": len(steps_log), "ts": _utcnow()}

    if failed is not None:
        return _receipt(
            plan,
            "failed",
            stages,
            steps_log,
            None,
            note="step failed: %s" % failed["id"],
        )

    # -- Verify --------------------------------------------------------------
    verify_log = []
    all_ok = True
    for step in plan.ordered_steps():
        step_dir = os.path.abspath(os.path.join(root, step.workdir))
        v = _verify_step(step, step_dir)
        verify_log.append({"id": step.id, **v})
        all_ok = all_ok and v["verified"]
    stages["verify"] = {"steps": verify_log, "ts": _utcnow()}

    return _receipt(
        plan,
        "executed",
        stages,
        steps_log,
        all_ok,
        note="executed %d step(s); verified=%s" % (len(steps_log), all_ok),
    )


def forge_dry_run(plan: BuildPlan) -> Dict[str, Any]:
    """Convenience: the default path — preview only, receipt included."""
    return forge(plan, live=False)
