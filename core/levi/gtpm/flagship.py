"""The flagship demonstration: scan-mind + blackboard + rule-reflex (+ dictionary)
running one task.

Working module name — **naming is Chauncey's**.

GTPM (Chauncey): "Basically analyzing but pure deterministic. I call it
goal targeted predator mentality." This is the predator's first hunt, run
as a demonstration: one task, one frozen world, every decision receipted.

The task: **house-watch** — keep the subsystem honest. Observe signals,
plan a response to drift, verify the plan against a critic, confirm it,
let reflexes stage the acts, and let the scan-mind commit them through
the permission gate. Perceive → reason → act → verify → receipt.

Determinism: no randomness, no wall-clock in any decision. Timestamps
appear in receipts (audit trail), never in logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.gtpm import board, reflex, scanmind, words
from levi.gtpm.adapters import append_receipt, deliberative_voice, policy_gate

ORIGIN = "levi-gtpm/flagship"

TASK = "house-watch: keep the subsystem honest"


def build_dictionary() -> Dict[str, Any]:
    """A tiny working vocabulary; the demo computes with it, not around it."""
    d = words.new_dictionary()
    words.define(d, "double", ["dup", "add"], ("1", "1"))
    return d


def build_board() -> Dict[str, Any]:
    """Blackboard with observer / planner / critic knowledge sources."""
    b = board.new_board(["raw", "parsed", "planned", "verified", "receipted"])

    def observer_trigger(bd: Dict[str, Any]) -> bool:
        return not bd["cells"]["raw"]

    def observer_contribute(bd: Dict[str, Any]):
        return (
            "raw",
            {"drift": True, "computed": 42, "health_ok": True},
            0.8,
            ["scan-image/cycle-1"],
        )

    def planner_trigger(bd: Dict[str, Any]) -> bool:
        drift_seen = any(
            h["content"].get("drift") for h in bd["cells"]["raw"]
        )
        return drift_seen and not bd["cells"]["planned"]

    def planner_contribute(bd: Dict[str, Any]):
        return (
            "planned",
            {"action": "recheck", "target": "drift"},
            0.7,
            ["planner/observer"],
        )

    def critic_trigger(bd: Dict[str, Any]) -> bool:
        return any(
            h["confidence"] < 0.9 and h["posted_by"] != "critic"
            for h in bd["cells"]["planned"]
        )

    def critic_contribute(bd: Dict[str, Any]):
        return (
            "planned",
            {"action": "escalate", "target": "drift"},
            0.6,
            ["critic"],
        )

    board.register_ks(b, "observer", ["raw"], observer_trigger, observer_contribute, priority=3.0)
    board.register_ks(b, "planner", ["planned"], planner_trigger, planner_contribute, priority=2.0)
    board.register_ks(b, "critic", ["planned"], critic_trigger, critic_contribute, priority=1.0)
    return b


def build_program() -> Dict[str, Any]:
    """Scan program: rung-0 interlock armed, drift rungs live."""
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
                "name": "drift_watch",
                "safety": False,
                "branches": [[{"signal": "drift", "pred": "is_true"}]],
                "coil": {"intent": "plan_response", "args": {"signal": "drift"}, "risk": 1},
                "mode": "normal",
            },
            {
                "name": "drift_seal",
                "safety": False,
                "branches": [[{"signal": "drift", "pred": "is_true"}]],
                "coil": {"intent": "drift_latched", "args": {}, "risk": 0},
                "mode": "latch",
            },
            {
                "name": "drift_edge",
                "safety": False,
                "branches": [[{"signal": "drift", "pred": "is_true"}]],
                "coil": {"intent": "announce_drift", "args": {}, "risk": 0},
                "mode": "one_shot",
            },
        ]
    )


def build_rules() -> List[Dict[str, Any]]:
    """Reflex rules: confirmed plans stage acts; low-confidence only proposes."""
    lhs = [
        {
            "fact_type": "hypothesis",
            "constraints": [
                {"signal": "status", "pred": "eq", "value": "confirmed"},
                {"signal": "action", "pred": "present"},
            ],
        }
    ]
    return [
        {
            "id": "rx-plan",
            "name": "confirmed plan drives act",
            "lhs": lhs,
            "rhs": {"assert": [], "retract": [], "act": "recheck"},
            "provenance": ["flagship/demo"],
            "confidence": 0.8,
            "priority": 10,
            "born_at": "demo",
            "corroboration": 2,
        },
        {
            "id": "rx-tune",
            "name": "low confidence only proposes",
            "lhs": lhs,
            "rhs": {"assert": [], "retract": [], "act": "tune"},
            "provenance": ["flagship/demo"],
            "confidence": 0.3,
            "priority": 5,
            "born_at": "demo",
            "corroboration": 1,
        },
    ]


def tick_as_scan(
    due_entries: List[str],
    program: Dict[str, Any],
    world: Dict[str, Any],
    gate=None,
    executor=None,
    budget_ms: float = 100.0,
) -> Dict[str, Any]:
    """Reference implementation for contract B4 (beginning team owns tick_schedules).

    One scan per tick: FREEZE (due schedules + world) → EXECUTE (policy rungs)
    → FLUSH (staged commits through gate/executor) → HOUSEKEEPING (receipt).
    The beginning team wires ``run_goal`` as the executor for due entries;
    this reference records staged intents so the discipline is auditable
    before it is wired.
    """
    gate = gate or policy_gate()
    staged: List[Dict[str, Any]] = []

    def _executor(intent: Dict[str, Any]) -> bool:
        staged.append({"intent": intent.get("intent"), "args": intent.get("args", {})})
        return True

    image_world = dict(world)
    image_world["due"] = list(due_entries)
    image, _ = scanmind.freeze_image(image_world)
    receipt, _state = scanmind.run_scan_cycle(
        image_world,
        program,
        gate=gate,
        executor=executor or _executor,
        budget_ms=budget_ms,
    )
    receipt["due_entries"] = list(due_entries)
    return receipt


def run_demo(consult_deliberative: bool = False) -> Dict[str, Any]:
    """Run the flagship task end to end. Returns a JSON-serializable summary."""
    receipts_written = 0

    def log(receipt: Dict[str, Any]) -> None:
        nonlocal receipts_written
        append_receipt(receipt)
        receipts_written += 1

    # 1. Dictionary computes.
    d = build_dictionary()
    computed = words.replay(d, "double", [21])  # [42], deterministic

    # 2. Blackboard deliberates: observe → plan → critic → arbitrate → confirm.
    b = build_board()
    journal: List[Dict[str, Any]] = []
    board.on_transition(b, journal.append)
    board_receipts = [board.step(b, cycle=c)[1] for c in range(3)]
    for r in board_receipts:
        log(r)
    # Proposed -> active (corroboration) before arbitration can judge.
    for hyp in list(b["cells"]["planned"]):
        board.corroborate(b, hyp["id"], "flagship")
    arb = board.arbitrate(b, "planned", key_fn=lambda h: str(h["content"].get("target")))
    log({"kind": "arbitration", **{k: (v if k != "winner" else v["id"]) for k, v in arb.items()}})
    winner_id = arb["winner"]["id"] if isinstance(arb["winner"], dict) else arb["winner"]
    # arbitrate already confirmed the winner; record the outcome for weighting.
    board.record_outcome(b, "planner", True)
    winner = next(h for h in b["cells"]["planned"] if h["id"] == winner_id)

    # 3. Rule-reflex: confirmed hypotheses become working-memory facts.
    net = reflex.compile_rules(build_rules())
    reflex.assert_fact(
        net,
        {
            "type": "hypothesis",
            "fields": {"status": "confirmed", **winner["content"]},
            "source": "board/confirmed",
            "t": "demo-c1",
        },
    )
    firing_receipts = reflex.run_cycle(net)
    for r_ in firing_receipts:
        log(r_)
    staged_acts = [r_["staged_act"] for r_ in firing_receipts if "staged_act" in r_]
    proposals = [r_["proposal"] for r_ in firing_receipts if "proposal" in r_]

    # 4. Scan-mind: two cycles over a frozen world; drift clears in cycle 2.
    program = build_program()
    gate = policy_gate()
    committed: List[Dict[str, Any]] = []

    def executor(intent: Dict[str, Any]) -> bool:
        committed.append({"intent": intent.get("intent"), "args": intent.get("args", {})})
        return True

    worlds = [
        {"offline_enforced": True, "drift": True, "health_ok": True, "computed": computed[0]},
        {"offline_enforced": True, "drift": False, "health_ok": True, "computed": computed[0]},
    ]
    scan_receipts = []
    state = {"latch_bits": {}, "prev_image": None, "scan_count": 0}
    for i, world in enumerate(worlds):
        receipt, state = scanmind.run_scan_cycle(
            world, program, gate=gate, executor=executor,
            budget_ms=100.0, state=state, scan_id=f"demo-{i+1}",
        )
        log(receipt)
        scan_receipts.append(receipt)

    # 5. Verify: commit summary posted back to the board (the receipt level).
    board.post(
        b,
        "receipted",
        {"commits": [c["intent"] for c in committed], "scans": len(scan_receipts)},
        1.0,
        ["scan-cycle/demo"],
        "flagship",
    )

    # 6. Optional: consult the deliberative voice (a voice, never the decider).
    deliberation: Dict[str, Any] = {"mode": "not-consulted"}
    if consult_deliberative:
        deliberation = deliberative_voice(
            "Assess this house-watch cycle: " + str([c["intent"] for c in committed])
        )

    summary = {
        "task": TASK,
        "dictionary_computed": computed,
        "board_winner": {"id": winner["id"], "content": winner["content"]},
        "board_journal_events": len(journal),
        "staged_acts": staged_acts,
        "proposals": proposals,
        "scan_commits": [c["intent"] for c in committed],
        "scan_faults": [f for r_ in scan_receipts for f in r_.get("faults", [])],
        "watchdog_ok": all(r_.get("watchdog_ok") for r_ in scan_receipts),
        "deliberation": deliberation.get("mode"),
        "receipts_written": receipts_written,
    }
    log({"kind": "demo", "summary": summary})
    summary["receipts_written"] = receipts_written
    return summary
