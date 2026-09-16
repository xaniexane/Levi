"""CLI: python -m levi.recap — your year, computed on-device."""

from __future__ import annotations

import argparse
import sys

from levi.recap.recap import (
    RecapError,
    compute_stats,
    load_events,
    render_html,
    render_text,
    sample_events,
)


def cmd_stats(args) -> int:
    try:
        events = load_events(args.events)
    except RecapError as exc:
        print("recap: %s" % exc, file=sys.stderr)
        return 1
    print(render_text(compute_stats(events, year=args.year)))
    return 0


def cmd_html(args) -> int:
    try:
        events = load_events(args.events)
    except RecapError as exc:
        print("recap: %s" % exc, file=sys.stderr)
        return 1
    page = render_html(compute_stats(events, year=args.year), title=args.title)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(page)
        print("wrote %s (standalone — no external requests)" % args.out)
    else:
        print(page)
    return 0


def cmd_sample(args) -> int:
    p = sample_events(args.out, year=args.year, n=args.n, seed=args.seed)
    print("wrote synthetic sample (%d events): %s" % (args.n, p))
    print("labeled synthetic in the file — never mix with real data")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.recap",
        description="Local annual recap — Wrapped-style cards, on-device.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("stats", help="text recap from a JSONL event file")
    p.add_argument("events")
    p.add_argument("--year", type=int, default=None)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("html", help="standalone HTML recap card")
    p.add_argument("events")
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--title", default="My Year in Review")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_html)

    p = sub.add_parser("sample", help="generate synthetic sample events")
    p.add_argument("--out", default="sample.jsonl")
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--n", type=int, default=400)
    p.add_argument("--seed", type=int, default=7)
    p.set_defaults(func=cmd_sample)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
