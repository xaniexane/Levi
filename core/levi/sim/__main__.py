"""CLI: python -m levi.sim

Bounded text simulations — every scenario opens and closes with a
SIMULATION banner, is deterministic (seeded), and performs zero real
network I/O. Mirrors ``levi sim``.
"""

from __future__ import annotations

import argparse


def cmd_list(args) -> int:
    from levi.sim import SCENARIOS

    print("Available simulations (all clearly labeled SIMULATION, zero network):")
    for name, fn in SCENARIOS.items():
        doc = (fn.__doc__ or "").strip().splitlines()
        blurb = doc[0] if doc else ""
        print(f"  {name:16s} {blurb}")
    print("\nUsage: python -m levi.sim <scenario> [--seed N]")
    return 0


def cmd_run(args) -> int:
    from levi.sim import run_scenario

    return run_scenario(args.scenario, seed=args.seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.sim",
        description="LEVI bounded simulations — labeled, deterministic, "
        "zero network (mirrors `levi sim`)",
    )
    ap.add_argument(
        "scenario", nargs="?", default=None, help="scenario name (omit to list)"
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="deterministic seed (same seed -> same run)",
    )
    ap.add_argument("--list", action="store_true", help="list scenarios")
    args = ap.parse_args(argv)
    if args.list or not args.scenario:
        return cmd_list(args)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
