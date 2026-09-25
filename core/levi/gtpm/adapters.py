"""Thin adapters over Phase 1's synthesis interfaces.

Working module name — **naming is Chauncey's**.

The beginning team owns ``core/levi/synthesis/*``; this module never edits
their files. It imports them lazily and degrades honestly when an interface
is unavailable — an adapter that guesses is a liability.

GTPM (Chauncey): "Basically analyzing but pure deterministic. I call it
goal targeted predator mentality." These adapters let the predator use the
deliberative mind as a *consulted voice*, never as the decider: the
scan-mind's deterministic verdict stands beside the deliberator's analysis,
and the receipt records both.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-gtpm/adapters"


def gtpm_dir() -> Path:
    """Receipt/state home. Override with LEVI_GTPM_DIR (hermetic tests use this)."""
    raw = os.environ.get("LEVI_GTPM_DIR")
    path = Path(raw).expanduser() if raw else Path.home() / ".levi" / "gtpm"
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_receipt(receipt: Dict[str, Any]) -> Path:
    """Append one JSON receipt to the flagship receipt log (JSONL)."""
    log = gtpm_dir() / "receipts.jsonl"
    entry = dict(receipt)
    entry.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return log


def policy_gate(
    auto_approve_up_to: Any = None,
) -> Callable[[Dict[str, Any]], bool]:
    """Build the scan-mind FLUSH gate over the shared PolicyEngine.

    Chauncey's standing approval: levels 0–2 (INFO/LOW/MODERATE) auto-approved;
    3–4 (HIGH/CRITICAL) need his explicit word. A non-interactive scan cycle
    cannot obtain that word, so anything not auto-approved is a DENIED fault —
    fail-closed, never a silent skip.
    """
    from levi.policy.gates import ActionStatus, PolicyEngine, RiskLevel

    ceiling = (
        auto_approve_up_to if auto_approve_up_to is not None else RiskLevel.MODERATE
    )
    engine = PolicyEngine(auto_approve_up_to=ceiling)

    def gate(intent: Dict[str, Any]) -> bool:
        name = str(intent.get("intent", "act"))
        try:
            risk = RiskLevel(int(intent.get("risk", 1)))
        except (TypeError, ValueError):
            risk = RiskLevel.MODERATE
        proposal = engine.propose(
            description=f"scan-mind staged intent: {name}",
            risk_level=risk,
            reason="flagship scan-cycle FLUSH",
            affected_systems=["levi-gtpm"],
            reversible=True,
        )
        decided = engine.request_permission(proposal.id)
        if decided.status == ActionStatus.APPROVED:
            return True
        engine.deny(proposal.id, note="non-interactive cycle: fail-closed DENIED")
        return False

    gate.engine = engine  # type: ignore[attr-defined]  # introspection hook
    return gate


def deliberative_voice(task: str, brain_policy: str = "auto") -> Dict[str, Any]:
    """Consult Phase 1's deliberative mind as a voice, not the decider.

    Returns the synthesis report on success; on any failure returns an
    honest ``{"mode": "unavailable", "error": ...}`` — never a fabricated
    analysis.
    """
    try:
        from levi.synthesis import mind

        report = mind.ask(task, brain_policy=brain_policy)
        return {"mode": "deliberative", "report": report}
    except Exception as exc:  # fail-open consultation would be dishonest
        return {"mode": "unavailable", "error": f"{type(exc).__name__}: {exc}"}


def governance_frame(
    goal: str, consent: bool, limits: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Frozen per-pass frame for the agent loop's reason step (contract B5).

    The beginning team's ``run_goal`` would freeze
    ``(goal, consent, standing limits, safety signals)`` into the image the
    reason step reads. This is the reference shape; the tool loop inside the
    act phase keeps observing its own results (agentic flexibility stays at
    the execution layer).
    """
    return {
        "goal": goal,
        "consent": bool(consent),
        "limits": dict(limits or {}),
        "offline_enforced": True,
    }


def build_supervisory_program() -> Dict[str, Any]:
    """Scan program for delegated supervisory sub-runs (contract B6).

    Rung 0 is the offline interlock (safety supremacy, same discipline as
    the flagship): if the frozen image ever shows ``offline_enforced``
    false, the cycle trips INTERLOCK and commits nothing. The watch rungs
    stage supervisory intents; the goal text rides in the frozen image and
    is resolved into coil args (``"$goal"``), never guessed.
    """
    from levi.gtpm import scanmind

    return scanmind.make_program(
        [
            {
                "name": "interlock_offline",
                "safety": True,
                "branches": [[{"signal": "offline_enforced", "pred": "is_false"}]],
                "coil": {"intent": "halt_all", "args": {}, "risk": 4},
                "mode": "normal",
            },
            {
                "name": "goal_watch",
                "safety": False,
                "branches": [[{"signal": "goal_present", "pred": "is_true"}]],
                "coil": {
                    "intent": "supervise_goal",
                    "args": {"goal": "$goal"},
                    "risk": 1,
                },
                "mode": "normal",
            },
            {
                "name": "goal_seal",
                "safety": False,
                "branches": [[{"signal": "goal_present", "pred": "is_true"}]],
                "coil": {
                    "intent": "goal_latched",
                    "args": {"goal": "$goal"},
                    "risk": 0,
                },
                "mode": "latch",
            },
            {
                "name": "goal_edge",
                "safety": False,
                "branches": [[{"signal": "goal_present", "pred": "is_true"}]],
                "coil": {
                    "intent": "announce_goal",
                    "args": {"goal": "$goal"},
                    "risk": 0,
                },
                "mode": "one_shot",
            },
        ]
    )


def _scan_cycles_per_goal(max_steps: Any) -> int:
    """Bound the scan cycles for one delegated goal to [1, 6]."""
    try:
        n = int(max_steps)
    except (TypeError, ValueError):
        n = 6
    return max(1, min(n, 6))


def _recording_executor(
    committed: List[Dict[str, Any]],
) -> Callable[[Dict[str, Any]], bool]:
    """Executor that records committed supervisory intents (no side effects)."""

    def executor(intent: Dict[str, Any]) -> bool:
        committed.append(
            {"intent": intent.get("intent"), "args": intent.get("args", {})}
        )
        return True

    return executor


def delegate_scan(
    goals: List[str], config: Any = None, max_steps: int = 6
) -> Dict[str, Any]:
    """Execute supervisory goals as real scan-mind sub-runs (contract B6).

    This previously probed ``synthesis.delegate_goals(mind="scan")`` and
    routed back into it — circular, because synthesis calls this adapter
    for ``mind="scan"`` (the B6 contract conflict the beginning team
    flagged). It now executes directly: per goal, a bounded run of scan
    cycles — FREEZE (goal + offline frame) → EXECUTE (supervisory rung
    program) → FLUSH (staged intents through the policy gate) →
    HOUSEKEEPING (receipt). No call back into ``levi.synthesis`` is made
    on this path.

    The signature and the merged-receipt shape are the contract surface
    the beginning team's ``delegate_goals(mind="scan")`` codes against:
    it returns this dict directly. ``config`` is read defensively
    (``scan_budget_ms``, ``offline_enforced`` — contract B9); ``max_steps``
    bounds the scan cycles per goal.
    """
    from levi.gtpm import scanmind

    goal_list = list(goals or [])
    for goal in goal_list:
        if not isinstance(goal, str):
            raise ValueError(
                f"delegate_scan: each goal must be a string, got {type(goal).__name__}"
            )

    try:
        budget_ms = float(getattr(config, "scan_budget_ms", 100))
    except (TypeError, ValueError):
        budget_ms = 100.0
    offline_enforced = bool(getattr(config, "offline_enforced", True))

    program = build_supervisory_program()
    gate = policy_gate()
    n_cycles = _scan_cycles_per_goal(max_steps)

    started = datetime.now(timezone.utc).isoformat()
    sub_receipts: List[Dict[str, Any]] = []
    for gi, goal_text in enumerate(goal_list):
        committed: List[Dict[str, Any]] = []
        executor = _recording_executor(committed)
        state: Dict[str, Any] = {}
        fault_list: List[Dict[str, Any]] = []
        cycle_commits: List[List[Dict[str, Any]]] = []
        image_hashes: List[Any] = []
        watchdog_ok = True
        for ci in range(n_cycles):
            world = {
                "goal": goal_text,
                "goal_present": bool(goal_text.strip()),
                "offline_enforced": offline_enforced,
                "cycle": ci,
            }
            receipt, state = scanmind.run_scan_cycle(
                world,
                program,
                gate=gate,
                executor=executor,
                budget_ms=budget_ms,
                state=state,
                scan_id=f"delegate-scan/g{gi}/c{ci}",
            )
            receipt["goal"] = goal_text
            append_receipt(receipt)
            fault_list.extend(receipt.get("faults", []))
            cycle_commits.append(list(receipt.get("commits", [])))
            image_hashes.append(receipt.get("image_hash"))
            watchdog_ok = watchdog_ok and bool(receipt.get("watchdog_ok"))
        # Join the scan-mind's commit verdicts with the executor's recorded
        # args so the merged receipt is self-describing (which goal each
        # committed intent supervised).
        args_by_intent: Dict[str, Any] = {}
        for rec in committed:
            args_by_intent.setdefault(rec["intent"], rec["args"])
        commit_list = [
            {
                "intent": c.get("intent"),
                "ok": c.get("ok"),
                "args": args_by_intent.get(c.get("intent"), {}),
            }
            for commits in cycle_commits
            for c in commits
        ]
        sub_receipts.append(
            {
                "goal": goal_text,
                "cycles": n_cycles,
                "commits": commit_list,
                "faults": fault_list,
                "watchdog_ok": watchdog_ok,
                "image_hashes": image_hashes,
                "ok": not fault_list and watchdog_ok,
            }
        )

    return {
        "coordinator": "gtpm.adapters.delegate_scan",
        "mind": "scan",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "workers": len(sub_receipts),
        "workers_ok": sum(1 for r in sub_receipts if r["ok"]),
        "sub_receipts": sub_receipts,
    }
