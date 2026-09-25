"""CLI: python -m levi.promises — LEVI's own promise ledger, local only."""

from __future__ import annotations

import argparse
import sys

from levi.promises.promises import PromiseError, PromiseStore, check


def _store() -> PromiseStore:
    return PromiseStore()


def cmd_make(args) -> int:
    try:
        p = _store().make(args.text, due=args.due, actor=args.actor)
    except PromiseError as exc:
        print("promises: %s" % exc, file=sys.stderr)
        return 1
    print(
        "promise %s recorded%s" % (p["id"], " (due %s)" % p["due"] if p["due"] else "")
    )
    print('  "%s"' % p["text"])
    return 0


def cmd_fulfill(args) -> int:
    try:
        p = _store().fulfill(args.id, evidence=args.evidence)
    except PromiseError as exc:
        print("promises: %s" % exc, file=sys.stderr)
        return 1
    print("promise %s kept." % p["id"])
    if p["evidence"]:
        print("  evidence: %s" % p["evidence"])
    return 0


def cmd_break(args) -> int:
    try:
        p = _store().break_promise(args.id, args.why)
    except PromiseError as exc:
        print("promises: %s" % exc, file=sys.stderr)
        return 1
    print("promise %s recorded as BROKEN (kept on the ledger)." % p["id"])
    print("  reason: %s" % p["why_broken"])
    return 0


def cmd_list(args) -> int:
    try:
        items = _store().list(state=args.state)
    except PromiseError as exc:
        print("promises: %s" % exc, file=sys.stderr)
        return 1
    if not items:
        print("no promises%s." % (" (%s)" % args.state if args.state else ""))
        return 0
    for p in items:
        print(
            "[%s] %s — %s%s"
            % (
                p["state"],
                p["id"],
                p["text"],
                " (due %s)" % p["due"] if p["due"] else "",
            )
        )
    return 0


def cmd_status(args) -> int:
    st = _store()
    s = st.status()
    print(
        "promise ledger: %d kept · %d pending · %d broken (%d total)"
        % (s["kept"], s["pending"], s["broken"], s["total"])
    )
    if s["fulfillment_rate"] is None:
        print("fulfillment rate: n/a")
    else:
        print("fulfillment rate: %.0f%%" % (100.0 * s["fulfillment_rate"]))
    print(s["note"])
    if s["overdue"]:
        print("%d overdue — run 'check' for details." % s["overdue"])
    return 0


def cmd_check(args) -> int:
    signals = check()
    if not signals:
        print("no overdue promises. the ledger is clean.")
        return 0
    for sig in signals:
        print("[%s] %s" % (sig["grade"], sig["title"]))
        print("  %s" % sig["body"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi-promises", description="LEVI's promise ledger"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("make", help="record a promise")
    p.add_argument("text", help="what was promised")
    p.add_argument("--due", default=None, help="due date YYYY-MM-DD")
    p.add_argument("--actor", default="levi", help="who promised")
    p.set_defaults(fn=cmd_make)

    p = sub.add_parser("fulfill", help="mark a promise kept")
    p.add_argument("id", help="promise id (e.g. p0001)")
    p.add_argument("--evidence", default="", help="evidence of fulfillment")
    p.set_defaults(fn=cmd_fulfill)

    p = sub.add_parser("break", help="record a promise as broken")
    p.add_argument("id", help="promise id")
    p.add_argument("--why", required=True, help="honest reason")
    p.set_defaults(fn=cmd_break)

    p = sub.add_parser("list", help="list promises")
    p.add_argument("--state", default=None, choices=["pending", "kept", "broken"])
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("status", help="fulfillment report")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("check", help="overdue-promise signals")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
