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

    p_q = sub.add_parser("quote", help="Latest close + day range")
    p_q.add_argument("sym", help="Symbol, e.g. AAPL (or BTCUSDT with --source binance)")
    p_q.add_argument("--json", action="store_true", help="Print the quote as JSON")
    p_q.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source",
    )
    p_q.add_argument(
        "--wsb", action="store_true", help="WSB presentation skin (paper-only)"
    )

    p_i = sub.add_parser("indicators", help="Indicator snapshot for the latest bar")
    p_i.add_argument("sym", help="Symbol, e.g. AAPL (or BTCUSDT with --source binance)")
    p_i.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source",
    )

    p_s = sub.add_parser(
        "signal", help="Advisory signal (paper-only, not financial advice)"
    )
    p_s.add_argument("sym", help="Symbol, e.g. AAPL (or BTCUSDT with --source binance)")
    p_s.add_argument("--json", action="store_true", help="Print the signal as JSON")
    p_s.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source",
    )
    p_s.add_argument(
        "--wsb",
        action="store_true",
        help="Render the signal as a WSB-style DD post (paper-only)",
    )

    p_pf = sub.add_parser("portfolio", help="Show the paper portfolio ledger")
    p_pf.add_argument(
        "--json", action="store_true", help="Print the portfolio summary as JSON"
    )
    p_pf.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source for valuations",
    )
    p_pf.add_argument(
        "--wsb",
        action="store_true",
        help="WSB skin: positions-or-ban + gain/loss porn (paper-only)",
    )

    p_o = sub.add_parser("order", help="Paper order (HITL: needs --yes)")
    p_o.add_argument("sym", help="US symbol, e.g. AAPL")
    p_o.add_argument("qty", type=float, help="Quantity (> 0)")
    p_o.add_argument(
        "--side", required=True, choices=["buy", "sell"], help="buy or sell"
    )
    p_o.add_argument(
        "--yes", action="store_true", help="Explicit human confirmation (HITL gate)"
    )
    p_o.add_argument(
        "--live",
        action="store_true",
        help="Refused: live trading is not enabled in this build",
    )

    p_d = sub.add_parser("deposit", help="Fund the paper portfolio")
    p_d.add_argument("amount", type=float, help="Amount (> 0)")

    # --- WSB finance expansion (mirrors `levi finance`; all paper-only) ---
    p_bet = sub.add_parser("bet", help="Place a paper YOLO bet (HITL: needs --yes)")
    p_bet.add_argument(
        "sym", help="Symbol, e.g. AAPL (or BTCUSDT with --source binance)"
    )
    p_bet.add_argument("qty", type=float, help="Quantity (> 0)")
    p_bet.add_argument(
        "--side", required=True, choices=["buy", "sell"], help="buy or sell"
    )
    p_bet.add_argument("--trader", default="anon", help="Paper-trader name")
    p_bet.add_argument("--horizon", type=int, default=30, help="Horizon in days")
    p_bet.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source for the entry price",
    )
    p_bet.add_argument(
        "--yes", action="store_true", help="Explicit human confirmation (HITL gate)"
    )

    p_bets = sub.add_parser("bets", help="List paper bets + win rate")
    p_bets.add_argument("--trader", default=None, help="Filter to one trader")
    p_bets.add_argument("--json", action="store_true", help="Print as JSON")

    p_settle = sub.add_parser("settle", help="Settle an open paper bet")
    p_settle.add_argument("bet_id", help="Bet id, e.g. bet-1a2b3c4d")
    p_settle.add_argument(
        "--price", type=float, required=True, help="Exit price (never invented)"
    )
    p_settle.add_argument(
        "--paper-hands", action="store_true", help="Mark as an early exit"
    )

    p_lb = sub.add_parser("leaderboard", help="Paper-trader leaderboard (SIMULATED)")
    p_lb.add_argument("--json", action="store_true", help="Print as JSON")

    p_ct = sub.add_parser(
        "copytrade", help="Simulate copying a paper trader (SIMULATED forecast)"
    )
    p_ct.add_argument("--follow", required=True, help="Paper-trader name to mirror")
    p_ct.add_argument("--capital", type=float, default=10000.0, help="Copier capital")
    p_ct.add_argument("--all", action="store_true", help="Rank every qualifying trader")
    p_ct.add_argument("--json", action="store_true", help="Print as JSON")

    p_bl = sub.add_parser(
        "broker-link",
        help="Draft-only broker-link option (live structurally refused)",
    )
    bl_sub = p_bl.add_subparsers(dest="broker_link_action")
    bl_sub.add_parser("status", help="Show broker-link state (no network)")
    bl_cfg = bl_sub.add_parser("configure", help="Set the draft platform label")
    bl_cfg.add_argument(
        "--platform",
        required=True,
        choices=["alpaca", "binance", "coinbase"],
        help="Platform label for drafts",
    )
    bl_draft = bl_sub.add_parser("draft", help="Prepare a DRAFT order (NOT SENT)")
    bl_draft.add_argument("sym", help="Symbol, e.g. AAPL or BTCUSDT")
    bl_draft.add_argument("qty", type=float, help="Quantity (> 0)")
    bl_draft.add_argument("--side", required=True, choices=["buy", "sell"])
    bl_draft.add_argument(
        "--price", type=float, default=None, help="Reference price (never invented)"
    )
    bl_draft.add_argument(
        "--source",
        default="stooq",
        choices=["stooq", "binance", "synth"],
        help="Market-data source for the reference price",
    )

    args = ap.parse_args(argv)
    if not getattr(args, "finance_action", None):
        ap.print_help()
        return 2

    from levi.cli.main import cmd_finance

    result = cmd_finance(args)
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
