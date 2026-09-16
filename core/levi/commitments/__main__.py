"""CLI: python -m levi.commitments — honest habit mechanics, local only."""

from __future__ import annotations

import argparse
import sys

from levi.commitments.commitments import CommitmentError, CommitmentStore


def _store() -> CommitmentStore:
    return CommitmentStore()


def cmd_define(args) -> int:
    try:
        c = _store().define(
            args.name,
            unit=args.unit,
            target=args.target,
            per=args.per,
            rest_days_per_week=args.rest_days,
            mulligans_per_month=args.mulligans,
            start=args.start,
        )
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print(
        "commitment '%s': %g %s per %s%s%s"
        % (
            c["name"],
            c["target"],
            c["unit"],
            c["per"],
            " (rest: %d/wk)" % c["rest_days_per_week"]
            if c["rest_days_per_week"]
            else "",
            " (mulligans: %d/mo)" % c["mulligans_per_month"]
            if c["mulligans_per_month"]
            else "",
        )
    )
    print("No guilt here — the rules are yours. Pause or delete anytime.")
    return 0


def cmd_checkin(args) -> int:
    try:
        r = _store().checkin(args.name, value=args.value, day=args.day)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print("recorded: %s on %s (day total: %g)" % (r["name"], r["day"], r["total"]))
    return 0


def cmd_mulligan(args) -> int:
    try:
        r = _store().mulligan(args.name, day=args.day)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print(r["message"])
    return 0


def _show_status(st: CommitmentStore, name: str) -> int:
    try:
        s = st.status(name)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print("%s — %s" % (s["name"], s["message"]))
    print(
        "  %d/%d periods hit · longest run %d · target %g %s/%s"
        % (s["hits"], s["periods"], s["longest"], s["target"], s["unit"], s["per"])
    )
    if s["missed"]:
        print("  missed: %s" % ", ".join(s["missed"]))
    return 0


def cmd_status(args) -> int:
    st = _store()
    names = [args.name] if args.name else [c["name"] for c in st.list()]
    if not names:
        print(
            "no commitments — define one with: python -m levi.commitments define NAME"
        )
        return 0
    rc = 0
    for n in names:
        rc = _show_status(st, n) or rc
    return rc


def cmd_pause(args) -> int:
    try:
        _store().edit(args.name, paused=True)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print(
        "paused '%s' — streak is held, not broken. Come back when you want." % args.name
    )
    return 0


def cmd_resume(args) -> int:
    try:
        _store().edit(args.name, paused=False)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print("resumed '%s'." % args.name)
    return 0


def cmd_delete(args) -> int:
    try:
        _store().delete(args.name)
    except CommitmentError as exc:
        print("commitments: %s" % exc, file=sys.stderr)
        return 1
    print("deleted '%s'. No penalty, no guilt — it was yours to end." % args.name)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.commitments",
        description="Opt-in commitment devices — streaks without the guilt.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("define", help="define a commitment")
    p.add_argument("name")
    p.add_argument("--unit", default="times")
    p.add_argument("--target", type=float, default=1.0)
    p.add_argument("--per", default="day", choices=["day", "week"])
    p.add_argument(
        "--rest-days", type=int, default=0, help="rest days per week (Sat/Sun first)"
    )
    p.add_argument("--mulligans", type=int, default=0, help="forgiven misses per month")
    p.add_argument("--start", default=None, help="YYYY-MM-DD (default today)")
    p.set_defaults(func=cmd_define)

    p = sub.add_parser("checkin", help="record a check-in")
    p.add_argument("name")
    p.add_argument("--value", type=float, default=1.0)
    p.add_argument("--day", default=None, help="YYYY-MM-DD (default today)")
    p.set_defaults(func=cmd_checkin)

    p = sub.add_parser("mulligan", help="forgive a missed day")
    p.add_argument("name")
    p.add_argument("--day", default=None)
    p.set_defaults(func=cmd_mulligan)

    p = sub.add_parser("status", help="neutral status report")
    p.add_argument("name", nargs="?", default=None)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("pause", help="pause (streak held)")
    p.add_argument("name")
    p.set_defaults(func=cmd_pause)

    p = sub.add_parser("resume", help="resume")
    p.add_argument("name")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("delete", help="delete a commitment")
    p.add_argument("name")
    p.set_defaults(func=cmd_delete)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
