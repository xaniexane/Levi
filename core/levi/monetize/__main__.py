"""CLI: python -m levi.monetize <list|show|log|summary|recent|checklist>

Examples:
  python -m levi.monetize list
  python -m levi.monetize show resume-service
  python -m levi.monetize checklist lead-generation
  python -m levi.monetize log --project resume-service --kind sale --amount 30 \\
      --counterparty "A. Client" --note "standard package"
  python -m levi.monetize summary
  python -m levi.monetize recent --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys

from . import ledger
from . import projects as registry


def _cmd_list(_args: argparse.Namespace) -> int:
    for i, p in enumerate(registry.list_projects(), 1):
        lo, hi = p["month3_range"]
        print(f"{i:2d}. {p['slug']:<18} {p['name']}")
        print(
            f"    automation={p['automation']:<6} risk={p['risk_band']:<9} "
            f"setup={p['setup_hours']:<18} month3=${lo}-${hi}"
        )
        print(f"    {p['mechanism']}")
    tot = registry.total_month3_range()
    print(
        f"\ncombined month-3 range: ${tot['month3_conservative']}-${tot['month3_ceiling']} "
        f"({tot['note']})"
    )
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    try:
        p = registry.get(args.slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"== {p['name']} ({p['slug']})")
    for key in (
        "automation",
        "setup_hours",
        "days_to_first_dollar",
        "daily_time_min",
        "risk_band",
    ):
        print(f"  {key}: {p[key]}")
    lo, hi = p["month3_range"]
    print(f"  month3_range: ${lo}-${hi}")
    print(f"  mechanism: {p['mechanism']}")
    if "pricing" in p:
        print("  pricing:")
        for tier, spec in p["pricing"].items():
            print(f"    {tier}: {json.dumps(spec, ensure_ascii=False)}")
    if "products" in p:
        print("  products:")
        for prod, spec in p["products"].items():
            print(f"    {prod}: {json.dumps(spec)}")
    print("  Chauncey-gated steps:")
    for step in p["chauncey_gated"]:
        print(f"    - {step}")
    return 0


def _cmd_checklist(args: argparse.Namespace) -> int:
    try:
        mod = registry.get_module(args.slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"== setup checklist: {args.slug}")
    for i, item in enumerate(mod.setup_checklist(), 1):
        tag = "[Chauncey] " if item["gated"] else "[levi] "
        print(f"  {i}. {tag}{item['step']}")
    return 0


def _cmd_log(args: argparse.Namespace) -> int:
    try:
        rec = ledger.log_event(
            project=args.project,
            kind=args.kind,
            amount=args.amount,
            note=args.note or "",
            counterparty=args.counterparty or "",
            risk_band=args.risk_band,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    print(
        json.dumps(ledger.summarize(project=args.project), indent=2, ensure_ascii=False)
    )
    return 0


def _cmd_recent(args: argparse.Namespace) -> int:
    for rec in ledger.read_events(project=args.project, limit=args.limit):
        print(
            f"{rec['at']}  {rec['project']:<18} {rec['kind']:<10} "
            f"{rec['amount']:>8.2f} {rec['currency']}  {rec['note']}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="levi.monetize")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list the 12 projects")

    p = sub.add_parser("show", help="show one project's details")
    p.add_argument("slug")

    p = sub.add_parser("checklist", help="show one project's setup checklist")
    p.add_argument("slug")
    p.set_defaults(func=_cmd_checklist)

    p = sub.add_parser("log", help="write an income receipt to the ledger")
    p.add_argument("--project", required=True)
    p.add_argument("--kind", required=True, choices=ledger.KINDS)
    p.add_argument("--amount", required=True, type=float)
    p.add_argument("--note", default="")
    p.add_argument("--counterparty", default="")
    p.add_argument("--risk-band", default="low", choices=ledger.RISK_BANDS)
    p.set_defaults(func=_cmd_log)

    p = sub.add_parser("summary", help="income totals")
    p.add_argument("--project", default=None)
    p.set_defaults(func=_cmd_summary)

    p = sub.add_parser("recent", help="recent receipts")
    p.add_argument("--project", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=_cmd_recent)

    sub.choices["list"].set_defaults(func=_cmd_list)
    sub.choices["show"].set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
