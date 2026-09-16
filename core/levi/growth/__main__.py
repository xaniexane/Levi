"""CLI: python -m levi.growth

Thin entry point over the growth loop (harvest -> reflect -> consolidate
-> journal). Mirrors ``levi growth`` semantics.

Growth writes ONLY growth-tagged memory entries and the journal — it can
never alter tools, policy, or identity. Cycles are cheap and idempotent
(watermarked harvest).
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_status(args) -> int:
    from levi.growth import status

    dash = status()
    if args.json:
        print(json.dumps(dash, indent=2))
        return 0
    print(f"stage: {dash.get('stage')}")
    blurb = dash.get("stage_blurb")
    if blurb:
        print(f"  {blurb}")
    print(f"cycles completed: {dash.get('cycles_completed')}")
    print(f"learnings consolidated: {dash.get('learnings_consolidated')}")
    kinds = dash.get("learnings_by_kind") or {}
    if kinds:
        print("  by kind: " + ", ".join(f"{k}={v}" for k, v in kinds.items()))
    print(f"experiences pending: {dash.get('experiences_pending')}")
    last = dash.get("last_cycle")
    if last:
        print(f"last cycle: {last.get('id')} ({last.get('mode')}) "
              f"accepted={last.get('accepted')}")
    return 0


def cmd_cycle(args) -> int:
    from levi.growth import run_cycle

    report = run_cycle(use_model=not args.no_model, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"cycle {report.get('cycle_id')}: mode={report.get('mode')} "
          f"dry_run={report.get('dry_run')}")
    cons = report.get("consolidation") or {}
    print(f"  experiences: {report.get('experiences', 0)}  "
          f"learnings proposed: {report.get('learnings_proposed', 0)}  "
          f"accepted: {cons.get('accepted', 0)}")
    if report.get("quiet"):
        print("  quiet cycle: no new experiences to reflect on.")
    return 0


def cmd_journal(args) -> int:
    from levi.growth import read_entries

    entries = read_entries(limit=args.limit)
    if not entries:
        print("journal is empty.")
        return 0
    for e in entries:
        print(f"[{e.get('ts')}] {e.get('id')} mode={e.get('mode')} "
              f"accepted={e.get('accepted')} sources={e.get('sources')}")
    return 0


def cmd_forget(args) -> int:
    # Parental control surface: growth supports forgetting a cycle's
    # journal entry; memory-side forget is handled by the forget flow.
    print("growth forget: use `levi forget` for memory-side removal; "
          "journal entries are append-only.", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.growth",
        description="LEVI growth loop — raise baby Levi (mirrors `levi growth`)",
    )
    ap.add_argument("--json", action="store_true", help="JSON output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="growth dashboard: stage, counts, last cycle") \
        .set_defaults(func=cmd_status)

    p_cyc = sub.add_parser("cycle", help="run one growth cycle")
    p_cyc.add_argument("--dry-run", action="store_true",
                       help="reflect only; write nothing")
    p_cyc.add_argument("--no-model", action="store_true",
                       help="offline rules engine only (never a provider)")
    p_cyc.set_defaults(func=cmd_cycle)

    p_j = sub.add_parser("journal", help="show journal entries (newest first)")
    p_j.add_argument("--limit", type=int, default=10)
    p_j.set_defaults(func=cmd_journal)

    sub.add_parser("forget", help="note on growth forgetting policy") \
        .set_defaults(func=cmd_forget)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
