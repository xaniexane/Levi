"""Tests for the LEVI fleet (Enterprise Phase 1, §2–4). Hermetic."""

import time

import pytest

from levi.fleet import (
    list_categories,
    get_category,
    cost_per_call,
    tool_risk_level,
    tool_risk_name,
    validate_categories,
    Plan,
    PlanNode,
    heuristic_plan,
    plan_objective,
    format_plan,
    replan_remaining,
    SwarmBudgets,
    SwarmRunner,
    Blackboard,
    Ledger,
    BudgetExceeded,
    FleetRefusal,
    MaxDepthExceeded,
    select_worker_provider,
    spawn_subswarm,
    Verification,
)
from levi.fleet.categories import ALL_TOOLS
from levi.fleet.swarm import (
    WorkerContext,
    default_worker,
    make_counting_registry,
)
from levi.fleet.verify import structural_check


# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------


def test_registry_lists_all_categories_with_valid_tools():
    cats = list_categories()
    assert len(cats) == 34
    known = set(ALL_TOOLS)
    for c in cats:
        assert c.role.strip(), c.name
        assert c.prompt.strip(), c.name
        assert c.cost_class in ("light", "standard", "heavy"), c.name
        for t in c.tools:
            assert t in known, f"{c.name}: unknown tool {t}"
    assert validate_categories() == []


def test_expected_categories_present():
    names = {c.name for c in list_categories()}
    for expected in (
        "executive supervisor project_manager planning research "
        "coding architect uiux database devops qa security "
        "automation browser computer device communication "
        "finance payment support sales negotiation marketing data document "
        "memory learning verification fraud_risk compliance "
        "dispatch bidding coach guardian"
    ).split():
        assert expected in names


def test_read_only_categories_hold_no_mutating_tools():
    mutating = {
        "file_edit",
        "file_write",
        "shell_exec",
        "memory_write",
        "schedule_add",
        "schedule_remove",
        "http_request",
        "delegate",
    }
    for name in ("research", "verification", "fraud_risk"):
        c = get_category(name)
        assert not (set(c.tools) & mutating), name


def test_payment_and_finance_are_stubs():
    assert get_category("payment").stub is True
    assert get_category("finance").stub is True
    assert get_category("payment").tools == []
    assert "shell_exec" not in get_category("finance").tools


def test_tool_risk_classification():
    assert tool_risk_level("shell_exec") == 2
    assert tool_risk_name("shell_exec") == "moderate"
    assert tool_risk_level("file_write") == 2
    assert tool_risk_level("memory_write") == 1
    assert tool_risk_level("memory_read") == 0
    assert tool_risk_name("web_search") == "info"


def test_cost_classes_are_relative_units():
    assert cost_per_call("light") == 1
    assert cost_per_call("standard") == 3
    assert cost_per_call("heavy") == 8


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


def test_supervisor_produces_valid_dag():
    plan = heuristic_plan("Build a SaaS app for managing contractors")
    assert plan.validate() == []
    cats = [n.category for n in plan.nodes]
    assert "coding" in cats
    assert "verification" in cats
    assert plan.nodes[-1].category == "verification"
    # dependencies only point backwards (valid topological order)
    seen = set()
    for n in plan.nodes:
        for d in n.deps:
            assert d in seen, f"{n.id} depends on unseen {d}"
        seen.add(n.id)


def test_supervisor_research_objective():
    plan = plan_objective("Research the best local LLM options")
    assert plan.validate() == []
    assert "research" in [n.category for n in plan.nodes]


def test_plan_rejects_cycle():
    plan = Plan(
        objective="x",
        nodes=[
            PlanNode(
                id="n1", category="research", task="t", acceptance="a", deps=["n2"]
            ),
            PlanNode(
                id="n2", category="research", task="t", acceptance="a", deps=["n1"]
            ),
        ],
    )
    problems = plan.validate()
    assert any("cycle" in p for p in problems)


def test_plan_rejects_unknown_category_and_bad_dep():
    plan = Plan(
        objective="x",
        nodes=[
            PlanNode(
                id="n1", category="nope", task="t", acceptance="a", deps=["ghost"]
            ),
        ],
    )
    problems = plan.validate()
    assert len(problems) == 2


def test_format_plan_renders_dag():
    plan = heuristic_plan("Write a launch blog post")
    text = format_plan(plan)
    assert "Objective: Write a launch blog post" in text
    assert "n1" in text and "verification" in text


def test_replan_remaining_rebuilds_failed_nodes():
    plan = heuristic_plan("Build a small API")
    failed = [plan.nodes[1].id]
    replanned = replan_remaining(plan, failed)
    assert replanned.validate() == []
    ids = [n.id for n in replanned.nodes]
    assert f"{failed[0]}-r" in ids


# ---------------------------------------------------------------------------
# Swarm runner (stub workers — hermetic)
# ---------------------------------------------------------------------------


def _chain_plan() -> Plan:
    return Plan(
        objective="stub objective",
        method="test",
        nodes=[
            PlanNode(
                id="n1", category="research", task="gather", acceptance="notes exist"
            ),
            PlanNode(
                id="n2",
                category="document",
                task="write",
                acceptance="doc exists",
                deps=["n1"],
            ),
            PlanNode(
                id="n3",
                category="verification",
                task="check",
                acceptance="all green",
                deps=["n2"],
            ),
        ],
    )


def _stub_worker(node, category, ctx):
    ctx.blackboard.put(f"done:{node.id}", True)
    return {
        "ok": True,
        "summary": f"stub completed {node.id} as {category.name}",
        "artifacts": [{"name": f"out-{node.id}", "data": node.id}],
    }


def test_swarm_runs_three_node_dag_with_merged_results():
    runner = SwarmRunner(budgets=SwarmBudgets(max_agents=10), worker_fn=_stub_worker)
    report = runner.run(_chain_plan())
    assert report["status"] == "completed"
    assert report["halt_reason"] is None
    for nid in ("n1", "n2", "n3"):
        assert report["nodes"][nid]["status"] == "ok", nid
    assert report["budgets"]["spent"]["agents"] == 3
    assert report["escalations"] == []
    # decision journal persisted
    loaded = SwarmRunner.load(report["run_id"])
    assert loaded is not None
    assert loaded["run_id"] == report["run_id"]


def test_swarm_blackboard_shares_state():
    seen = {}

    def worker(node, category, ctx):
        seen[node.id] = ctx.blackboard.get("done:n1")
        ctx.blackboard.put(f"done:{node.id}", True)
        return {"ok": True, "summary": f"stub finished {node.id} fine", "artifacts": []}

    report = SwarmRunner(worker_fn=worker).run(_chain_plan())
    assert report["status"] == "completed"
    # n2 ran after n1, so it saw n1's blackboard write
    assert seen["n2"] is True


def test_budget_exceeded_halts_with_structured_report():
    runner = SwarmRunner(budgets=SwarmBudgets(max_agents=1), worker_fn=_stub_worker)
    report = runner.run(_chain_plan())
    assert report["status"] == "halted"
    assert report["halt_reason"]["type"] == "budget"
    assert report["halt_reason"]["budget"] == "max_agents"
    assert report["budgets"]["spent"]["agents"] == 1
    assert report["nodes"]["n2"]["status"] == "skipped"


def test_tool_call_budget_enforced():
    budgets = SwarmBudgets(max_tool_calls=1)
    ctx = WorkerContext(
        blackboard=Blackboard(), ledger=Ledger(), budgets=budgets, run_id="t"
    )
    reg = make_counting_registry(
        ["capabilities"], get_category("research"), ctx, deadline=time.time() + 60
    )
    first = reg.execute("capabilities", {})
    assert first.ok
    with pytest.raises(BudgetExceeded) as exc:
        reg.execute("capabilities", {})
    assert exc.value.budget == "max_tool_calls"
    assert ctx.ledger.tool_calls == 1
    assert ctx.ledger.cost_units == 1  # light = 1 unit/call


def test_verification_failure_retries_once_then_escalates():
    calls = {"n": 0}

    def worker(node, category, ctx):
        calls["n"] += 1
        return {"ok": True, "summary": "stub result looks fine", "artifacts": []}

    def always_fail(node, result):
        return Verification(False, "not good enough", "test")

    report = SwarmRunner(worker_fn=worker, verify_fn=always_fail).run(_chain_plan())
    # initial + exactly one retry per wave; the failed node triggers the
    # single allowed replan, whose recovery node also retries once.
    assert calls["n"] == 4
    assert report["nodes"]["n1"]["status"] == "escalated"
    assert report["nodes"]["n1"]["attempts"] == 2
    assert report["replanned"] is True
    assert report["nodes"]["n1-r"]["status"] == "escalated"
    assert report["status"] == "completed_with_escalations"
    assert len(report["escalations"]) == 2


def test_payment_stub_refuses_without_approval_wiring():
    node = PlanNode(id="n1", category="payment", task="pay invoice", acceptance="paid")
    ctx = WorkerContext(
        blackboard=Blackboard(), ledger=Ledger(), budgets=SwarmBudgets(), run_id="t"
    )
    with pytest.raises(FleetRefusal) as exc:
        default_worker(node, get_category("payment"), ctx)
    assert "approval" in str(exc.value).lower()


def test_max_depth_refused():
    budgets = SwarmBudgets(max_depth=2)
    with pytest.raises(MaxDepthExceeded):
        spawn_subswarm("x", depth=3, budgets=budgets, worker_fn=_stub_worker)


def test_permission_check_refuses_out_of_grant_tool():
    ctx = WorkerContext(
        blackboard=Blackboard(),
        ledger=Ledger(),
        budgets=SwarmBudgets(),
        run_id="t",
        permissions=["web_search"],
    )
    ctx.check_permission("web_search")  # granted — no raise
    with pytest.raises(FleetRefusal):
        ctx.check_permission("shell_exec")


def test_structural_verification_catches_empty_result():
    board = Blackboard()
    node = {"task": "t", "acceptance": "a"}
    v = structural_check(node, {"ok": True, "summary": "  "}, board)
    assert not v.ok
    v2 = structural_check(
        node,
        {
            "ok": True,
            "summary": "a real summary here",
            "artifacts": [{"name": "missing"}],
        },
        board,
    )
    assert not v2.ok and "missing" in v2.notes


def test_tool_audit_logged_with_risk():
    from levi.fleet.swarm import _check_budgets  # noqa: F401 (import guard)

    budgets = SwarmBudgets()
    ctx = WorkerContext(
        blackboard=Blackboard(), ledger=Ledger(), budgets=budgets, run_id="t"
    )
    reg = make_counting_registry(
        ["capabilities", "web_search"],
        get_category("research"),
        ctx,
        deadline=time.time() + 60,
    )
    reg.execute("capabilities", {})
    assert len(ctx.ledger.tool_log) == 1
    entry = ctx.ledger.tool_log[0]
    assert entry["tool"] == "capabilities"
    assert entry["risk"] == "info"
    assert entry["ok"] is True
    assert ctx.ledger.risk_summary() == {"info": 1}


def test_select_worker_provider_routes_light_to_local():
    ctx = WorkerContext(
        blackboard=Blackboard(),
        ledger=Ledger(),
        budgets=SwarmBudgets(),
        run_id="t",
        provider="anthropic",
    )
    assert select_worker_provider(get_category("research"), ctx) == "local"
    assert select_worker_provider(get_category("devops"), ctx) == "anthropic"


def test_cli_categories_lists_thirty():
    from levi.fleet.cli import cmd_fleet

    class Args:
        fleet_action = "categories"

    assert cmd_fleet(Args()) == 0


def test_swarm_status_missing_run():
    assert SwarmRunner.load("no-such-run-id") is None


# -- hardening: validation ---------------------------------------------------

def test_plan_rejects_blank_objective():
    with pytest.raises(ValueError, match="objective"):
        Plan(objective="   ", nodes=[], method="heuristic")


def test_plan_node_rejects_blank_task():
    with pytest.raises(ValueError, match="task"):
        PlanNode(id="n1", category="planning", task="", acceptance="done")


def test_replan_remaining_rejects_bad_failed_ids():
    plan = Plan(
        objective="do things",
        nodes=[PlanNode(id="n1", category="planning", task="t1", acceptance="a1")],
        method="heuristic",
    )
    # contract: failed_ids must be a list of non-empty node-id strings
    for bad in (None, 123, ["n1", ""], ["n1", None], "n1"):
        with pytest.raises(ValueError, match="failed_ids"):
            replan_remaining(plan, bad)
    # a well-formed but unknown id is a no-op, not an error
    replanned = replan_remaining(plan, ["no-such-node"])
    assert replanned.objective == "do things (replanned)"


def test_swarm_budgets_reject_non_positive():
    for kwargs in [
        {"max_depth": 0},
        {"max_agents": -1},
        {"max_time_seconds": "600"},
        {"max_tool_calls": True},
        {"max_cost_units": 1.5},
    ]:
        with pytest.raises(ValueError):
            SwarmBudgets(**kwargs)


def test_swarm_load_rejects_malicious_run_id():
    for bad in ("../secret", "a/b", "x" * 65, "", None, 123):
        with pytest.raises(ValueError, match="run_id"):
            SwarmRunner.load(bad)


def test_swarm_load_corrupt_json_warns_and_returns_none(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "r1.json").write_text("{corrupt", encoding="utf-8")
    monkeypatch.setattr("levi.fleet.swarm._fleet_dir", lambda: runs_dir)
    with pytest.warns(UserWarning, match="unreadable"):
        assert SwarmRunner.load("r1") is None


def test_swarm_load_missing_returns_none(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    monkeypatch.setattr("levi.fleet.swarm._fleet_dir", lambda: runs_dir)
    assert SwarmRunner.load("nope") is None
