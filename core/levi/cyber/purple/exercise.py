"""Exercise runner: the gate, the kill-switch, and the closed loop.

run_exercise() is the framework's only entry point for executing an
emulation. Flow:

  1. Authorization gate (I1-I4). Denial -> exactly one DENIED receipt,
     then AuthorizationDenied propagates. Zero phases execute.
  2. For each technique in scenario order: check the kill-switch BEFORE
     the phase (I6). Synthesize the technique's telemetry into the
     sandbox, evaluate the defensive signal, record a PHASE receipt.
  3. Build one Finding per technique against the playbook manifest
     (I8 — fail closed on unknown ids).
  4. Append exactly one COMPLETED (or KILLED) receipt (I7).

Non-destructive by construction (I5): the runner never spawns
processes, never opens sockets, never writes outside the sandbox.
"Detection" here means confirming the expected defensive signal is
present and well-formed in the synthetic telemetry — the drill is that
the blue team's rule WOULD fire on this pattern.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from core.levi.cyber.purple.authorize import (
    AuthorizationDenied,
    AuthorizationStore,
    check,
)
from core.levi.cyber.purple.findings import (
    Finding,
    build_findings,
    load_playbook_ids,
    load_playbook_index,
)
from core.levi.cyber.purple.receipts import ReceiptLog
from core.levi.cyber.purple.sandbox import Sandbox
from core.levi.cyber.purple.scenarios import EmulatedTechnique, Scenario


class KillSwitch:
    """Cooperative abort. Checked before every phase."""

    def __init__(self) -> None:
        self._killed = False

    def kill(self) -> None:
        self._killed = True

    @property
    def killed(self) -> bool:
        return self._killed


@dataclass
class ExerciseResult:
    exercise_id: str
    scenario_id: str
    target_id: str
    auth_id: str
    phases_executed: int
    killed: bool
    findings: tuple[Finding, ...] = ()
    receipt_kinds: tuple[str, ...] = ()


def _signal_present(technique: EmulatedTechnique, artifact_text: str) -> bool:
    """Defensive-signal check on synthetic telemetry.

    The signal counts as present when every telemetry line the scenario
    specified is present verbatim and parses as JSON carrying
    "simulated": true. A missing or malformed line is a MISS — the blue
    team's rule would not have fired.
    """
    for line in technique.telemetry:
        if line not in artifact_text:
            return False
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return False
        if record.get("simulated") is not True:
            return False
    return True


def run_exercise(
    *,
    store: AuthorizationStore,
    auth_id: str,
    target_id: str,
    scenario: Scenario,
    sandbox_root: str,
    kill_switch: KillSwitch | None = None,
    now: int | None = None,
    receipt_log: ReceiptLog | None = None,
    exercise_id: str | None = None,
) -> ExerciseResult:
    """Run one authorized emulation. See module docstring for the flow."""
    at = now if now is not None else int(time.time())
    switch = kill_switch if kill_switch is not None else KillSwitch()
    log = receipt_log if receipt_log is not None else ReceiptLog()
    ex_id = exercise_id if exercise_id is not None else f"ex-{at}"

    try:
        check(store, auth_id, target_id, scenario.scenario_id, at)
    except AuthorizationDenied as denied:
        log.append(
            "DENIED",
            ex_id,
            {
                "auth_id": auth_id,
                "target_id": target_id,
                "scenario_id": scenario.scenario_id,
                "reason": str(denied),
            },
            at,
        )
        raise

    sandbox = Sandbox(sandbox_root)
    log.append(
        "STARTED",
        ex_id,
        {
            "auth_id": auth_id,
            "target_id": target_id,
            "scenario_id": scenario.scenario_id,
        },
        at,
    )

    detections: list[tuple[str, str, bool, str, str]] = []
    phases = 0
    killed = False
    kinds: list[str] = ["STARTED"]
    playbook_index = load_playbook_index()
    playbook_ids = load_playbook_ids()

    for technique in scenario.techniques:
        if switch.killed:  # I6: checked before EVERY phase
            killed = True
            break
        artifact = sandbox.write(
            f"phase-{phases:02d}-{technique.technique_id.replace('.', '_')}.jsonl",
            "\n".join(technique.telemetry) + "\n",
        )
        detected = _signal_present(technique, artifact.read_text(encoding="utf-8"))
        detections.append(
            (
                technique.technique_id,
                technique.phase,
                detected,
                technique.playbook_id,
                playbook_index[technique.playbook_id],
            )
        )
        phases += 1
        kinds.append("PHASE")
        log.append(
            "PHASE",
            ex_id,
            {
                "technique_id": technique.technique_id,
                "phase": technique.phase,
                "detected": detected,
                "artifact": artifact.name,
            },
            at,
        )

    findings = build_findings(
        exercise_id=ex_id, detections=detections, playbook_ids=playbook_ids
    )

    terminal = "KILLED" if killed else "COMPLETED"
    kinds.append(terminal)
    log.append(
        terminal,
        ex_id,
        {
            "phases_executed": phases,
            "findings": len(findings),
            "detected": sum(1 for f in findings if f.detected),
            "missed": sum(1 for f in findings if not f.detected),
        },
        at,
    )

    return ExerciseResult(
        exercise_id=ex_id,
        scenario_id=scenario.scenario_id,
        target_id=target_id,
        auth_id=auth_id,
        phases_executed=phases,
        killed=killed,
        findings=findings,
        receipt_kinds=tuple(kinds),
    )
