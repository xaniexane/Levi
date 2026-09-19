"""CLI for the seven worlds lens."""

from __future__ import annotations

import argparse
import json

from levi.worlds import WORLDS, checkin, classify, recent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi-worlds")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List the seven worlds")

    cl = sub.add_parser("classify", help="Which worlds does this text touch?")
    cl.add_argument("--text", required=True)

    ci = sub.add_parser("checkin", help="Log a note against one world")
    ci.add_argument("--world", required=True)
    ci.add_argument("--note", required=True)

    rc = sub.add_parser("recent", help="Latest check-ins for a world")
    rc.add_argument("--world", required=True)
    rc.add_argument("--limit", type=int, default=10)

    args = ap.parse_args(argv)
    if args.cmd == "list":
        for wid, w in WORLDS.items():
            print(f"{wid:12} {w['name']} — {w['domain']}")
    elif args.cmd == "classify":
        print(json.dumps(classify(args.text), indent=2))
    elif args.cmd == "checkin":
        try:
            print(json.dumps(checkin(args.world, args.note), indent=2))
        except ValueError as e:
            print(f"error: {e}")
            return 1
    elif args.cmd == "recent":
        print(json.dumps(recent(args.world, args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
