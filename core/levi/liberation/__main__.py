"""CLI: python -m levi.liberation — the Liberation Ledger, local only.

Registers services holding your data, scores their hostage-ness with
every component explained, and tracks liberation tasks to receipts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from levi.liberation.ledger import (
    LedgerError,
    LiberationLedger,
    ServiceProfile,
)


def _ledger() -> LiberationLedger:
    return LiberationLedger()


def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def cmd_seed(args) -> int:
    added = _ledger().seed_known()
    if not added:
        print("seed profiles already present — nothing added")
    for name in added:
        print("seeded: %s" % name)
    return 0


def cmd_add_service(args) -> int:
    try:
        data = json.loads(args.json)
    except ValueError as exc:
        print("liberation: bad --json: %s" % exc, file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("liberation: --json must be an object", file=sys.stderr)
        return 2
    try:
        profile = ServiceProfile.from_dict(data)
        _ledger().add_service(profile)
    except (ValueError, TypeError, LedgerError) as exc:
        print("liberation: %s" % exc, file=sys.stderr)
        return 1
    print("registered: %s" % profile.name)
    return 0


def cmd_list(args) -> int:
    services = _ledger().list_services()
    if not services:
        print("no services registered — run: python -m levi.liberation seed")
        return 0
    for s in services:
        print("%s  (%s)" % (s.name, s.category or "uncategorized"))
    return 0


def cmd_score(args) -> int:
    try:
        result = _ledger().score(args.name)
    except LedgerError as exc:
        print("liberation: %s" % exc, file=sys.stderr)
        return 1
    print(
        "%s — hostage score %d/%d: %s"
        % (result["service"], result["total"], result["max"], result["verdict"])
    )
    for c in result["components"]:
        print("  %-10s %2d/%-2d  %s" % (c["name"], c["points"], c["max"], c["reason"]))
    return 0


def cmd_report(args) -> int:
    rep = _ledger().report()
    if not rep["services"]:
        print("no services registered — run: python -m levi.liberation seed")
        return 0
    print("hostage ranking (worst first):")
    for s in rep["services"]:
        print("  %3d  %-35s %s" % (s["total"], s["service"], s["verdict"]))
    print("open liberation tasks: %d" % rep["open_task_count"])
    for t in rep["open_tasks"]:
        print("  %s  %-8s %s" % (t["id"], t["kind"], t["service"]))
    return 0


def cmd_task_add(args) -> int:
    try:
        task = _ledger().add_task(args.service, args.kind, notes=args.notes or "")
    except (LedgerError, ValueError) as exc:
        print("liberation: %s" % exc, file=sys.stderr)
        return 1
    print("queued %s: %s %s" % (task["id"], task["kind"], task["service"]))
    return 0


def cmd_task_done(args) -> int:
    try:
        task = _ledger().complete_task(args.task_id, receipt_notes=args.receipt or "")
    except LedgerError as exc:
        print("liberation: %s" % exc, file=sys.stderr)
        return 1
    print(
        "closed %s with receipt %s" % (task["id"], _ts(task["receipt"]["completed_at"]))
    )
    return 0


def cmd_tasks(args) -> int:
    try:
        tasks = _ledger().list_tasks(status=args.status)
    except LedgerError as exc:
        print("liberation: %s" % exc, file=sys.stderr)
        return 1
    if not tasks:
        print("no tasks" + (" with status %s" % args.status if args.status else ""))
        return 0
    for t in tasks:
        flag = "DONE" if t["status"] == "done" else "OPEN"
        extra = " — %s" % t["notes"] if t["notes"] else ""
        print("%s [%s] %-8s %s%s" % (t["id"], flag, t["kind"], t["service"], extra))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.liberation",
        description="Liberation Ledger — price your exit, then take it. Local only.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seed", help="load the researched hostage profiles")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("add-service", help="register a service (JSON profile)")
    p.add_argument("--json", required=True, help="ServiceProfile as JSON object")
    p.set_defaults(func=cmd_add_service)

    p = sub.add_parser("list", help="list registered services")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("score", help="transparent hostage score for a service")
    p.add_argument("name")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("report", help="ranked hostage report + open tasks")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("task-add", help="queue a liberation task")
    p.add_argument("service")
    p.add_argument("kind", help="export | verify | migrate | delete | confirm")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_task_add)

    p = sub.add_parser("task-done", help="close a task with a receipt")
    p.add_argument("task_id")
    p.add_argument("--receipt", default="")
    p.set_defaults(func=cmd_task_done)

    p = sub.add_parser("tasks", help="list liberation tasks")
    p.add_argument("--status", default=None, help="open | done")
    p.set_defaults(func=cmd_tasks)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
