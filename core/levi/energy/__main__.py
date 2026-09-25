"""CLI: python -m levi.energy

Log work sessions, learn peak hours from shipped deep work, and get
time-window recommendations for hard tasks. Everything is local JSON
under ``$LEVI_HOME`` (else ``~/.levi``).
"""

from __future__ import annotations

import argparse
import sys


def _log() -> "object":
    from levi.energy.tracker import EnergyLog

    return EnergyLog()


def cmd_log(args) -> int:
    from levi.energy.tracker import EnergyLog

    log = EnergyLog()
    try:
        s = log.log_session(
            args.start,
            args.end,
            args.kind,
            args.shipped.lower() in ("1", "yes", "true", "y"),
        )
    except ValueError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(
        f"logged {s.id}: {s.kind} {s.duration_min:.0f} min "
        f"shipped={'yes' if s.shipped else 'no'}"
    )
    return 0


def cmd_peaks(args) -> int:
    log = _log()
    print(log.format_peaks(min_sessions=args.min_sessions))
    return 0


def cmd_suggest(args) -> int:
    log = _log()
    try:
        slot = log.suggest_slot(args.weight, now=args.at, duration_min=args.minutes)
    except ValueError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(f"task weight : {slot['task_weight']}")
    print(f"when        : {slot['when']} -> {slot['until']}")
    print(f"basis       : {slot['basis']}")
    print(f"rationale   : {slot['rationale']}")
    return 0


def cmd_list(args) -> int:
    log = _log()
    rows = log.sessions()
    if not rows:
        print("no sessions logged yet")
        return 0
    for s in rows[-args.last :]:
        print(
            f"{s.id} {s.start} -> {s.end} {s.kind} "
            f"{s.duration_min:.0f}min shipped={'yes' if s.shipped else 'no'}"
        )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.energy",
        description="LEVI energy-aware scheduling: learn your real peak "
        "hours from shipped deep work.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("log", help="log a work session")
    p.add_argument(
        "--start", required=True, help="ISO-8601 local start, e.g. 2026-09-15T09:00"
    )
    p.add_argument(
        "--end", required=True, help="ISO-8601 local end, e.g. 2026-09-15T11:30"
    )
    p.add_argument(
        "--kind", default="deep", help="session kind: deep (default), admin, ..."
    )
    p.add_argument(
        "--shipped", default="yes", help="did it produce its outcome? yes/no"
    )
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("peaks", help="show learned peak windows")
    p.add_argument(
        "--min-sessions",
        type=int,
        default=8,
        help="sessions required before peaks are claimed",
    )
    p.set_defaults(func=cmd_peaks)

    p = sub.add_parser("suggest", help="recommend a slot for a task")
    p.add_argument("--weight", default="hard", help="hard|deep|normal|admin|light")
    p.add_argument(
        "--at", default=None, help="injectable now (ISO-8601); defaults to local now"
    )
    p.add_argument("--minutes", type=float, default=60)
    p.set_defaults(func=cmd_suggest)

    p = sub.add_parser("list", help="list recent sessions")
    p.add_argument("--last", type=int, default=20)
    p.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
