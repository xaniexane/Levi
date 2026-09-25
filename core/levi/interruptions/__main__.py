"""CLI: python -m levi.interruptions — LEVI's noise ledger, local only."""

from __future__ import annotations

import argparse
import sys

from levi.interruptions.interruptions import (
    InterruptionError,
    InterruptionLedger,
)


def _ledger() -> InterruptionLedger:
    return InterruptionLedger()


def cmd_log(args) -> int:
    try:
        e = _ledger().log(args.source, args.summary, args.value)
    except InterruptionError as exc:
        print("interruptions: %s" % exc, file=sys.stderr)
        return 1
    print("logged [%s] %s — %s" % (e["value"], e["source"], e["summary"]))
    return 0


def cmd_report(args) -> int:
    try:
        r = _ledger().noise_roi(days=args.days)
    except InterruptionError as exc:
        print("interruptions: %s" % exc, file=sys.stderr)
        return 1
    c = r["counts"]
    print(
        "interruption ROI — last %d day(s): %d useful · %d noise · %d mixed"
        % (r["days"], c["useful"], c["noise"], c["mixed"])
    )
    if r["noise_ratio"] is None:
        print("noise ratio: n/a")
    else:
        print("noise ratio: %d%%" % round(100 * r["noise_ratio"]))
    if r["top_noisy_sources"]:
        print("noisiest sources:")
        for s in r["top_noisy_sources"]:
            print(
                "  %s — %dx noise of %d total" % (s["source"], s["noise"], s["total"])
            )
    print("verdict: %s" % r["verdict"])
    return 0


def cmd_check(args) -> int:
    for sig in _ledger().check():
        print("[%s] %s" % (sig["grade"], sig["title"]))
        print("  %s" % sig["body"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi-interruptions", description="LEVI's interruption ledger"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("log", help="log an interruption")
    p.add_argument("source", help="what interrupted (e.g. heartbeat, nudge)")
    p.add_argument("summary", help="what it said/did")
    p.add_argument(
        "value",
        choices=["useful", "noise", "mixed"],
        help="was it worth the interruption?",
    )
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("report", help="noise ROI report")
    p.add_argument("--days", type=int, default=7, help="window in days")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("check", help="weekly noise card signal")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
