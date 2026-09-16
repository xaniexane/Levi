"""``levi automation`` CLI: browser plans, primitive registry, safety summary.

Plans and descriptions only — nothing here executes automation.
"""

from __future__ import annotations

import argparse

from .browser import emit_termux_helper, format_plan, plan_browser_job
from .primitives import list_primitives, match_nl


def register_automation_parser(sub) -> None:
    ap = sub.add_parser("automation", help="Automation plans + primitive registry")
    cmds = ap.add_subparsers(dest="automation_cmd")

    plan_p = cmds.add_parser(
        "plan", help="build a browser-automation plan (no execution)"
    )
    plan_p.add_argument(
        "--goal", required=True, help="what the automation should achieve"
    )
    plan_p.add_argument("--url", default="about:blank", help="target URL")
    plan_p.add_argument(
        "--field", action="append", default=[], help="form field (repeatable)"
    )

    emit_p = cmds.add_parser("emit", help="emit the Termux helper for a plan")
    emit_p.add_argument("--goal", required=True, help="plan goal")
    emit_p.add_argument("--url", default="about:blank", help="target URL")

    prim_p = cmds.add_parser("primitives", help="list automation primitives")
    prim_p.add_argument("--band", choices=["green", "yellow", "red"], default=None)

    match_p = cmds.add_parser("match", help="map a phrase to primitives")
    match_p.add_argument("text", help="natural-language request")

    cmds.add_parser("safety", help="print the automation safety summary")


def cmd_automation(args: argparse.Namespace) -> int:
    cmd = getattr(args, "automation_cmd", None) or "safety"

    if cmd == "plan":
        plan = plan_browser_job(args.goal, url=args.url, fields=args.field)
        print(format_plan(plan))
        return 0

    if cmd == "emit":
        plan = plan_browser_job(args.goal, url=args.url)
        print(emit_termux_helper(plan))
        return 0

    if cmd == "primitives":
        for p in list_primitives(args.band):
            hitl = " HITL" if p.hitl_required else ""
            print(f"{p.id} [{p.band}]{hitl} {p.name} — {p.description}")
        return 0

    if cmd == "match":
        found = match_nl(args.text)
        if not found:
            print("no primitive match")
            return 0
        for p in found:
            hitl = " HITL" if p.hitl_required else ""
            print(f"{p.id} [{p.band}]{hitl} {p.name}")
        return 0

    print(
        "LEVI automation: plans only, never silent execution.\n"
        "Green = user-initiated. Yellow = HITL each run. Red = full HITL,\n"
        "and login/captcha/2FA/payments/banking stay manual — always.\n"
        "See docs/AUTOMATION_SAFETY.md."
    )
    return 0
