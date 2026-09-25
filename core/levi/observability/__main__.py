"""Query the observability corpus: ``python -m levi.observability <cmd>``.

Commands:
    recent [--limit N]          newest turns, newest first
    show <turn_id>              full record for one turn
    filter [--outcome O] [--min-risk N] [--route R] [--limit N]
    stats                      corpus census

``--home DIR`` overrides the LEVI home (default ``~``); the corpus lives
at ``<home>/.levi/observability``. ``--json`` prints full records as
JSON; the default human rendering summarizes (full detail on ``show``).

This entrypoint is the standing query surface. The ``levi observe``
top-level CLI command is the same surface wired into ``cli/main.py`` —
see docs/OBSERVABILITY.md § "CLI integration" for the one-region wiring
to add once cli/main.py is free of sibling in-flight work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from levi.observability.schema import TurnTrace
from levi.observability.store import TraceStore

OUTCOMES = ("success", "denied", "failed", "awaiting_permission")


def _store_for(args) -> TraceStore:
    home = getattr(args, "home", None)
    base = Path(home) / ".levi" / "observability" if home else None
    return TraceStore(base_dir=base)


def _as_json(args) -> bool:
    return bool(getattr(args, "json", False))


def _summary(t: TurnTrace) -> str:
    stages = ",".join(s.stage for s in t.stages) or "-"
    tools = ",".join(c.name for c in t.tool_calls) or "-"
    dur = f"{t.duration_ms:.0f}ms" if t.duration_ms is not None else "?"
    return (
        f"{t.turn_id}  {t.ts}  outcome={t.outcome}  risk={t.risk_ceiling}  "
        f"route={t.route}  provider={t.provider}  dur={dur}\n"
        f"    stages: {stages}\n"
        f"    tools: {tools}" + (f"\n    reason: {t.reason}" if t.reason else "")
    )


def _print_traces(traces: List[TurnTrace], as_json: bool) -> int:
    if as_json:
        print(json.dumps([t.to_dict() for t in traces], indent=2, default=str))
    else:
        for t in traces:
            print(_summary(t))
    return 0


def cmd_recent(args) -> int:
    return _print_traces(_store_for(args).recent(limit=args.limit), _as_json(args))


def cmd_show(args) -> int:
    trace = _store_for(args).get(args.turn_id)
    if trace is None:
        print(f"no turn {args.turn_id!r} in the corpus", file=sys.stderr)
        return 1
    if _as_json(args):
        print(json.dumps(trace.to_dict(), indent=2, default=str))
        return 0
    print(_summary(trace))
    print("\n-- stages --")
    for s in trace.stages:
        dur = f"{s.duration_ms:.1f}ms" if s.duration_ms is not None else "n/a"
        ceil = s.risk_ceiling if s.risk_ceiling is not None else "n/a"
        print(f"  {s.stage}: decision={s.decision} dur={dur} risk_ceiling={ceil}")
    if trace.tool_calls:
        print("\n-- tool calls --")
        for c in trace.tool_calls:
            print(f"  {c.name}  params_hash={c.params_hash[:16]}…")
    return 0


def cmd_filter(args) -> int:
    store = _store_for(args)
    traces = store.filter(
        outcome=args.outcome,
        min_risk=args.min_risk,
        route=args.route,
        limit=args.limit,
    )
    return _print_traces(traces, _as_json(args))


def cmd_stats(args) -> int:
    stats = _store_for(args).stats()
    if _as_json(args):
        print(json.dumps(stats, indent=2))
    else:
        print(f"days: {len(stats['days'])}  total traces: {stats['total']}")
        print("by outcome:")
        for outcome, count in sorted(stats["by_outcome"].items()):
            print(f"  {outcome}: {count}")
        print("by risk ceiling:")
        for risk, count in sorted(stats["by_risk"].items()):
            print(f"  risk {risk}: {count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.observability", description="Query LEVI's decision-trace corpus"
    )
    # Global flags live on a parent parser so they work both before and
    # after the subcommand: `... recent --json` and `... --json recent`.
    # SUPPRESS defaults keep the subparser from clobbering values the
    # main parser already set (argparse applies subparser defaults over
    # the shared namespace).
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--home",
        default=argparse.SUPPRESS,
        help="LEVI home dir override (tests)",
    )
    parent.add_argument(
        "--json",
        default=argparse.SUPPRESS,
        action="store_true",
        help="Full records as JSON",
    )
    p.add_argument("--home", default=None, help="LEVI home dir override (tests)")
    p.add_argument("--json", action="store_true", help="Full records as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recent", parents=[parent], help="Newest turns, newest first")
    r.add_argument("--limit", type=int, default=20)
    r.set_defaults(func=cmd_recent)

    s = sub.add_parser("show", parents=[parent], help="Full record for one turn")
    s.add_argument("turn_id")
    s.set_defaults(func=cmd_show)

    f = sub.add_parser(
        "filter", parents=[parent], help="Query by outcome / risk / route"
    )
    f.add_argument("--outcome", choices=OUTCOMES, default=None)
    f.add_argument("--min-risk", type=int, default=None)
    f.add_argument("--route", default=None)
    f.add_argument("--limit", type=int, default=50)
    f.set_defaults(func=cmd_filter)

    st = sub.add_parser("stats", parents=[parent], help="Corpus census")
    st.set_defaults(func=cmd_stats)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
