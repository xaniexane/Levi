"""CLI: python -m levi.demand

Thin entry point over DemandPulse: scan free-text into demand signals,
score opportunities (3-factor worth or the five-factor composite),
and show status. Mirrors ``levi demand``.

Honesty rules are inherited unchanged: five-factor scoring requires a
basis note for every factor (rejected if empty), and every score is
labeled a hypothesis/advisory — never a claim about real demand.
"""

from __future__ import annotations

import argparse
import sys


def _flag_for(factor: str) -> str:
    return {
        "demand": "ff_demand",
        "market_size": "ff_market",
        "competition_gap": "ff_gap",
        "trend_velocity": "ff_velocity",
        "entry_feasibility": "ff_feasibility",
    }[factor]


def cmd_run(args) -> int:
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    if args.scan:
        signal = dp.scan_seed(args.scan, segment=args.segment or "general")
        print(f"Signal [{signal.id}] kind={signal.kind}: {signal.need[:80]}")
        if args.title:
            if args.five_factor:
                return _cmd_five_factor(dp, signal.id, args)
            try:
                opp = dp.score_opportunity(
                    signal.id,
                    args.title,
                    demand_score=float(args.demand_score),
                    serviceability=float(args.serviceability),
                    startup_cost=float(args.cost),
                )
            except ValueError as exc:
                print(f"Opportunity scoring rejected: {exc}", file=sys.stderr)
                return 1
            print(f"Opportunity worth={opp.worth:.2f}: {opp.title}")
    elif args.five_factor:
        print('Five-factor scoring needs --scan "..." --title "..." '
              "plus the --ff-* factors.", file=sys.stderr)
        return 2
    print(dp.format_status())
    return 0


def _cmd_five_factor(dp, demand_id, args) -> int:
    from levi.demand.scoring import FACTORS, parse_weights

    missing = [f for f in FACTORS if getattr(args, _flag_for(f)) is None]
    if missing:
        print("Five-factor scoring needs values for: " + ", ".join(missing) +
              " (flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/"
              "--ff-feasibility, 0-100).", file=sys.stderr)
        return 2
    basis = args.ff_basis
    if not basis or not basis.strip():
        print("Five-factor scoring needs --ff-basis: a note on why these "
              "scores were assigned.", file=sys.stderr)
        return 2
    weights = None
    if args.ff_weights:
        try:
            weights = parse_weights(args.ff_weights)
        except ValueError as exc:
            print(f"Bad --ff-weights: {exc}", file=sys.stderr)
            return 2
    try:
        factor_vals = {f: (float(getattr(args, _flag_for(f))), basis)
                       for f in FACTORS}
        threshold = float(args.ff_threshold or 75.0)
    except (TypeError, ValueError) as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    try:
        card = dp.score_five_factor(demand_id, args.title, factor_vals,
                                    weights=weights, threshold=threshold)
    except ValueError as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    print(card.explain())
    print(dp.format_status())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.demand",
        description="LEVI DemandPulse — demand signals + opportunity scoring "
        "(mirrors `levi demand`)",
    )
    ap.add_argument("--scan", default=None, help="scan free text into a signal"); ap.add_argument("--segment", default="general")
    ap.add_argument("--title", default=None, help="score opportunity title"); ap.add_argument("--demand-score", dest="demand_score", type=float, default=0.6)
    ap.add_argument("--serviceability", type=float, default=0.6); ap.add_argument("--cost", type=float, default=0.2)
    ap.add_argument("--five-factor", action="store_true", help="five-factor composite model")
    ap.add_argument("--ff-demand", type=float, default=None); ap.add_argument("--ff-market", type=float, default=None)
    ap.add_argument("--ff-gap", type=float, default=None); ap.add_argument("--ff-velocity", type=float, default=None)
    ap.add_argument("--ff-feasibility", type=float, default=None)
    ap.add_argument("--ff-basis", default=None, help="REQUIRED: why these scores were assigned")
    ap.add_argument("--ff-weights", default=None, help="e.g. demand=.3,market_size=.25,..."); ap.add_argument("--ff-threshold", type=float, default=75.0)
    ap.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
