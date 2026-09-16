"""Paper-trader leaderboard for the LEVI finance domain.

Aggregates settled paper bets (see :mod:`levi.finance.bets`) into
per-trader rows: bets, wins, win rate, total simulated P&L, diamond-hands
rate, and open-bet count. Ranks by total simulated P&L.

Everything here is paper: the leaderboard measures simulated wagers,
never real trading. Rendered output carries the paper stamp.

Stdlib-only.
"""

from __future__ import annotations

from levi.finance.bets import Bet
from levi.finance.wsb import PAPER_STAMP, assert_clean

__all__ = [
    "build_leaderboard",
    "ranked_leaderboard",
    "render_leaderboard",
    "MIN_BETS_RANKED",
]

#: Traders with fewer settled bets than this are shown but flagged as
#: unranked — a 1-for-1 record is noise, not skill.
MIN_BETS_RANKED = 3


def build_leaderboard(bets: list[Bet]) -> list[dict]:
    """Aggregate bets into one row per trader.

    Rows for traders with no settled bets still appear (open bets count
    toward activity, not toward ranking).
    """
    by_trader: dict[str, list[Bet]] = {}
    for bet in bets:
        by_trader.setdefault(bet.trader, []).append(bet)
    rows: list[dict] = []
    for trader in sorted(by_trader):
        trader_bets = by_trader[trader]
        settled = [b for b in trader_bets if b.status == "settled"]
        open_bets = [b for b in trader_bets if b.status == "open"]
        wins = sum(1 for b in settled if (b.pnl or 0) > 0)
        diamond = [b for b in settled if not b.early_exit]
        rows.append(
            {
                "trader": trader,
                "bets": len(settled),
                "wins": wins,
                "losses": len(settled) - wins,
                "win_rate": round(wins / len(settled), 4) if settled else None,
                "total_pnl": round(sum(b.pnl or 0 for b in settled) + 0.0, 2),
                "diamond_rate": (
                    round(len(diamond) / len(settled), 4) if settled else None
                ),
                "open": len(open_bets),
            }
        )
    return rows


def ranked_leaderboard(rows: list[dict]) -> list[dict]:
    """Rank rows by total simulated P&L (descending).

    Adds ``rank`` (None for traders below ``MIN_BETS_RANKED`` settled
    bets) without mutating the input rows.
    """
    ordered = sorted(rows, key=lambda r: r["total_pnl"], reverse=True)
    out: list[dict] = []
    rank = 0
    for row in ordered:
        copy = dict(row)
        if row["bets"] >= MIN_BETS_RANKED:
            rank += 1
            copy["rank"] = rank
        else:
            copy["rank"] = None
        out.append(copy)
    return out


def _pct(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "n/a"


def _money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def render_leaderboard(rows: list[dict]) -> str:
    """Render ranked leaderboard rows, WSB-flavored, paper-stamped."""
    rows = ranked_leaderboard(rows)
    lines = [
        "🐵 PAPER TRADER LEADERBOARD 🐵",
        f"   ({PAPER_STAMP} — simulated bets only, not financial advice)",
        "",
        f"  {'#':<3} {'trader':<14} {'bets':>4} {'win%':>6} "
        f"{'P&L':>12} {'💎%':>6} {'open':>4}",
        "  " + "-" * 56,
    ]
    if not rows:
        lines.append("  (no paper traders yet — place a bet to get ranked)")
    for row in rows:
        rank = str(row["rank"]) if row["rank"] is not None else "–"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row["rank"], "  ")
        lines.append(
            assert_clean(
                f"  {medal}{rank:<3} {row['trader']:<14} {row['bets']:>4} "
                f"{_pct(row['win_rate']):>6} {_money(row['total_pnl']):>12} "
                f"{_pct(row['diamond_rate']):>6} {row['open']:>4}"
            )
        )
    lines += [
        "",
        f"  Ranked by total simulated P&L (min {MIN_BETS_RANKED} settled "
        "bets to rank).",
        f"  {PAPER_STAMP} — not financial advice.",
    ]
    return assert_clean("\n".join(lines))
