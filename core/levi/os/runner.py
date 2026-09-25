"""The daemon-style runner — Alpha builds the workflow, Omega executes it.

Stage shape follows the Automation Engine's HISTORIC CANON (Chauncey's
ruling 2026-09-22, "Historic cannon")::

    Workflow Processor -> Logic Module -> Routine Generator -> Execution Hub
                                              (Real-Time Adaptation feeds the hub)

- Workflow Processor: :func:`levi.os.outcome.state_outcome` — outcome text
  becomes an ordered, skill-backed step workflow.
- Logic Module: per-step resolution — skill lookup, rank/mastery shaping,
  device routing, and the Real-Time Adaptation decision (the step's honest
  status is decided against live reality: backend flag, device status).
- Routine Generator: the resolved steps assembled into an ordered routine.
- Execution Hub: the run loop. Every step gets a hash-chained receipt,
  whatever its outcome — including honest non-execution. Outputs fan out
  as digital actions (delivered playbooks), staged native work (ready),
  deferred physical/device tasks, and blocked wiring gaps; receipts close
  the feedback loop.

Step outcomes (v0.1, all honest):
- ``blocked`` — ``needs-wiring`` skill: no connector exists, so nothing
  executes. The receipt says so instead of faking it.
- ``deferred`` — the routed device is stubbed/unpaired/unknown, or no
  device covers the step's capabilities. Named, not retried silently.
- ``delivered`` — ``playbook-only`` skill on a real device: the procedure
  (skill + rank-rung guidance) is the output.
- ``ready`` — ``platform-native`` skill: v0.1 ships no native handlers,
  so the step is staged, not executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.legion.skill_pool import get_pool
from levi.os.devices import Device, enumerate_devices
from levi.os.outcome import Plan, PlanStep
from levi.os.receipts import ReceiptWriter, verify

__all__ = ["RunReport", "StepResult", "execute", "default_home"]


#: Where the OS layer keeps state when the caller doesn't say.
def default_home() -> Path:
    return Path.home()


@dataclass
class StepResult:
    step_id: str
    skill_id: str
    rank: str
    device_id: Optional[str]
    status: str  # blocked | deferred | delivered | ready
    note: str
    receipt_seq: int


@dataclass
class RunReport:
    plan_id: str
    session_id: str
    results: List[StepResult] = field(default_factory=list)
    receipts_path: str = ""
    chain_ok: bool = False

    def summary(self) -> str:
        lines = [f"plan {self.plan_id}: {len(self.results)} step(s)"]
        for r in self.results:
            lines.append(
                f"  [{r.step_id}] {r.skill_id}@{r.rank} -> {r.status} ({r.note})"
            )
        lines.append(f"receipts: {self.receipts_path} chain_ok={self.chain_ok}")
        return "\n".join(lines)


def _playbook_text(skill: Dict[str, Any], rank: str, rank_description: str) -> str:
    inputs = ", ".join(skill.get("inputs") or []) or "none declared"
    outputs = ", ".join(skill.get("outputs") or []) or "none declared"
    return (
        f"{skill['name']} (rank {rank}): {rank_description} "
        f"Procedure: {skill['description']} "
        f"Inputs: {inputs}. Outputs: {outputs}."
    )


def _workflow_processor(plan: Plan) -> List[PlanStep]:
    """Workflow Processor (canon): validate the workflow is runnable."""
    if not plan.steps:
        raise ValueError("cannot execute an empty plan")
    return list(plan.steps)


def _logic_module(
    step: PlanStep,
    pool: Any,
    known_devices: Dict[str, Device],
) -> Dict[str, Any]:
    """Logic Module + Real-Time Adaptation (canon): resolve one step
    against live reality — skill presence, backend flag, device status —
    and decide its honest status and note."""
    skill = pool.get(step.skill_id)
    if skill is None:  # pool changed under the plan — fail loudly
        raise ValueError(f"skill {step.skill_id!r} vanished from the pool")
    device = known_devices.get(step.device_id or "")

    if step.backend == "needs-wiring":
        status = "blocked"
        note = f"{step.skill_id} is needs-wiring: no connector exists, nothing executed"
    elif device is None:
        status = "deferred"
        note = f"no device covers capabilities {','.join(step.required_capabilities)}"
    elif device.status != "real":
        status = "deferred"
        note = f"device {device.id} is {device.status}: {device.notes}"
    elif step.backend == "playbook-only":
        status = "delivered"
        note = _playbook_text(skill, step.rank, step.rank_description)
    else:  # platform-native
        status = "ready"
        note = "platform-native: v0.1 ships no native handlers — staged"
    return {"skill": skill, "device": device, "status": status, "note": note}


def _routine_generator(
    steps: List[PlanStep],
    pool: Any,
    known_devices: Dict[str, Device],
) -> List[Dict[str, Any]]:
    """Routine Generator (canon): ordered step intents, fully resolved."""
    routine = []
    for step in steps:
        decision = _logic_module(step, pool, known_devices)
        routine.append({"step": step, **decision})
    return routine


def _execution_hub(
    plan: Plan,
    routine: List[Dict[str, Any]],
    writer: ReceiptWriter,
) -> List[StepResult]:
    """Execution Hub (canon): run the routine; receipt every step."""
    results: List[StepResult] = []
    for intent in routine:
        step = intent["step"]
        receipt = writer.append(
            "step",
            {
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "clause": step.clause,
                "skill_id": step.skill_id,
                "rank": step.rank,
                "device_id": step.device_id,
                "backend": step.backend,
                "status": intent["status"],
                "note": intent["note"],
            },
        )
        results.append(
            StepResult(
                step_id=step.step_id,
                skill_id=step.skill_id,
                rank=step.rank,
                device_id=step.device_id,
                status=intent["status"],
                note=intent["note"],
                receipt_seq=receipt.seq,
            )
        )
    return results


def execute(
    plan: Plan,
    home: Optional[Path] = None,
    session_id: Optional[str] = None,
    devices: Optional[List[Device]] = None,
) -> RunReport:
    """Run a plan through the canon stages; verify the receipt chain."""
    home = Path(home) if home is not None else default_home()
    session = session_id or plan.plan_id
    pool = get_pool()
    known_devices = {d.id: d for d in enumerate_devices(devices)}
    writer = ReceiptWriter(home, session)

    steps = _workflow_processor(plan)
    routine = _routine_generator(steps, pool, known_devices)
    results = _execution_hub(plan, routine, writer)

    chain_ok, _ = verify(home, session)
    return RunReport(
        plan_id=plan.plan_id,
        session_id=session,
        results=results,
        receipts_path=str(writer.path),
        chain_ok=chain_ok,
    )
