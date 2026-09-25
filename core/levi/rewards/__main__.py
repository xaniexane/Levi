"""CLI: python -m levi.rewards <command>.

Commands:
  status --account ACCT        full reward standing for an account
  verify                       verify the reward ledger hash chain
  sweep --month YYYY-MM        expire month-scoped reductions past their month
  redeem --account ACCT --units N [--purpose TEXT]
                               burn N extra-usage credits
  badges --account ACCT         list earned badges
  catalog                      list the reward rules catalog
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.rewards import (
    REWARDS_CATALOG,
    balances,
    list_badges,
    month_reduction,
    redeem_usage,
    sweep_expiry,
    verify,
)


def _cmd_status(args) -> int:
    print(json.dumps(balances(args.account), indent=2, ensure_ascii=False))
    return 0


def _cmd_verify(args) -> int:
    result = verify()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def _cmd_sweep(args) -> int:
    result = sweep_expiry(args.month)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_redeem(args) -> int:
    try:
        result = redeem_usage(args.account, args.units, purpose=args.purpose or "")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def _cmd_badges(args) -> int:
    print(json.dumps(list_badges(args.account), indent=2, ensure_ascii=False))
    return 0


def _cmd_catalog(args) -> int:
    slim = [
        {
            "id": r["id"],
            "name": r["name"],
            "trigger": r["trigger"],
            "reward_type": r["reward_type"],
            "per": r["per"],
            "description": r["description"],
        }
        for r in REWARDS_CATALOG
    ]
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    return 0


def _cmd_month(args) -> int:
    print(json.dumps(month_reduction(args.account, args.month), indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.rewards")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="full reward standing for an account")
    p.add_argument("--account", required=True)
    p.set_defaults(fn=_cmd_status)

    p = sub.add_parser("verify", help="verify the reward ledger hash chain")
    p.set_defaults(fn=_cmd_verify)

    p = sub.add_parser("sweep", help="expire lapsed monthly reductions")
    p.add_argument("--month", required=True, help="current month YYYY-MM")
    p.set_defaults(fn=_cmd_sweep)

    p = sub.add_parser("redeem", help="burn extra-usage credits")
    p.add_argument("--account", required=True)
    p.add_argument("--units", required=True, type=int)
    p.add_argument("--purpose", default="")
    p.set_defaults(fn=_cmd_redeem)

    p = sub.add_parser("badges", help="list earned badges")
    p.add_argument("--account", required=True)
    p.set_defaults(fn=_cmd_badges)

    p = sub.add_parser("month", help="tier reduction for an account and month")
    p.add_argument("--account", required=True)
    p.add_argument("--month", required=True)
    p.set_defaults(fn=_cmd_month)

    p = sub.add_parser("catalog", help="list the reward rules catalog")
    p.set_defaults(fn=_cmd_catalog)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
