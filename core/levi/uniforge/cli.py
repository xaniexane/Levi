"""``levi uniforge`` CLI: plan hybrid builds, run the forge law.

Dry-run is the default. ``build --live`` prints the preview, asks
explicit permission, then executes every step for real.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from levi.automation.hitl import auto_approve

from .si import assemble_plan, forge, plan_readiness
from .surgeon import operate as surgeon_operate
from .surgeon import receipt_json, surgeon_file


def _console_responder(request):
    """Interactive yes/no gate responder. Non-tty stdin denies (fail-closed)."""
    try:
        if not sys.stdin.isatty():
            return {"decision": "denied", "note": "non-interactive stdin"}
        answer = input("[uniforge gate] %s — approve? [y/N] " % request.prompt)
    except (EOFError, KeyboardInterrupt):
        return {"decision": "denied", "note": "no answer"}
    if answer.strip().lower() in ("y", "yes"):
        return {"decision": "approved", "note": "approved at the console"}
    return {"decision": "denied", "note": "declined at the console"}


def _add_subcommands(cmds) -> None:
    """Attach plan/build under an existing argparse subparsers object."""
    plan_p = cmds.add_parser("plan", help="assemble a build plan (preview only)")
    plan_p.add_argument(
        "--target",
        action="append",
        default=[],
        help="target id (repeatable): python-package, static-site, android-apk-scaffold",
    )
    plan_p.add_argument(
        "--workdir", default=".", help="source root the plan builds from"
    )
    plan_p.add_argument("--out", default="", help="write the plan as JSON to FILE")

    build_p = cmds.add_parser("build", help="run the forge law over a plan")
    build_p.add_argument(
        "--target",
        action="append",
        default=[],
        help="target id (repeatable)",
    )
    build_p.add_argument(
        "--workdir", default=".", help="source root the plan builds from"
    )
    build_p.add_argument(
        "--live",
        action="store_true",
        help="execute for real: prints the preview, asks explicit "
        "permission, then runs every step",
    )
    build_p.add_argument(
        "--yes",
        action="store_true",
        help="approve every permission gate (only for runs you fully trust)",
    )
    build_p.add_argument(
        "--receipt", default="", help="write the final receipt as JSON to FILE"
    )

    surgeon_p = cmds.add_parser(
        "surgeon", help="code-surgeon quick cleanup on FILE (preview; --apply writes)"
    )
    surgeon_p.add_argument("file", help="file to clean")
    surgeon_p.add_argument(
        "--apply", action="store_true", help="write the cleaned text back to FILE"
    )
    surgeon_p.add_argument(
        "--receipt", default="", help="write the receipt as JSON to FILE"
    )

    operate_p = cmds.add_parser(
        "operate",
        help="full surgery on FILE: diagnose -> fix -> verify (preview; --apply writes)",
    )
    operate_p.add_argument("file", help="file to operate on")
    operate_p.add_argument(
        "--apply", action="store_true", help="write fixes back to FILE"
    )
    operate_p.add_argument(
        "--receipt", default="", help="write the receipt as JSON to FILE"
    )


def register_uniforge_parser(sub) -> None:
    """Attach the ``levi uniforge`` parser under ``sub`` (argparse subparsers)."""
    up = sub.add_parser(
        "uniforge",
        help="UniForge: one build plan across heterogeneous targets",
    )
    cmds = up.add_subparsers(dest="uniforge_cmd", required=True)
    _add_subcommands(cmds)


def _cmd_plan(args: argparse.Namespace) -> int:
    if not args.target:
        print("error: at least one --target is required", file=sys.stderr)
        return 2
    try:
        plan = assemble_plan(args.target, args.workdir)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(plan.preview())
    readiness = plan_readiness(plan)
    if readiness["tools_missing"]:
        print(
            "\nrefusal note: missing tools: %s — a live run would refuse "
            "cleanly rather than fake this build."
            % ", ".join(readiness["tools_missing"])
        )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(plan.to_dict(), fh, indent=2, sort_keys=True)
        print("\nplan written to %s" % args.out)
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    if not args.target:
        print("error: at least one --target is required", file=sys.stderr)
        return 2
    try:
        plan = assemble_plan(args.target, args.workdir)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(plan.preview())
    print("")
    responder = auto_approve if args.yes else _console_responder
    receipt = forge(
        plan,
        live=args.live,
        responder=responder,
        workdir=os.path.abspath(args.workdir),
    )
    print("decision: %s" % receipt["decision"])
    print("note: %s" % receipt["note"])
    if receipt["decision"] == "executed":
        print("verified: %s" % receipt["verified"])
    if args.receipt:
        with open(args.receipt, "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2, sort_keys=True)
        print("receipt written to %s" % args.receipt)
    return 0 if receipt["decision"] in ("dry-run", "executed") else 1


def _cmd_surgeon(args: argparse.Namespace) -> int:
    if not os.path.isfile(args.file):
        print("error: not a file: %s" % args.file, file=sys.stderr)
        return 2
    receipt = surgeon_file(args.file, apply=args.apply)
    print("file: %s" % receipt["path"])
    print("decision: %s" % receipt["decision"])
    print("fixes: %d" % receipt["total_fixes"])
    for name, count in sorted(receipt["fixes"].items()):
        if count:
            print("  %s: %d" % (name, count))
    if args.receipt:
        with open(args.receipt, "w", encoding="utf-8") as fh:
            fh.write(receipt_json(receipt))
        print("receipt written to %s" % args.receipt)
    return 0


def _cmd_operate(args: argparse.Namespace) -> int:
    if not os.path.isfile(args.file):
        print("error: not a file: %s" % args.file, file=sys.stderr)
        return 2
    receipt = surgeon_operate(args.file, apply=args.apply)
    print("file: %s" % receipt["path"])
    print("decision: %s" % receipt["decision"])
    print("findings before: %d" % len(receipt["findings_before"]))
    for f in receipt["findings_before"]:
        print("  [%s] line %d: %s" % (f["kind"], f["line"], f["detail"]))
    if args.apply:
        applied = sum(receipt["fixes_applied"].values())
        print("fixes applied: %d" % applied)
        print("findings after: %d" % len(receipt["findings_after"]))
        for f in receipt["findings_after"]:
            print("  [%s] line %d: %s" % (f["kind"], f["line"], f["detail"]))
        print("verified: %s" % receipt["verified"])
    if args.receipt:
        with open(args.receipt, "w", encoding="utf-8") as fh:
            fh.write(receipt_json(receipt))
        print("receipt written to %s" % args.receipt)
    return 0 if receipt["decision"] in ("dry-run", "executed") else 1


def cmd_uniforge(args: argparse.Namespace) -> int:
    """Dispatch ``levi uniforge`` subcommands."""
    handlers = {
        "plan": _cmd_plan,
        "build": _cmd_build,
        "surgeon": _cmd_surgeon,
        "operate": _cmd_operate,
    }
    handler = handlers.get(args.uniforge_cmd)
    if handler is None:
        print("error: unknown uniforge command", file=sys.stderr)
        return 2
    return handler(args)
