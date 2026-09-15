"""Tests for the LEVI control plane (Enterprise Phase 2, §7/§9/§15/§34).

Hermetic: approvals and the ledger are redirected to a tmp home via the
``home`` constructor argument (or a monkeypatched ``Path.home`` for the
fleet integration, which builds its own engine).
"""

import threading
import time
from pathlib import Path

import pytest

from levi.control.approvals import (
    ApprovalBlocked,
    ApprovalEngine,
    ApprovalNotFound,
)
from levi.control.ledger import LedgerWriter
from levi.control.router import plan as router_plan
from levi.control.routing import (
    COST_UNIT_NOTE,
    classify_complexity,
    plan_route,
)
from levi.fleet.supervisor import Plan, PlanNode
from levi.fleet.swarm import SwarmBudgets, SwarmRunner
from levi.policy.gates import RiskLevel


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture()
def engine(home: Path) -> ApprovalEngine:
    return ApprovalEngine(home=home)


@pytest.fixture()
def ledger(home: Path) -> LedgerWriter:
    return LedgerWriter(home=home)


@pytest.fixture()
def isolated_home(monkeypatch, tmp_path: Path):
    """Redirect Path.home() so fleet-built engines stay hermetic."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")


def _l2_kwargs(**over):
    kw = dict(description="run shell command",
              risk_level=RiskLevel.MODERATE,
              action_key="shell_exec", workflow_key="wf-test")
    kw.update(over)
    return kw


# ---------------------------------------------------------------------------
# approvals: L0/L1 auto-resolve
# ---------------------------------------------------------------------------

def test_l0_l1_auto_approve_and_log(engine: ApprovalEngine):
    r0 = engine.guard(description="read status", risk_level=RiskLevel.INFO)
    r1 = engine.guard(description="list files", risk_level=RiskLevel.LOW)
    assert r0["status"] == "approved"
    assert r1["status"] == "approved"
    assert engine.pending() == []
    decisions = [h.get("decision") or h.get("decision_note", "")
                 for h in engine.history()]
    assert any("auto-approved" in d for d in decisions)


# ---------------------------------------------------------------------------
# approvals: L2+ pending and blocked
# ---------------------------------------------------------------------------

def test_l2_pending_and_blocked_until_decided(engine: ApprovalEngine):
    rec = engine.guard(**_l2_kwargs())
    assert rec["status"] == "awaiting_permission"
    assert rec["id"]
    assert len(engine.pending()) == 1

    with pytest.raises(ApprovalBlocked) as excinfo:
        engine.require(**_l2_kwargs())
    assert excinfo.value.record["id"] == rec["id"]

    with pytest.raises(ApprovalNotFound):
        engine.approve_once("no-such-id")


def test_l3_pending_and_blocked(engine: ApprovalEngine):
    rec = engine.guard(description="drop production database",
                       risk_level=RiskLevel.HIGH,
                       action_key="db_drop", workflow_key="wf-test")
    assert rec["status"] == "awaiting_permission"
    assert rec["risk_name"] == "high"
    with pytest.raises(ApprovalBlocked):
        engine.require(description="drop production database",
                       risk_level=RiskLevel.HIGH,
                       action_key="db_drop", workflow_key="wf-test")


def test_deny_is_visible_and_final_for_that_request(engine: ApprovalEngine):
    rec = engine.guard(**_l2_kwargs())
    denied = engine.deny(rec["id"], note="too risky right now")
    assert denied["status"] == "denied"
    assert engine.get(rec["id"])["status"] == "denied"
    assert engine.pending() == []


# ---------------------------------------------------------------------------
# approvals: approve-once releases exactly one action
# ---------------------------------------------------------------------------

def test_approve_once_releases_exactly_one_action(engine: ApprovalEngine):
    first = engine.guard(**_l2_kwargs())
    # Retry before any decision: same pending record, no queue spam.
    retry = engine.guard(**_l2_kwargs())
    assert retry["id"] == first["id"]
    assert len(engine.pending()) == 1

    engine.approve_once(first["id"])

    claimed = engine.guard(**_l2_kwargs())
    assert claimed["status"] == "approved"
    assert claimed.get("consumed") is True

    # The one-time grant is spent: the next call asks again.
    again = engine.guard(**_l2_kwargs())
    assert again["status"] == "awaiting_permission"
    assert again["id"] != first["id"]


def test_approve_once_claim_survives_process_restart(home: Path):
    kw = _l2_kwargs()
    e1 = ApprovalEngine(home=home)
    rec = e1.guard(**kw)
    ApprovalEngine(home=home).approve_once(rec["id"])  # CLI-like process
    e3 = ApprovalEngine(home=home)  # worker retry in a new process
    assert e3.guard(**kw)["status"] == "approved"
    assert e3.guard(**kw)["status"] == "awaiting_permission"


def test_approve_for_workflow_grants_action(engine: ApprovalEngine):
    rec = engine.guard(**_l2_kwargs())
    engine.approve_for_workflow(rec["id"], workflow_key="wf-test")
    for _ in range(3):
        assert engine.guard(**_l2_kwargs())["status"] == "approved"
    assert engine.pending() == []


def test_guard_timeout_waits_for_cli_decision(home: Path):
    kw = _l2_kwargs()
    seen = {}

    def waiter():
        seen["rec"] = ApprovalEngine(home=home).guard(timeout=10, **kw)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.5)
    pending = ApprovalEngine(home=home).pending()
    assert len(pending) == 1
    ApprovalEngine(home=home).approve_once(pending[0]["id"])
    t.join(timeout=10)
    assert not t.is_alive()
    assert seen["rec"]["status"] == "approved"


# ---------------------------------------------------------------------------
# ledger: round-trip
# ---------------------------------------------------------------------------

def test_ledger_full_round_trip(ledger: LedgerWriter):
    ledger.record_task("t1", objective="summarize the inbox",
                       user_id="u1", tenant_id="t1", plan_version="2")
    sid = ledger.record_step(
        "t1", agent="agent_cli", category="agent_run", task_class="simple",
        model="levi-0.6b", model_version="r1",
        tools_used=["memory_read"],
        decision_summary="read memory, then summarize",
        action="summarize the inbox", expected_result="a summary",
        actual_result="3 items summarized",
        verification={"notes": "structural"},
        outcome="ok", cost_units=2.5, latency_ms=120.0,
    )
    assert sid > 0
    ledger.record_feedback("t1", rating=5, comment="good summary")
    ledger.set_task_status("t1", "ok", cost_units=2.5, latency_ms=120.0)

    task = ledger.get_task("t1")
    assert task is not None
    assert task["objective"] == "summarize the inbox"
    assert task["status"] == "ok"
    assert len(task["steps"]) == 1
    step = task["steps"][0]
    assert step["model"] == "levi-0.6b"
    assert step["task_class"] == "simple"
    assert step["tools_used"] == ["memory_read"]
    assert step["outcome"] == "ok"
    assert task["feedback"][0]["rating"] == 5

    stats = ledger.stats()
    assert stats["tasks"] == 1
    assert stats["steps"] == 1
    assert stats["outcomes"] == {"ok": 1}

    assert ledger.get_task("missing") is None


def test_ledger_model_category_stats_feed_router(ledger: LedgerWriter):
    for i in range(4):
        ledger.record_step(
            f"t{i}", agent="fleet:research", category="research",
            task_class="hard", model="levi-0.6b",
            decision_summary="cheap run", action="research x",
            outcome="ok", cost_units=3.0,
        )
    ledger.record_step("t9", agent="fleet:research", category="research",
                       task_class="hard", model="levi-4b",
                       decision_summary="baseline", action="research x",
                       outcome="ok", cost_units=10.0)
    rows = {(r["model"], r["task_class"]): r
            for r in ledger.model_category_stats()}
    cheap = rows[("levi-0.6b", "hard")]
    assert cheap["runs"] == 4
    assert cheap["successes"] == 4


# ---------------------------------------------------------------------------
# routing: cost-aware model selection
# ---------------------------------------------------------------------------

def test_simple_task_routes_to_cheapest_viable():
    route = plan_route("what is 2 + 2?", only_downloaded=False)
    assert route.complexity == "simple"
    assert route.model == "levi-tiny"
    assert route.quality_ok
    assert route.within_budget
    assert "not dollars" in COST_UNIT_NOTE


def test_tool_needs_exclude_tiny():
    route = plan_route("write a deployment script", needs_tools=True,
                       only_downloaded=False)
    # levi-tiny cannot emit tool calls: it must never win a tool task.
    assert route.model != "levi-tiny"
    assert route.model == "levi-0.6b"


def test_hard_task_routes_to_stronger_model():
    route = plan_route(
        "research and compare distributed consensus architectures",
        only_downloaded=False)
    assert route.complexity == "hard"
    assert route.model == "levi-4b"


def test_budget_overrun_flagged_not_silently_downgraded():
    route = plan_route(
        "research and compare distributed consensus architectures",
        budget_units=0.5, only_downloaded=False)
    assert route.model == "levi-4b"  # quality bar kept
    assert route.within_budget is False


def test_complexity_classifier_reasons():
    level, reasons = classify_complexity("research quantum networks")
    assert level == "hard" and reasons
    level, _ = classify_complexity("hi")
    assert level == "simple"


# ---------------------------------------------------------------------------
# router: task -> (model, category, tools, strategy) + learning
# ---------------------------------------------------------------------------

def test_router_plans_category_tools_strategy(home: Path):
    rp = router_plan("research the best local vector databases", home=home)
    assert rp.category == "research"
    assert "web_search" in rp.tools
    assert rp.strategy == "swarm"
    assert rp.model == "levi-4b"
    assert rp.explanation  # never a bare decision
    assert rp.learned_from_history is False  # no history yet: honest


def test_router_simple_task_is_direct(home: Path):
    rp = router_plan("what time is it?", home=home)
    assert rp.complexity == "simple"
    assert rp.strategy == "direct"


def test_router_local_only_excludes_cloud(home: Path):
    rp = router_plan("research the best local vector databases",
                     privacy="local-only", home=home)
    assert rp.model in ("levi-tiny", "levi-0.6b", "levi-4b")


def test_router_learns_from_ledger_history(home: Path):
    ledger = LedgerWriter(home=home)
    for i in range(4):
        ledger.record_step(
            f"h{i}", agent="fleet:architect", category="architect",
            task_class="hard", model="levi-0.6b",
            decision_summary="0.6b handled it", action="design x",
            outcome="ok", cost_units=3.0,
        )
    rp = router_plan("design a distributed task queue architecture",
                     home=home)
    assert rp.learned_from_history is True
    assert rp.model == "levi-0.6b"  # cheaper than the heuristic levi-4b
    assert any("ledger" in line for line in rp.explanation)


def test_router_ignores_thin_history(home: Path):
    ledger = LedgerWriter(home=home)
    ledger.record_step("h0", agent="x", category="architect",
                       task_class="hard", model="levi-0.6b",
                       decision_summary="one lucky run", action="design x",
                       outcome="ok", cost_units=3.0)
    rp = router_plan("design a distributed task queue architecture",
                     home=home)
    assert rp.learned_from_history is False
    assert rp.model == "levi-4b"


# ---------------------------------------------------------------------------
# fleet integration: L2+ tools pause before execution
# ---------------------------------------------------------------------------

def _approval_plan() -> Plan:
    return Plan(objective="touch an L2 tool", nodes=[
        PlanNode(id="n1", category="coding",
                 task="run a shell command", acceptance="command ran",
                 deps=[]),
    ])


def test_fleet_l2_tool_pauses_before_execution(isolated_home):
    from levi.fleet.swarm import (
        WorkerContext, make_counting_registry,
    )
    import time as _time

    executed = []

    def worker(node, category, ctx: WorkerContext):
        registry = make_counting_registry(
            category.tools, category, ctx, _time.time() + 60)
        # Simulate the agentic loop invoking a MODERATE tool.
        registry.execute("shell_exec", {"command": "echo pwned"})
        executed.append(True)
        return {"ok": True, "summary": "done", "artifacts": []}

    report = SwarmRunner(
        budgets=SwarmBudgets(max_agents=2), worker_fn=worker,
    ).run(_approval_plan())

    assert executed == []  # the tool never ran
    assert report["nodes"]["n1"]["status"] == "awaiting_approval"
    approval_id = report["nodes"]["n1"]["approval_id"]
    assert approval_id and approval_id != "?"
    assert any(e["reason"] == "awaiting_approval"
               for e in report["escalations"])
    # Exactly one pending approval — no queue spam.
    engine = ApprovalEngine()  # Path.home is monkeypatched
    assert len(engine.pending()) == 1

    # Human approves in the CLI; the claim path releases one action.
    engine.approve_once(approval_id)
    assert engine.guard(
        description="fleet tool call", risk_level=RiskLevel.MODERATE,
        action_key="shell_exec",
        workflow_key=report["run_id"])["status"] == "approved"


def test_fleet_l0_tools_do_not_require_approval(isolated_home):
    from levi.fleet.swarm import WorkerContext, make_counting_registry
    import time as _time

    def worker(node, category, ctx: WorkerContext):
        registry = make_counting_registry(
            category.tools, category, ctx, _time.time() + 60)
        res = registry.execute("file_read", {"path": "nonexistent"})
        return {"ok": True, "summary": f"read ok={res.ok}", "artifacts": []}

    report = SwarmRunner(
        budgets=SwarmBudgets(max_agents=2), worker_fn=worker,
    ).run(_approval_plan())
    assert report["nodes"]["n1"]["status"] == "ok"
    assert ApprovalEngine().pending() == []


def test_fleet_run_recorded_in_decision_ledger(isolated_home, tmp_path: Path):
    def worker(node, category, ctx):
        return {"ok": True, "summary": "stub did the thing", "artifacts": []}

    report = SwarmRunner(
        budgets=SwarmBudgets(max_agents=2), worker_fn=worker,
    ).run(_approval_plan())
    run_id = report["run_id"]

    ledger = LedgerWriter()  # Path.home is monkeypatched
    task = ledger.get_task(run_id)
    assert task is not None
    assert task["objective"] == "touch an L2 tool"
    assert len(task["steps"]) == 1
    step = task["steps"][0]
    assert step["category"] == "coding"
    assert step["outcome"] == "ok"
    assert step["task_class"] in ("simple", "medium", "hard")
    assert "decision_summary" in step and step["decision_summary"]
    # No hidden chain-of-thought column exists.
    assert "chain_of_thought" not in step
