"""Dream Engine CLI: ``python -m levi.dream once|journal|nudge|cycle``."""

from __future__ import annotations

import argparse
import sys

from levi.dream.cycle import run_nightly
from levi.dream.engine import DreamEngine
from levi.dream.journal import DreamJournal
from levi.dream.symbiote import nudge


def cmd_once(args: argparse.Namespace) -> int:
    engine = DreamEngine()
    if args.text:
        seeds = [{"text": args.text, "source": "cli"}]
    else:
        seeds = engine.collect_seeds(args.limit)
        if not seeds:
            print("no seeds — pass --text or grow some history first")
            return 1
    records = engine.run_once(seeds=seeds)
    for rec in records:
        d = rec.to_dict()
        print(f"— dream ({d['mode']}) from: {str(d['seed'].get('text'))[:70]}")
        for v in d["variants"]:
            print(
                f"  [{v['outcome']:^9}] {v['kind']:16} novelty={v['novelty']} {v['note']}"
            )
        if d["lesson"]:
            print(f"  lesson: {d['lesson']}")
        print(f"  composted: {d['compost_count']}")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    journal = DreamJournal()
    for entry in journal.recent(args.last):
        seed = entry.get("seed", {})
        print(f"[{entry.get('ts', '?')[:16]}] {str(seed.get('text'))[:80]}")
        if entry.get("lesson"):
            print(f"    → {entry['lesson'][:100]}")
    return 0


def cmd_nudge(_args: argparse.Namespace) -> int:
    print(nudge())
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    """Run the full dream → REIM → RIEM cycle (the nightly job's runner)."""
    summary = run_nightly(limit=args.limit)
    print(
        "dream cycle: %d dreams, %d variants, %d composted, %d risky"
        % (
            summary["dreams"],
            summary["variants"],
            summary["compost_branches"],
            summary["risky_branches"],
        )
    )
    print("compost: %s" % summary["compost_file"])
    print("proposals: %d (data only — nothing applied)" % len(summary["proposals"]))
    for lesson in summary["lessons"]:
        print("lesson: %s" % str(lesson)[:120])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="levi.dream", description="LEVI Dream Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_once = sub.add_parser("once", help="dream one cycle over recent seeds")
    p_once.add_argument("--text", default="", help="dream this seed text directly")
    p_once.add_argument("--limit", type=int, default=5)
    p_once.set_defaults(fn=cmd_once)

    p_j = sub.add_parser("journal", help="show recent dreams")
    p_j.add_argument("--last", type=int, default=10)
    p_j.set_defaults(fn=cmd_journal)

    p_n = sub.add_parser("nudge", help="surface the freshest thread")
    p_n.set_defaults(fn=cmd_nudge)

    p_c = sub.add_parser(
        "cycle", help="full dream → REIM → RIEM cycle (nightly job runner)"
    )
    p_c.add_argument("--limit", type=int, default=5)
    p_c.set_defaults(fn=cmd_cycle)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
