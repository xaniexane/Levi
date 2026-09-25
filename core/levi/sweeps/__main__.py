"""CLI: python -m levi.sweeps

Run broken-window sweeps against an EXPLICIT root. Safe specs auto-fix;
unsafe specs are reported and never auto-run. ``/`` and the real HOME
are always refused.
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_list(args) -> int:
    from levi.sweeps.sweeps import list_specs

    for s in list_specs():
        print(f"{s.id:18} [{'SAFE' if s.safe else 'UNSAFE'}] {s.area}")
        print(f"{'':18}  {s.description}")
    return 0


def cmd_run(args) -> int:
    from levi.sweeps.sweeps import run_sweep, SweepRefusedError

    try:
        report = run_sweep(args.root, only=args.only, max_age_days=args.max_age_days)
    except SweepRefusedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(report.format())
    if args.json:
        import dataclasses

        print(json.dumps(dataclasses.asdict(report), indent=2))
    return 0 if not report.errors else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.sweeps",
        description="LEVI broken-window sweeps: tiny fixes for small "
        "messes. Requires an explicit root; / and the real HOME are "
        "refused.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list registered sweep specs")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("run", help="run sweeps against an explicit root")
    p.add_argument("root", help="EXPLICIT target directory (required)")
    p.add_argument("--only", nargs="*", default=None, help="run only these spec ids")
    p.add_argument(
        "--max-age-days",
        type=float,
        default=7,
        help="staleness threshold for age-based sweeps",
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
