"""``levi council`` CLI: LEVI's own minds arguing to get stronger.

``levi council seats``
    List which LEVI minds are available (never any keys — there are none).

``levi council build --task TEXT --tests PATH [--properties PATH] ...``
    Run the council: each LEVI mind generates → static gates → tests →
    property checks → mutation sample → peer review → synthesize.
    Prints a provenance receipt naming which mind wrote what.
"""

from __future__ import annotations

import argparse
import hashlib
import sys

from .orchestrator import run_council
from .seats import ALL_SEATS, detect_seats


def _seats_cmd(_args: argparse.Namespace) -> int:
    print("council seats — LEVI's own minds (no keys, no network):")
    for seat in detect_seats():
        state = "available" if seat.available else "skipped"
        print(f"  {seat.id:12s} {state}  {seat.label}")
        if seat.note:
            print(f"                 note: {seat.note}")
    return 0


def _build_cmd(args: argparse.Namespace) -> int:
    def _read(path: str | None) -> str | None:
        if not path:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    tests = _read(args.tests)
    if not tests:
        print("error: --tests PATH is required and must be non-empty", file=sys.stderr)
        return 2
    properties = _read(args.properties)

    seats = None
    if args.seats:
        seats = [s.strip() for s in args.seats.split(",") if s.strip()]

    result = run_council(
        task=args.task,
        tests=tests,
        properties=properties,
        seats=seats,
        timeout=args.timeout,
        prop_trials=args.prop_trials,
        max_mutants=args.max_mutants,
    )
    receipt = result["receipt"]
    import json

    print(json.dumps(receipt, indent=2))

    if args.write:
        code = result["winner_code"]
        if not code:
            print(
                "error: --write requested but there is no winning code",
                file=sys.stderr,
            )
            return 1
        if not args.confirm:
            print(
                "refusing to write without --confirm "
                "(Plan→Preview→Permission: confirm explicitly)",
                file=sys.stderr,
            )
            return 1
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if args.expect_sha and args.expect_sha != digest:
            print(
                f"refusing to write: sha256 mismatch (expected {args.expect_sha}, "
                f"got {digest})",
                file=sys.stderr,
            )
            return 1
        with open(args.write, "w", encoding="utf-8") as fh:
            fh.write(code)
        print(f"wrote winner ({receipt['winner']}) to {args.write}  sha256={digest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="levi council")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seats = sub.add_parser("seats", help="list which LEVI minds are available")
    p_seats.set_defaults(func=_seats_cmd)

    p_build = sub.add_parser("build", help="run the council pipeline")
    p_build.add_argument("--task", required=True, help="task brief for the council")
    p_build.add_argument("--tests", required=True, help="path to a tests file (test_*)")
    p_build.add_argument(
        "--properties", default=None, help="optional path to a properties file (prop_*)"
    )
    p_build.add_argument(
        "--seats",
        default=None,
        help=f"comma-separated seat ids (default: all available; "
        f"choose from: {', '.join(ALL_SEATS)})",
    )
    p_build.add_argument("--timeout", type=float, default=120.0)
    p_build.add_argument("--prop-trials", type=int, default=30)
    p_build.add_argument("--max-mutants", type=int, default=12)
    p_build.add_argument("--write", default=None, help="write winning code to PATH")
    p_build.add_argument("--confirm", action="store_true")
    p_build.add_argument("--expect-sha", default=None)
    p_build.set_defaults(func=_build_cmd)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
