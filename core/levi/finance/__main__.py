"""CLI: python -m levi.finance

Paper-only finance domain (blueprint §5). Mirrors ``levi finance``
exactly: same subcommands, same flags, same semantics — the parser
here is a faithful copy, and dispatch goes through the real
``cmd_finance`` handler.

Hard rules, inherited unchanged:
* The only reachable broker is the paper (simulated) one; live
  trading is structurally disabled in this build.
* `--live` is refused. Paper orders require explicit --yes (HITL).
* Market-data failures are reported honestly (exit 1) — numbers are
  never fabricated. Advisory only, not financial advice.
"""

from __future__ import annotations

import argparse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.finance",
        description="LEVI paper-only finance: quotes, indicators, signals, "
        "paper orders (mirrors `levi finance`)",
    )
    sub = ap.add_subparsers(dest="finance_action")

    p_q = sub.add_parser("quote", help="Latest close + day range via Stooq")
    p_q.add_argument("sym", help="US symbol, e.g. AAPL")
    p_q.add_argument("--json", action="store_true", help="Print the quote as JSON")

    p_i = sub.add_parser("indicators", help="Indicator snapshot for the latest bar")
    p_i.add_argument("sym", help="US symbol, e.g. AAPL")

    p_s = sub.add_parser("signal", help="Advisory signal (paper-only, not financial advice)")
    p_s.add_argument("sym", help="US symbol, e.g. AAPL")
    p_s.add_argument("--json", action="store_true", help="Print the signal as JSON")

    p_pf = sub.add_parser("portfolio", help="Show the paper portfolio ledger")
    p_pf.add_argument("--json", action="store_true",
                      help="Print the portfolio summary as JSON")

    p_o = sub.add_parser("order", help="Paper order (HITL: needs --yes)")
    p_o.add_argument("sym", help="US symbol, e.g. AAPL")
    p_o.add_argument("qty", type=float, help="Quantity (> 0)")
    p_o.add_argument("--side", required=True, choices=["buy", "sell"],
                     help="buy or sell")
    p_o.add_argument("--yes", action="store_true",
                     help="Explicit human confirmation (HITL gate)")
    p_o.add_argument("--live", action="store_true",
                     help="Refused: live trading is not enabled in this build")

    p_d = sub.add_parser("deposit", help="Fund the paper portfolio")
    p_d.add_argument("amount", type=float, help="Amount (> 0)")

    args = ap.parse_args(argv)
    if not getattr(args, "finance_action", None):
        ap.print_help()
        return 2

    from levi.cli.main import cmd_finance

    result = cmd_finance(args)
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
