"""CLI: python -m levi.premortem

Run the pre-mortem ritual: open a session on a commitment, list imagined
causes of its failure with likelihood/impact (1-5), close for a ranked
mitigation checklist. Local JSON under ``$LEVI_HOME`` (else ``~/.levi``).
"""

from __future__ import annotations

import argparse
import sys


def _pm():
    from levi.premortem.ritual import Premortem

    return Premortem()


def cmd_begin(args) -> int:
    pm = _pm()
    try:
        s = pm.begin(" ".join(args.task))
    except ValueError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(f"session {s.id}: {s.task}")
    print("assume it failed. list the causes.")
    return 0


def cmd_cause(args) -> int:
    pm = _pm()
    try:
        c = pm.add_cause(
            args.session,
            " ".join(args.cause),
            args.likelihood,
            args.impact,
            mitigation=args.mitigation,
        )
    except (ValueError, KeyError) as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(f"cause {c.id}: {c.cause} (L{c.likelihood} x I{c.impact} = {c.risk})")
    return 0


def cmd_close(args) -> int:
    pm = _pm()
    try:
        result = pm.close(args.session)
    except (ValueError, KeyError) as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    print(pm.format_close(result))
    return 0


def cmd_list(args) -> int:
    pm = _pm()
    rows = pm.sessions(status=args.status)
    if not rows:
        print("no pre-mortem sessions yet")
        return 0
    for s in rows:
        print(f"{s.id} [{s.status}] {s.task} ({len(s.causes)} causes)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.premortem",
        description="LEVI pre-mortem ritual: assume the commitment "
        "failed, harvest the causes, rank them, mitigate.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("begin", help="open a session on a commitment")
    p.add_argument("task", nargs="+", help="the commitment to imagine failing")
    p.set_defaults(func=cmd_begin)

    p = sub.add_parser("cause", help="add an imagined cause")
    p.add_argument("session", help="session id")
    p.add_argument("cause", nargs="+", help="what killed it")
    p.add_argument(
        "--likelihood", type=int, required=True, help="1-5, your honest estimate"
    )
    p.add_argument(
        "--impact", type=int, required=True, help="1-5, your honest estimate"
    )
    p.add_argument("--mitigation", default=None, help="how you would blunt this cause")
    p.set_defaults(func=cmd_cause)

    p = sub.add_parser("close", help="rank causes, emit the checklist")
    p.add_argument("session", help="session id")
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("list", help="list sessions")
    p.add_argument("--status", default=None, choices=["open", "closed"])
    p.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
