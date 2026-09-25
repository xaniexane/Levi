"""CLI: python -m levi.feedlab — the feed-ranking transparency lab.

Subcommands:
  demo          run the built-in sample feed through both rankers
  rank FILE     rank the user's own posts (JSON array) both ways
  audit FILE    per-signal contribution ledger for every post
  flags FILE    heuristic bait flags for every post
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from levi.feedlab.feedlab import (
    DEMO_POSTS,
    MODEL_VERSION,
    Post,
    compare,
    flag_bait,
    load_posts,
    rank_bait,
    rank_chronological,
    score,
    transparency,
)


def _posts_from(args) -> list[Post]:
    if args.demo:
        return list(DEMO_POSTS)
    try:
        return load_posts(args.file)
    except ValueError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        raise SystemExit(2) from exc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_rank(args) -> int:
    posts = _posts_from(args)
    now = _now()
    chrono = rank_chronological(posts)
    bait = rank_bait(posts, now)
    print("model: %s" % MODEL_VERSION)
    print("EDUCATIONAL SIMULATION — does not reproduce any real platform's ranker.\n")
    print("== chronological (the honest feed) ==")
    for i, p in enumerate(chrono, 1):
        print("%2d. @%s — %s" % (i, p.author, p.text[:90]))
    print("\n== engagement-bait ranking (the disclosed model) ==")
    for i, (p, total) in enumerate(bait, 1):
        print("%2d. [%7.2f] @%s — %s" % (i, total, p.author, p.text[:90]))
    return 0


def cmd_audit(args) -> int:
    posts = _posts_from(args)
    now = _now()
    for p in posts:
        total, _ = score(p, now)
        print("@%s  bait score %.2f" % (p.author, total))
        for c in transparency(p, now):
            print("    %-20s %8.2f pts  %s" % (c["signal"], c["points"], c["detail"]))
        print()
    return 0


def cmd_flags(args) -> int:
    posts = _posts_from(args)
    for p in posts:
        flags = flag_bait(p)
        print("@%s — %d flag(s)" % (p.author, len(flags)))
        for f in flags:
            print("    [%s] %s: %s" % (f["kind"], f["flag"], f["basis"]))
        if not flags:
            print("    (no heuristic patterns matched)")
    print("\nFlags are HEURISTICS — pattern matches, not verdicts.")
    return 0


def cmd_compare(args) -> int:
    posts = _posts_from(args)
    print(json.dumps(compare(posts, _now()), indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.feedlab",
        description="Feed-ranking transparency lab: disclosed engagement-bait "
        "scoring on your own posts. Educational simulation.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, func, help_text in (
        ("rank", cmd_rank, "rank posts: chronological vs bait model"),
        ("audit", cmd_audit, "per-signal contribution ledger per post"),
        ("flags", cmd_flags, "heuristic bait flags per post"),
        ("compare", cmd_compare, "full side-by-side report as JSON"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "file",
            nargs="?",
            default=None,
            help="JSON array of posts (omit with --demo)",
        )
        p.add_argument(
            "--demo", action="store_true", help="use the built-in sample feed"
        )
        p.set_defaults(func=func)

    args = ap.parse_args(argv)
    if not args.demo and not args.file:
        print("need a posts FILE or --demo", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
