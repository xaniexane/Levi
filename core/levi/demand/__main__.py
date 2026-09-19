"""CLI: python -m levi.demand

Thin entry point over DemandPulse: scan free-text into demand signals,
score opportunities (3-factor worth or the five-factor composite),
and show status. Mirrors ``levi demand``.

Honesty rules are inherited unchanged: five-factor scoring requires a
basis note for every factor (rejected if empty), and every score is
labeled a hypothesis/advisory — never a claim about real demand.

Feed subcommands (score→curate→digest product surface):
  feed    curate stored score cards into a dated digest (optionally scoring
          one new opportunity inline first), dedupe against previous
          digests, store as JSONL
  digest  show the latest stored digest (or --id one)
  watch   mark an opportunity id as watched
"""

from __future__ import annotations

import argparse
import sys

_FEED_COMMANDS = ("feed", "digest", "watch")


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
        print(
            'Five-factor scoring needs --scan "..." --title "..." '
            "plus the --ff-* factors.",
            file=sys.stderr,
        )
        return 2
    print(dp.format_status())
    return 0


def _cmd_five_factor(dp, demand_id, args) -> int:
    from levi.demand.scoring import FACTORS, parse_weights

    missing = [f for f in FACTORS if getattr(args, _flag_for(f)) is None]
    if missing:
        print(
            "Five-factor scoring needs values for: "
            + ", ".join(missing)
            + " (flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/"
            "--ff-feasibility, 0-100).",
            file=sys.stderr,
        )
        return 2
    basis = args.ff_basis
    if not basis or not basis.strip():
        print(
            "Five-factor scoring needs --ff-basis: a note on why these "
            "scores were assigned.",
            file=sys.stderr,
        )
        return 2
    weights = None
    if args.ff_weights:
        try:
            weights = parse_weights(args.ff_weights)
        except ValueError as exc:
            print(f"Bad --ff-weights: {exc}", file=sys.stderr)
            return 2
    try:
        factor_vals = {f: (float(getattr(args, _flag_for(f))), basis) for f in FACTORS}
        threshold = float(args.ff_threshold or 75.0)
    except (TypeError, ValueError) as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    try:
        card = dp.score_five_factor(
            demand_id, args.title, factor_vals, weights=weights, threshold=threshold
        )
    except ValueError as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    print(card.explain())
    print(dp.format_status())
    return 0


def cmd_feed(args) -> int:
    """Score (optionally) → curate → digest, one run."""
    from levi.demand import feed as feedmod
    from levi.demand.pulse import DemandPulse
    from levi.demand.scoring import FACTORS, parse_weights

    dp = DemandPulse()
    if args.title:
        missing = [f for f in FACTORS if getattr(args, _flag_for(f), None) is None]
        if missing:
            print(
                "Inline scoring needs values for: "
                + ", ".join(missing)
                + " (flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/"
                "--ff-feasibility, 0-100).",
                file=sys.stderr,
            )
            return 2
        basis = args.ff_basis
        if not basis or not basis.strip():
            print(
                "Inline scoring needs --ff-basis: a note on why these "
                "scores were assigned.",
                file=sys.stderr,
            )
            return 2
        weights = None
        if args.ff_weights:
            try:
                weights = parse_weights(args.ff_weights)
            except ValueError as exc:
                print(f"Bad --ff-weights: {exc}", file=sys.stderr)
                return 2
        try:
            factor_vals = {
                f: (float(getattr(args, _flag_for(f))), basis) for f in FACTORS
            }
            threshold = float(args.ff_threshold or 75.0)
        except (TypeError, ValueError) as exc:
            print(f"Inline scoring rejected: {exc}", file=sys.stderr)
            return 1
        seed = args.scan or args.title
        try:
            signal = dp.scan_seed(seed, segment=args.segment or "general")
            card = dp.score_five_factor(
                signal.id,
                args.title,
                factor_vals,
                weights=weights,
                threshold=threshold,
            )
        except ValueError as exc:
            print(f"Inline scoring rejected: {exc}", file=sys.stderr)
            return 1
        print(f"Scored [{card.opportunity_id}] {card.title}: {card.composite:.2f}")

    if not dp.score_cards:
        print(
            "No score cards to curate — seed one with: "
            'python -m levi.demand feed --title "…" --ff-demand 80 … --ff-basis "…"',
            file=sys.stderr,
        )
        return 1
    digest = feedmod.curate(dp.score_cards)
    path = feedmod.store_digest(digest)
    print(feedmod.render_digest(digest))
    print(f"stored: {path}")
    return 0


def cmd_digest(args) -> int:
    """Show the latest stored digest (or --id one)."""
    from levi.demand import feed as feedmod

    digest = feedmod.load_digest(args.id) if args.id else feedmod.load_latest()
    if digest is None:
        print("No digests stored yet — run: python -m levi.demand feed")
        return 1
    print(feedmod.render_digest(digest))
    return 0


def cmd_watch(args) -> int:
    """Mark an opportunity id as watched."""
    from levi.demand import feed as feedmod

    added = feedmod.watch_item(args.item)
    print(f"{'Now watching' if added else 'Already watching'} [{args.item}]")
    return 0


def _feed_main(argv) -> int:
    """Subcommand dispatch for: feed | digest | watch."""
    ap = argparse.ArgumentParser(
        prog="levi.demand",
        description="LEVI DemandPulse feed — score→curate→digest, "
        "show digests, watch items",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    feed_p = sub.add_parser(
        "feed", help="curate score cards into a dated digest (JSONL)"
    )
    feed_p.add_argument("--scan", default=None, help="seed text for inline scoring")
    feed_p.add_argument("--segment", default="general")
    feed_p.add_argument(
        "--title", default=None, help="score one opportunity inline before curating"
    )
    feed_p.add_argument("--ff-demand", type=float, default=None)
    feed_p.add_argument("--ff-market", type=float, default=None)
    feed_p.add_argument("--ff-gap", type=float, default=None)
    feed_p.add_argument("--ff-velocity", type=float, default=None)
    feed_p.add_argument("--ff-feasibility", type=float, default=None)
    feed_p.add_argument(
        "--ff-basis", default=None, help="REQUIRED for inline scoring: why these scores"
    )
    feed_p.add_argument("--ff-weights", default=None, help="e.g. 0.3,0.25,0.2,0.15,0.1")
    feed_p.add_argument("--ff-threshold", type=float, default=75.0)
    feed_p.set_defaults(func=cmd_feed)

    dig_p = sub.add_parser("digest", help="show the latest stored digest")
    dig_p.add_argument("--id", default=None, help="show a specific digest id")
    dig_p.set_defaults(func=cmd_digest)

    watch_p = sub.add_parser("watch", help="mark an opportunity id as watched")
    watch_p.add_argument("--item", required=True, help="opportunity_id to watch")
    watch_p.set_defaults(func=cmd_watch)

    args = ap.parse_args(argv)
    return args.func(args)


def main(argv=None) -> int:
    # Feed subcommands dispatch first; everything else keeps the legacy flags.
    peek = list(sys.argv[1:] if argv is None else argv)
    if peek and peek[0] in _FEED_COMMANDS:
        return _feed_main(peek)
    ap = argparse.ArgumentParser(
        prog="levi.demand",
        description="LEVI DemandPulse — demand signals + opportunity scoring "
        "(mirrors `levi demand`)",
    )
    ap.add_argument("--scan", default=None, help="scan free text into a signal")
    ap.add_argument("--segment", default="general")
    ap.add_argument("--title", default=None, help="score opportunity title")
    ap.add_argument("--demand-score", dest="demand_score", type=float, default=0.6)
    ap.add_argument("--serviceability", type=float, default=0.6)
    ap.add_argument("--cost", type=float, default=0.2)
    ap.add_argument(
        "--five-factor", action="store_true", help="five-factor composite model"
    )
    ap.add_argument("--ff-demand", type=float, default=None)
    ap.add_argument("--ff-market", type=float, default=None)
    ap.add_argument("--ff-gap", type=float, default=None)
    ap.add_argument("--ff-velocity", type=float, default=None)
    ap.add_argument("--ff-feasibility", type=float, default=None)
    ap.add_argument(
        "--ff-basis", default=None, help="REQUIRED: why these scores were assigned"
    )
    ap.add_argument(
        "--ff-weights", default=None, help="e.g. demand=.3,market_size=.25,..."
    )
    ap.add_argument("--ff-threshold", type=float, default=75.0)
    ap.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
