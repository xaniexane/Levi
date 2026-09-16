"""CLI: python -m levi.organs list | run <organ> [--seed ...] [--domain ...] [--kwargs-json ...] [--json]

Thin wrapper over levi.organs.registry. All organ calls are pure and
local; this CLI performs no writes.
"""

from __future__ import annotations

import argparse
import json
import sys


def _organ_names() -> list:
    from levi.organs.registry import ORGAN_REGISTRY

    return sorted(ORGAN_REGISTRY)


def cmd_list(args) -> int:
    from levi.organs.registry import list_organs

    organs = list_organs()
    if args.json:
        print(json.dumps(organs, indent=2, sort_keys=True))
    else:
        print("Registered organs:")
        for o in organs:
            print("  %-10s risk=%-4s  %s" % (o["name"], o["risk"], o["entry"]))
    return 0


def cmd_run(args) -> int:
    from levi.organs.registry import run_organ

    kwargs = {}
    try:
        if args.kwargs_json:
            kwargs = json.loads(args.kwargs_json)
            if not isinstance(kwargs, dict):
                raise ValueError("--kwargs-json must decode to a JSON object")
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.seed is not None:
        kwargs.setdefault("seed", args.seed)
    if args.domain is not None:
        kwargs.setdefault("domain", args.domain)

    try:
        result = run_organ(args.organ, **kwargs)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        # Format helpers when available; fall back to JSON.
        fmt = None
        if args.organ == "echoverse":
            from levi.organs.echo import format_echo

            fmt = format_echo
        elif args.organ == "mandella":
            from levi.organs.mandella import format_mandella

            fmt = format_mandella
        elif args.organ == "reim":
            from levi.organs.reim import format_compost

            fmt = format_compost
        elif args.organ == "riem":
            from levi.organs.riem import format_proposals

            fmt = format_proposals
        print(fmt(result) if fmt else json.dumps(result, indent=2, default=str))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.organs", description="LEVI branching organs CLI"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list registered organs")
    p_list.add_argument("--json", action="store_true", help="JSON output")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="run an organ by name")
    p_run.add_argument("organ", help="organ name: %s" % ", ".join(_organ_names()))
    p_run.add_argument("--seed", help="seed string (echoverse, mandella)")
    p_run.add_argument("--domain", help="domain (mandella)")
    p_run.add_argument(
        "--kwargs-json",
        help='extra keyword args as JSON object, e.g. --kwargs-json \'{"record": {...}}\'',
    )
    p_run.add_argument("--json", action="store_true", help="JSON output")
    p_run.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
