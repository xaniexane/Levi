"""CLI for the LEVI fleet: ``levi fleet categories|plan|run|status``."""

from __future__ import annotations

import json


def register_fleet(sub) -> None:
    """Add the ``fleet`` command and its action subparsers."""
    fleet_p = sub.add_parser(
        "fleet",
        help="Digital workforce: categories, plans, budgeted swarms "
             "(default: categories)",
    )
    fsub = fleet_p.add_subparsers(dest="fleet_action")

    fsub.add_parser("categories", help="List all fleet agent categories")

    plan_p = fsub.add_parser("plan", help="Decompose an objective into a DAG")
    plan_p.add_argument("objective", help="Objective to decompose")
    plan_p.add_argument("--model", action="store_true",
                        help="Use the agentic loop for decomposition "
                             "(default: deterministic heuristic)")

    run_p = fsub.add_parser("run", help="Execute an objective as a swarm")
    run_p.add_argument("objective", help="Objective to execute")
    run_p.add_argument("--max-agents", type=int, default=12)
    run_p.add_argument("--max-minutes", type=float, default=10.0,
                       help="Wall-clock budget in minutes")
    run_p.add_argument("--max-tool-calls", type=int, default=200)
    run_p.add_argument("--max-cost", type=int, default=400,
                       help="Cost-unit budget (relative units, not dollars)")
    run_p.add_argument("--model", action="store_true",
                       help="Use the agentic loop for decomposition")

    status_p = fsub.add_parser("status", help="Show a past swarm run report")
    status_p.add_argument("run_id", help="Run id from a previous fleet run")


def cmd_fleet(args) -> int:
    action = getattr(args, "fleet_action", None) or "categories"
    if action == "categories":
        return _cmd_categories()
    if action == "plan":
        return _cmd_plan(args)
    if action == "run":
        return _cmd_run(args)
    if action == "status":
        return _cmd_status(args)
    print(f"unknown fleet action: {action}")
    return 2


def _cmd_categories() -> int:
    from levi.fleet.categories import list_categories, validate
    problems = validate()
    for c in list_categories():
        stub = " [STUB — approval wiring required]" if c.stub else ""
        print(f"{c.name:16} {c.cost_class:8} "
              f"{len(c.tools):2} tools{stub}")
        print(f"    {c.role}")
    if problems:
        print("\nRegistry problems:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print(f"\n{len(list_categories())} categories, registry valid.")
    return 0


def _cmd_plan(args) -> int:
    from levi.fleet import plan_objective, format_plan
    plan = plan_objective(args.objective, use_model=args.model)
    print(format_plan(plan))
    problems = plan.validate()
    if problems:
        print("\nPlan problems:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    return 0


def _cmd_run(args) -> int:
    from levi.fleet import SwarmBudgets, SwarmRunner, plan_objective
    budgets = SwarmBudgets(
        max_agents=args.max_agents,
        max_time_seconds=int(args.max_minutes * 60),
        max_tool_calls=args.max_tool_calls,
        max_cost_units=args.max_cost,
    )
    plan = plan_objective(args.objective, use_model=args.model)
    print(f"Plan: {len(plan.nodes)} nodes ({plan.method}). Running swarm…")
    runner = SwarmRunner(budgets=budgets)
    report = runner.run(plan)
    print(f"\nRun {report['run_id']}: {report['status']}")
    for nid, n in report["nodes"].items():
        print(f"  {nid} [{n.get('category', '?')}] {n['status']}")
    if report["halt_reason"]:
        print(f"HALT: {report['halt_reason']['detail']}")
    for esc in report["escalations"]:
        print(f"ESCALATED {esc['node']}: {esc['detail']}")
    spent = report["budgets"]["spent"]
    print(f"Spent: {spent['agents']} agents, {spent['tool_calls']} tool "
          f"calls, {spent['cost_units']} cost units, {spent['seconds']}s")
    return 0 if report["status"] == "completed" else 1


def _cmd_status(args) -> int:
    from levi.fleet.swarm import SwarmRunner
    report = SwarmRunner.load(args.run_id)
    if report is None:
        print(f"no fleet run {args.run_id!r} found")
        return 1
    print(json.dumps(report, indent=2))
    return 0
