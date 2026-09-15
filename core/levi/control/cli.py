"""CLI for the LEVI control plane: approvals, ledger, routing."""

from __future__ import annotations

import json


def register_control(sub) -> None:
    """Add the ``approve`` / ``ledger`` / ``route`` commands."""

    approve_p = sub.add_parser(
        "approve",
        help="Human control plane: list / approve / deny pending actions "
             "(default: list)",
    )
    approve_p.add_argument("decision", nargs="?", default="list",
                           choices=["list", "approve", "deny", "for-workflow"],
                           help="Decision to take")
    approve_p.add_argument("approval_id", nargs="?",
                           help="Approval id (from list)")
    approve_p.add_argument("--note", default="",
                           help="Decision note recorded in history")
    approve_p.add_argument("--workflow", default="",
                           help="Workflow key for 'for-workflow' grants")

    ledger_p = sub.add_parser(
        "ledger",
        help="Decision & execution ledger (default: stats)",
    )
    ledger_p.add_argument("action", nargs="?", default="stats",
                          choices=["stats", "query", "recent"])
    ledger_p.add_argument("--task", default="",
                          help="Task id for 'query'")

    route_p = sub.add_parser(
        "route",
        help="AI router: show the planned route for a task",
    )
    route_p.add_argument("action", nargs="?", default="plan",
                         choices=["plan"])
    route_p.add_argument("task", nargs="?", default="",
                         help="Task text to route")
    route_p.add_argument("--budget", type=float, default=None,
                         help="Task budget in relative cost units")
    route_p.add_argument("--local-only", action="store_true",
                         help="Restrict to local models (privacy)")


def cmd_approve(args) -> int:
    from levi.control.approvals import ApprovalEngine, ApprovalNotFound
    engine = ApprovalEngine()
    decision = args.decision
    if decision == "list":
        pending = engine.pending()
        if not pending:
            print("No pending approvals.")
            return 0
        for r in pending:
            print(f"{r['id']}")
            print(f"  [{r['risk_name'].upper()}] {r['description']}")
            if r.get("reason"):
                print(f"  why: {r['reason']}")
            if r.get("estimated_impact"):
                print(f"  impact: {r['estimated_impact']}")
            if r.get("affected_systems"):
                print(f"  systems: {', '.join(r['affected_systems'])}")
            print(f"  requested: {r.get('created_at', '?')}")
        print(f"\n{len(pending)} pending. "
              "levi approve approve <id> | levi approve deny <id>")
        return 0
    if not args.approval_id:
        print(f"approval id required for '{decision}'")
        return 2
    try:
        if decision == "approve":
            r = engine.approve_once(args.approval_id, note=args.note)
        elif decision == "deny":
            r = engine.deny(args.approval_id, note=args.note)
        else:  # for-workflow
            r = engine.approve_for_workflow(
                args.approval_id, workflow_key=args.workflow,
                note=args.note)
    except ApprovalNotFound as exc:
        print(str(exc))
        return 1
    print(f"{r['status']}: {r['id']} ({r.get('decision', '')})")
    return 0


def cmd_ledger(args) -> int:
    from levi.control.ledger import LedgerWriter
    ledger = LedgerWriter()
    action = args.action
    if action == "stats":
        print(json.dumps(ledger.stats(), indent=2))
        return 0
    if action == "recent":
        for t in ledger.recent_tasks():
            print(f"{t['task_id']} [{t['status']}] "
                  f"{t['objective'][:70]} ({t['cost_units']:.1f}u)")
        return 0
    if action == "query":
        if not args.task:
            print("--task <id> required for query")
            return 2
        task = ledger.get_task(args.task)
        if task is None:
            print(f"no task {args.task!r} in the ledger")
            return 1
        print(json.dumps(task, indent=2, default=str))
        return 0
    print(f"unknown ledger action: {action}")
    return 2


def cmd_route(args) -> int:
    from levi.control.router import plan as plan_task_route
    if not args.task:
        print("task text required: levi route plan \"<task>\"")
        return 2
    rp = plan_task_route(
        args.task,
        budget_units=args.budget,
        privacy="local-only" if args.local_only else "standard",
    )
    print(f"Task: {args.task[:120]}")
    print(f"Complexity: {rp.complexity}")
    print(f"Model:      {rp.model}")
    print(f"Category:   {rp.category}  (tools: {len(rp.tools)})")
    print(f"Strategy:   {rp.strategy} — {rp.strategy_detail}")
    print(f"Est. cost:  ~{rp.est_cost_units:.1f} relative units")
    if rp.learned_from_history:
        print("Routing:    learned from ledger history")
    else:
        print("Routing:    heuristic (no qualifying ledger history yet)")
    print("\nWhy:")
    for line in rp.explanation:
        print(f"  · {line}")
    return 0
