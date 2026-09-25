"""CLI: python -m levi.decisions — LEVI's decision journal, local only."""

from __future__ import annotations

import argparse
import sys

from levi.decisions.decisions import DecisionError, DecisionJournal, check


def _journal() -> DecisionJournal:
    return DecisionJournal()


def cmd_decide(args) -> int:
    try:
        d = _journal().decide(args.title, args.reasoning, args.revisit)
    except DecisionError as exc:
        print("decisions: %s" % exc, file=sys.stderr)
        return 1
    print("decision %s recorded — revisit %s" % (d["id"], d["revisit"]))
    print('  "%s"' % d["title"])
    return 0


def cmd_reaffirm(args) -> int:
    try:
        d = _journal().reaffirm(args.id, args.note)
    except DecisionError as exc:
        print("decisions: %s" % exc, file=sys.stderr)
        return 1
    print(
        "decision %s reaffirmed (%d note(s) on record)."
        % (d["id"], len(d["reaffirmations"]))
    )
    return 0


def cmd_retire(args) -> int:
    try:
        d = _journal().retire(args.id, args.why)
    except DecisionError as exc:
        print("decisions: %s" % exc, file=sys.stderr)
        return 1
    print("decision %s retired — composted with reason, not deleted." % d["id"])
    print("  reason: %s" % d["retired_reason"])
    return 0


def cmd_list(args) -> int:
    try:
        items = _journal().list(state=args.state)
    except DecisionError as exc:
        print("decisions: %s" % exc, file=sys.stderr)
        return 1
    if not items:
        print("no decisions%s." % (" (%s)" % args.state if args.state else ""))
        return 0
    for d in items:
        print(
            "[%s] %s — %s (revisit %s)"
            % (d["state"], d["id"], d["title"], d["revisit"])
        )
    return 0


def cmd_status(args) -> int:
    s = _journal().status()
    print(
        "decision journal: %d active · %d retired (%d total)"
        % (s["active"], s["retired"], s["total"])
    )
    print(s["note"])
    return 0


def cmd_check(args) -> int:
    signals = check()
    if not signals:
        print("no decisions due for revisit.")
        return 0
    for sig in signals:
        print("[%s] %s" % (sig["grade"], sig["title"]))
        print("  %s" % sig["body"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi-decisions", description="LEVI's decision journal"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("decide", help="record a decision")
    p.add_argument("title", help="the decision")
    p.add_argument("--reasoning", default="", help="why it was made")
    p.add_argument("--revisit", required=True, help="revisit date YYYY-MM-DD")
    p.set_defaults(fn=cmd_decide)

    p = sub.add_parser("reaffirm", help="record that a decision still holds")
    p.add_argument("id", help="decision id (e.g. d0001)")
    p.add_argument("--note", required=True, help="what still holds")
    p.set_defaults(fn=cmd_reaffirm)

    p = sub.add_parser("retire", help="retire a decision (composted)")
    p.add_argument("id", help="decision id")
    p.add_argument("--why", required=True, help="honest reason")
    p.set_defaults(fn=cmd_retire)

    p = sub.add_parser("list", help="list decisions")
    p.add_argument("--state", default=None, choices=["active", "retired"])
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("status", help="journal status")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("check", help="revisit-due signals")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
