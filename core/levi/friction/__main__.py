"""CLI: python -m levi.friction

Capture annoyances in under a second, run the weekly theme review, and
promote candidate themes into real fixes. Local JSON under ``$LEVI_HOME``
(else ``~/.levi``).
"""

from __future__ import annotations

import argparse
import json
import sys


def _log():
    from levi.friction.log import FrictionLog

    return FrictionLog()


def cmd_capture(args) -> int:
    log = _log()
    try:
        e = log.capture(" ".join(args.note))
    except ValueError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(f"captured {e.id}: {e.note[:70]}")
    return 0


def cmd_list(args) -> int:
    log = _log()
    rows = log.entries(since_days=args.days)
    if not rows:
        print("no friction captured yet")
        return 0
    for e in rows:
        print(f"{e.id} {e.ts}  {e.note[:90]}")
    return 0


def cmd_review(args) -> int:
    log = _log()
    review = log.weekly_review(since_days=args.days)
    print(log.format_review(review))
    if args.json:
        print(json.dumps(review, indent=2))
    return 0


def cmd_promote(args) -> int:
    log = _log()
    try:
        fix = log.promote_to_fix(args.candidate, args.fix_note or "")
    except (ValueError, KeyError) as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(f"promoted {fix['id']} (theme={fix['theme']!r} x{fix['count']})")
    print(f"  fix: {fix['fix_note'][:90]}")
    return 0


def cmd_fixes(args) -> int:
    log = _log()
    rows = log.fixes()
    if not rows:
        print("no fixes yet — run a review, then promote a candidate")
        return 0
    for f in rows:
        print(f"{f['id']} theme={f['theme']!r} x{f['count']} @ {f['promoted_at']}")
        print(f"  fix: {f['fix_note'][:90]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.friction",
        description="LEVI friction log: capture annoyances fast, review "
        "weekly, promote themes into fixes.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("capture", help="capture one annoyance, fast")
    p.add_argument("note", nargs="+", help="the annoyance, in your words")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("list", help="list captured entries")
    p.add_argument("--days", type=float, default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("review", help="weekly theme review -> candidates")
    p.add_argument("--days", type=float, default=7)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("promote", help="promote a candidate to a real fix")
    p.add_argument("candidate", help="candidate id, e.g. fx-1a2b3c4d")
    p.add_argument(
        "--fix-note", default=None, help="REQUIRED: what the fix actually is"
    )
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("fixes", help="list converted fixes")
    p.set_defaults(func=cmd_fixes)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
