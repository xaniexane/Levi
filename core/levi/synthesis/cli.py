"""CLI wiring for ``levi synthesis``.

Follows the repo's ``register_*_parser`` precedent: ``register_synthesis_parser``
drops the ``synthesis`` command into the big ``levi`` argparse tree, and
``cmd_synthesis`` dispatches. ``main()`` powers ``python -m levi.synthesis``
standalone. All handlers import organs lazily — this module is stdlib-only.
"""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

ORIGIN = "levi-synthesis/cli"


def add_synthesis_arguments(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach ask/status/prove-offline/config/run/delegate/schedule/tick/receipts."""
    sub = p.add_subparsers(dest="synthesis_cmd")

    a = sub.add_parser(
        "ask", help="Ask the mind; the answer ships with its substrate report"
    )
    a.add_argument(
        "task", nargs="?", default=None, help="The task or question to reason about"
    )
    a.add_argument(
        "--brain-policy",
        choices=["auto", "rules-only"],
        default=None,
        help="Override the configured brain policy for this ask",
    )

    sub.add_parser("status", help="One honest dashboard for the organism")

    po = sub.add_parser(
        "prove-offline",
        help="Run status + ask with the network disabled; prove zero network",
    )
    po.add_argument(
        "--task",
        default="offline self-check: state your substrate and limits",
        help="Task to reason about inside the offline guard",
    )
    po.add_argument(
        "--brain-policy",
        choices=["auto", "rules-only"],
        default="rules-only",
        help="Brain policy for the proof (default rules-only: fast, no torch needed)",
    )

    c = sub.add_parser("config", help="Show or change the synthesis configuration")
    c.add_argument(
        "--show", action="store_true", help="Print the current configuration"
    )
    c.add_argument(
        "--brain-policy",
        choices=["auto", "rules-only"],
        default=None,
        help="Set the brain policy and save it",
    )
    c.add_argument(
        "--scan-budget-ms",
        type=int,
        default=None,
        help="Set the per-tick cycle budget in milliseconds (>= 1) and save it",
    )

    r = sub.add_parser(
        "run",
        help="Run one goal through the agentic loop: perceive, reason, act, verify, receipt",
    )
    r.add_argument("goal", nargs="?", default=None, help="The goal to pursue")
    r.add_argument(
        "--max-steps", type=int, default=10, help="Tool-loop step budget (default 10)"
    )
    r.add_argument(
        "--consent",
        action="store_true",
        help="Explicit Permission step: allow gated tools (file_write, shell_exec, ...). "
        "Without it, consequential acts stop at the gate and the receipt records the block.",
    )

    d = sub.add_parser(
        "delegate",
        help="Fan one job out to bounded sub-runs; one merged receipt",
    )
    d.add_argument("goals", nargs="*", help="Two or more sub-goals to run")
    d.add_argument(
        "--max-steps", type=int, default=6, help="Per-worker step budget (default 6)"
    )
    d.add_argument(
        "--consent",
        action="store_true",
        help="Explicit Permission step for gated tools in every worker.",
    )
    d.add_argument(
        "--mind",
        choices=["goal", "scan"],
        default="goal",
        help="Worker mind: 'goal' runs sub-goals through run_goal (default); "
        "'scan' routes supervisory goals to the Phase 2 scan-mind via "
        "levi.gtpm.adapters.delegate_scan (honest failure if unavailable).",
    )

    s = sub.add_parser("schedule", help="Register a goal to run on a local interval")
    s.add_argument("goal", nargs="?", default=None, help="The goal to schedule")
    s.add_argument(
        "--every",
        type=int,
        required=True,
        help="Interval in seconds between runs",
    )
    s.add_argument(
        "--consent",
        action="store_true",
        help="Explicit Permission step for gated tools when the schedule runs.",
    )

    t = sub.add_parser("tick", help="Run every scheduled goal whose time has come")
    t.add_argument(
        "--max-steps", type=int, default=6, help="Per-run step budget (default 6)"
    )

    rc = sub.add_parser("receipts", help="Show recent agentic-run receipts")
    rc.add_argument("--limit", type=int, default=5, help="How many to show")
    return p


def register_synthesis_parser(sub) -> argparse.ArgumentParser:
    """Drop ``synthesis`` into the ``levi`` subcommand tree."""
    p = sub.add_parser(
        "synthesis",
        help="The organism's mind and vital signs (offline-first)",
    )
    return add_synthesis_arguments(p)


def _cmd_ask(args) -> int:
    from levi.synthesis import mind
    from levi.synthesis.config import SynthesisConfig

    task = (getattr(args, "task", None) or "").strip()
    if not task:
        print('synthesis ask needs a task: levi synthesis ask "your question"')
        return 2
    cfg = SynthesisConfig.load()
    policy = getattr(args, "brain_policy", None) or cfg.brain_policy
    result = mind.ask(task, brain_policy=policy)
    print(result["answer"])
    print()
    print(f"substrate: {result['substrate']}")
    print(f"limits: {result['limits']}")
    return 0


def _cmd_status(args) -> int:
    from levi.synthesis import status as status_mod

    print(status_mod.render_status(status_mod.collect_status()))
    return 0


def _cmd_prove_offline(args) -> int:
    from levi.synthesis import mind, offline as offline_mod
    from levi.synthesis import status as status_mod
    from levi.synthesis.config import SynthesisConfig

    cfg = SynthesisConfig.load()
    policy = getattr(args, "brain_policy", None) or "rules-only"
    task = getattr(args, "task", None) or "offline self-check"
    print("offline proof: disabling sockets, then running status + ask ...")
    try:
        with offline_mod.OfflineGuard():
            dashboard = status_mod.collect_status(cfg)
            result = mind.ask(task, brain_policy=policy)
    except offline_mod.OfflineViolation as exc:
        print(f"OFFLINE PROOF FAILED: {exc}")
        return 1
    print(status_mod.render_status(dashboard))
    print(f"ask substrate under guard: {result['substrate']}")
    print("OFFLINE PROOF PASSED: status + ask completed with the network disabled")
    return 0


def _cmd_config(args) -> int:
    import json

    from levi.synthesis.config import SynthesisConfig

    cfg = SynthesisConfig.load()
    if getattr(args, "brain_policy", None):
        cfg.brain_policy = args.brain_policy
        saved = cfg.save()
        print(f"saved brain_policy={cfg.brain_policy} -> {saved}")
    if getattr(args, "scan_budget_ms", None) is not None:
        # Rebuild through the constructor so the new knob is validated.
        cfg = SynthesisConfig(
            **{**cfg.to_dict(), "scan_budget_ms": args.scan_budget_ms}
        )
        saved = cfg.save()
        print(f"saved scan_budget_ms={cfg.scan_budget_ms} -> {saved}")
    print(json.dumps(cfg.to_dict(), indent=2, sort_keys=True))
    return 0


def _cmd_run(args) -> int:
    import json

    from levi.synthesis import agent as agent_mod
    from levi.synthesis.config import SynthesisConfig

    goal = (getattr(args, "goal", None) or "").strip()
    if not goal:
        print('synthesis run needs a goal: levi synthesis run "your goal"')
        return 2
    cfg = SynthesisConfig.load()
    receipt = agent_mod.run_goal(
        goal,
        config=cfg,
        max_steps=getattr(args, "max_steps", 10) or 10,
        consent=bool(getattr(args, "consent", False)),
    )
    print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    return 0 if receipt.ok else 1


def _cmd_delegate(args) -> int:
    import json

    from levi.synthesis import agent as agent_mod
    from levi.synthesis.config import SynthesisConfig

    goals = [g for g in (getattr(args, "goals", None) or []) if g.strip()]
    if len(goals) < 2:
        print('synthesis delegate needs 2+ goals: levi synthesis delegate "a" "b"')
        return 2
    cfg = SynthesisConfig.load()
    merged = agent_mod.delegate_goals(
        goals,
        config=cfg,
        max_steps=getattr(args, "max_steps", 6) or 6,
        consent=bool(getattr(args, "consent", False)),
        mind=getattr(args, "mind", "goal") or "goal",
    )
    summary = {k: v for k, v in merged.items() if k != "sub_receipts"}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if merged["workers_ok"] == merged["workers"] else 1


def _cmd_schedule(args) -> int:
    import json

    from levi.synthesis import agent as agent_mod

    goal = (getattr(args, "goal", None) or "").strip()
    if not goal:
        print(
            'synthesis schedule needs a goal: levi synthesis schedule "goal" --every 3600'
        )
        return 2
    entry = agent_mod.schedule_goal(
        goal,
        args.every,
        consent=bool(getattr(args, "consent", False)),
    )
    print(json.dumps(entry, indent=2, sort_keys=True))
    print(
        "note: schedules run when 'levi synthesis tick' executes (wire it to a cron/daemon)"
    )
    return 0


def _cmd_tick(args) -> int:
    import json

    from levi.synthesis import agent as agent_mod
    from levi.synthesis.config import SynthesisConfig

    cfg = SynthesisConfig.load()
    ran = agent_mod.tick_schedules(
        config=cfg, max_steps=getattr(args, "max_steps", 6) or 6
    )
    print(json.dumps(ran, indent=2, sort_keys=True))
    return 0


def _cmd_receipts(args) -> int:
    from levi.synthesis import agent as agent_mod

    receipts = agent_mod.read_receipts(limit=getattr(args, "limit", 5) or 5)
    for r in receipts:
        print(
            f"[{r.get('finished_at', '?')}] ok={r.get('ok')} "
            f"steps={r.get('steps_taken')} tools={len(r.get('tool_calls', []))} "
            f"gates={len(r.get('gates_hit', []))} :: {r.get('goal', '')[:100]}"
        )
    if not receipts:
        print("(no receipts yet — run 'levi synthesis run \"goal\"' first)")
    return 0


def cmd_synthesis(args) -> int:
    """Dispatch ``levi synthesis <ask|status|prove-offline|config|run|delegate|schedule|tick|receipts>``."""
    cmd = getattr(args, "synthesis_cmd", None)
    if cmd == "ask":
        return _cmd_ask(args)
    if cmd == "status":
        return _cmd_status(args)
    if cmd == "prove-offline":
        return _cmd_prove_offline(args)
    if cmd == "config":
        return _cmd_config(args)
    if cmd == "run":
        return _cmd_run(args)
    if cmd == "delegate":
        return _cmd_delegate(args)
    if cmd == "schedule":
        return _cmd_schedule(args)
    if cmd == "tick":
        return _cmd_tick(args)
    if cmd == "receipts":
        return _cmd_receipts(args)
    print(
        "usage: levi synthesis {ask,status,prove-offline,config,run,delegate,schedule,tick,receipts}"
    )
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Standalone entry: ``python -m levi.synthesis ...``."""
    parser = argparse.ArgumentParser(prog="levi synthesis")
    add_synthesis_arguments(parser)
    args = parser.parse_args(argv)
    return cmd_synthesis(args)


__all__ = [
    "ORIGIN",
    "add_synthesis_arguments",
    "register_synthesis_parser",
    "cmd_synthesis",
    "main",
]
