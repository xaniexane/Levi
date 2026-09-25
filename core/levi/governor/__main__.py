"""CLI: python -m levi.governor status|top|cooldowns|budgets|why|reset

Run from the repo root with ``PYTHONPATH=core`` (or with the package
installed). All state lives under ``~/.levi/governor/``.
"""

from __future__ import annotations

import argparse
import sys

from levi.governor import (
    BudgetEnforcer,
    CooldownManager,
    Meter,
    PassWallet,
    SpikeDetector,
    summarize,
    top_contributors,
)


def _components(home):
    meter = Meter(home=home)
    wallet = PassWallet(home=home)
    return {
        "meter": meter,
        "detector": SpikeDetector(),
        "cooldowns": CooldownManager(home=home, wallet=wallet),
        "budgets": BudgetEnforcer(meter, home=home),
        "wallet": wallet,
    }


def cmd_status(args, c):
    totals = c["meter"].totals(since=None)
    print(f"Metered calls (all time): {totals['calls']}")
    print(
        f"Tokens: {totals['total_tokens']:,} "
        f"({totals['prompt_tokens']:,} in / {totals['completion_tokens']:,} out)"
    )
    rem = c["budgets"].remaining()
    print(
        f"Session budget: {rem['session_tokens']['remaining']:,} of "
        f"{rem['session_tokens']['budget']:,} remaining"
    )
    print(
        f"Day budget: {rem['day_tokens']['remaining']:,} of "
        f"{rem['day_tokens']['budget']:,} remaining"
    )
    states = c["cooldowns"].status()
    open_now = [s for s, st in states.items() if st.get("state") == "open"]
    half = [s for s, st in states.items() if st.get("state") == "half-open"]
    if open_now:
        print("Cooling down: " + ", ".join(sorted(open_now)))
    elif half:
        print("Half-open (probing): " + ", ".join(sorted(half)))
    else:
        print("Circuits: all closed")
    return 0


def cmd_top(args, c):
    rows = top_contributors(
        c["meter"], window_seconds=args.window, group_by=args.by, limit=args.limit
    )
    if not rows:
        print("No metered calls in the window.")
        return 0
    print(f"Top token contributors (last {args.window}s, by {args.by}):")
    for r in rows:
        print(
            f"  {r['key']}: {r['tokens']:,} tokens "
            f"({r['share']:.1%}, {r['calls']} calls)"
        )
    return 0


def cmd_cooldowns(args, c):
    states = c["cooldowns"].status()
    if not states:
        print("No cool-down circuits recorded.")
        return 0
    for scope, st in states.items():
        if scope == "_state_file":
            print("state file unreadable: all calls refused until reset")
            continue
        extra = ""
        if st["state"] == "open":
            extra = f", retry in {st['retry_in_s']}s"
        print(
            f"  {scope}: {st['state']} "
            f"(breaches: {st['breaches']}{extra}) — {st['last_reason']}"
        )
    return 0


def cmd_budgets(args, c):
    rem = c["budgets"].remaining()
    for name, r in rem.items():
        print(
            f"  {name}: {r['used']:,} used / {r['budget']:,} budget "
            f"({r['remaining']:,} remaining)"
        )
    return 0


def cmd_why(args, c):
    print(
        summarize(
            c["meter"],
            window_seconds=args.window,
            cooldowns=c["cooldowns"],
            budgets=c["budgets"],
            wallet=c["wallet"],
        )
    )
    return 0


def cmd_passes(args, c):
    active = c["wallet"].list_active()
    if not active:
        print("No active burst passes.")
        return 0
    print(
        "Active burst passes (honest priority lane — only valid during "
        "genuine contention):"
    )
    for p in active:
        print(
            f"  {p.pass_id}: scope={p.scope} "
            f"uses {p.uses_remaining}/{p.uses_total} "
            f"expires in {int(p.expires_at - __import__('time').time())}s"
            + (f" note={p.note}" if p.note else "")
        )
    return 0


def cmd_pass_issue(args, c):
    bp = c["wallet"].issue(
        scope=args.scope, uses=args.uses, ttl_seconds=args.ttl, note=args.note or ""
    )
    print(
        f"Issued burst pass {bp.pass_id}: scope={bp.scope}, "
        f"uses={bp.uses_total}, ttl={int(args.ttl)}s"
    )
    print(
        "This pass buys priority probe slots during genuine cool-downs only; "
        "it cannot create contention."
    )
    return 0


def cmd_reset(args, c):
    c["cooldowns"].reset(args.scope)
    print(f"Circuit reset for {args.scope}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="levi.governor", description="LEVI usage governor")
    p.add_argument("--home", default=None, help="HOME dir override (testing)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="totals, budgets, circuit states")

    t = sub.add_parser("top", help="top token contributors")
    t.add_argument("--window", type=int, default=3600)
    t.add_argument(
        "--by", choices=["tool", "task", "agent", "provider"], default="tool"
    )
    t.add_argument("--limit", type=int, default=10)

    sub.add_parser("cooldowns", help="cool-down circuit states")
    sub.add_parser("budgets", help="budget usage and remaining")

    w = sub.add_parser("why", help="plain-language spike diagnosis")
    w.add_argument("--window", type=int, default=3600)

    r = sub.add_parser("reset", help="manually reset a cool-down circuit")
    r.add_argument("scope", help="e.g. provider:openai")

    sub.add_parser("passes", help="list active burst passes")

    pi = sub.add_parser("pass-issue", help="issue a burst pass (operator action)")
    pi.add_argument(
        "--scope", default="*", help="scope the pass covers, e.g. provider:openai"
    )
    pi.add_argument("--uses", type=int, default=1)
    pi.add_argument(
        "--ttl", type=float, default=86400.0, help="time-to-live in seconds"
    )
    pi.add_argument(
        "--note", default="", help="operator note, e.g. a payment reference"
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    c = _components(args.home)
    handlers = {
        "status": cmd_status,
        "top": cmd_top,
        "cooldowns": cmd_cooldowns,
        "budgets": cmd_budgets,
        "why": cmd_why,
        "reset": cmd_reset,
        "passes": cmd_passes,
        "pass-issue": cmd_pass_issue,
    }
    return handlers[args.cmd](args, c)


if __name__ == "__main__":
    sys.exit(main())
