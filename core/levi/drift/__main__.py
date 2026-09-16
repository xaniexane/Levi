"""``python -m levi.drift`` — goal-drift instrument CLI.

Local only: reads/writes under the LEVI home (``LEVI_HOME`` or
``~/.levi``).

Commands:
    set-goal ID --statement "..." [--tag T ...]
    log --tag T [--tag T ...] --note "..." [--ts ISO]
    card                      # weekly card; prints SILENT when nothing fires
"""

from __future__ import annotations

import argparse

from .tracker import DriftTracker


def _build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="levi.drift", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sg = sub.add_parser("set-goal", help="define a goal and its activity tags")
    sg.add_argument("id")
    sg.add_argument("--statement", required=True)
    sg.add_argument("--tag", action="append", default=[], help="repeatable")

    lg = sub.add_parser("log", help="log an activity")
    lg.add_argument("--tag", action="append", default=[], help="repeatable")
    lg.add_argument("--note", required=True)
    lg.add_argument("--ts", default=None, help="ISO timestamp (default: now)")

    sub.add_parser("card", help="render the weekly card (SILENT when aligned)")
    return p


def main(argv=None) -> int:
    args = _build().parse_args(argv)
    tracker = DriftTracker()
    if args.cmd == "set-goal":
        g = tracker.set_goal(args.id, args.statement, args.tag)
        print(f"goal '{g['id']}' set — tags: {g['tags']}")
    elif args.cmd == "log":
        tracker.log_activity(args.tag, args.note, ts=args.ts)
        print(f"logged: [{', '.join(args.tag)}] {args.note}")
    elif args.cmd == "card":
        card = tracker.weekly_card()
        if card is None:
            print(
                "SILENT — stated goals and recent behavior are aligned (or too little data to say)."
            )
        else:
            print(f"[{card['grade']}] {card['tag']} {card['title']}")
            print()
            print(card["body"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
