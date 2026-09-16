"""Simulated copy trading for the LEVI finance domain.

Mirrors a paper trader's settled bets inside the simulation: for each of
the followed trader's settled bets, the copier takes the same
side/symbol at the same entry and exit prices, with quantities scaled to
the copier's capital. The report compares copying vs. not copying (the
honest baseline: sitting out = $0 on those signals) and can rank every
trader by forecasted copy outcome.

Honest limitations, stated in every report:

* The mirror assumes the copier gets the trader's exact fills — no
  slippage, no fees, no partial fills. Real copying would do worse.
* Past simulated bets do not predict future results; a hot paper streak
  is not skill until it survives many more bets.
* Everything is paper. Nothing here routes an order anywhere.

Stdlib-only.
"""

from __future__ import annotations

from levi.finance.bets import Bet
from levi.finance.wsb import PAPER_STAMP, assert_clean

__all__ = [
    "mirror_report",
    "compare_traders",
    "render_copy_report",
    "NoSettledBets",
]


class NoSettledBets(ValueError):
    """Raised when the followed trader has no settled paper bets."""


def _r2(value: float) -> float:
    return round(value + 0.0, 2)


def mirror_report(bets: list[Bet], follow: str, capital: float = 10000.0) -> dict:
    """Simulate copying ``follow``'s settled paper bets.

    The copier splits ``capital`` equally across the trader's settled
    bets (notional per bet = capital / n) and mirrors each bet's
    side/symbol/entry/exit. Returns a forecasted-outcome dict.
    """
    if isinstance(capital, bool) or not isinstance(capital, (int, float)):
        raise ValueError(f"capital must be a number, got {capital!r}")
    capital = float(capital)
    if capital <= 0:
        raise ValueError(f"capital must be positive, got {capital!r}")
    trader = str(follow or "").strip()
    if not trader:
        raise ValueError("follow must name a paper trader")
    settled = [
        b
        for b in bets
        if b.trader == trader and b.status == "settled" and b.exit_price is not None
    ]
    if not settled:
        raise NoSettledBets(
            f"paper trader {trader!r} has no settled bets to copy — "
            "nothing was simulated."
        )
    n = len(settled)
    notional = capital / n
    legs: list[dict] = []
    copier_pnl = 0.0
    wins = 0
    for bet in settled:
        qty = notional / bet.entry_price
        sign = 1.0 if bet.side == "buy" else -1.0
        pnl = qty * (bet.exit_price - bet.entry_price) * sign
        copier_pnl += pnl
        if pnl > 0:
            wins += 1
        legs.append(
            {
                "symbol": bet.symbol,
                "side": bet.side,
                "trader_qty": bet.qty,
                "copier_qty": round(qty, 6),
                "entry_price": bet.entry_price,
                "exit_price": bet.exit_price,
                "pnl": _r2(pnl),
            }
        )
    trader_pnl = _r2(sum(b.pnl or 0 for b in settled))
    return {
        "follow": trader,
        "n_mirrored": n,
        "capital": _r2(capital),
        "notional_per_bet": _r2(notional),
        "copier_pnl": _r2(copier_pnl),
        "copier_win_rate": round(wins / n, 4),
        "trader_pnl": trader_pnl,
        "baseline": "not copying (sitting out) = $0.00 on these signals",
        "baseline_pnl": 0.0,
        "beat_baseline": _r2(copier_pnl) > 0,
        "legs": legs,
        "assumptions": [
            "copier gets the trader's exact entry/exit fills",
            "no slippage, no fees, no partial fills (real copying is worse)",
            "capital split equally across mirrored bets",
            "past simulated bets do not predict future results",
        ],
    }


def compare_traders(
    bets: list[Bet], capital: float = 10000.0, min_bets: int = 3
) -> list[dict]:
    """Forecasted copy outcome for every trader, ranked by copier P&L.

    Traders with fewer than ``min_bets`` settled bets are skipped — a
    tiny sample is noise, not a track record.
    """
    reports: list[dict] = []
    for trader in sorted({b.trader for b in bets}):
        settled = [b for b in bets if b.trader == trader and b.status == "settled"]
        if len(settled) < min_bets:
            continue
        try:
            reports.append(mirror_report(bets, trader, capital=capital))
        except NoSettledBets:  # pragma: no cover — guarded by the count
            continue
    return sorted(reports, key=lambda r: r["copier_pnl"], reverse=True)


def _money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def render_copy_report(report: dict) -> str:
    """Render a mirror report, WSB-flavored, paper-stamped."""
    lines = [
        f"🪞 COPY TRADE SIMULATION — following @{report['follow']} 🪞",
        f"   ({PAPER_STAMP} — forecast, not financial advice)",
        "",
        f"  mirrored bets : {report['n_mirrored']}",
        f"  copier capital: ${report['capital']:,.2f} "
        f"(${report['notional_per_bet']:,.2f} per bet)",
        f"  copier P&L    : {_money(report['copier_pnl'])} "
        f"(win rate {report['copier_win_rate']:.0%})",
        f"  trader's P&L  : {_money(report['trader_pnl'])} (their own sizing)",
        f"  baseline      : {report['baseline']}",
    ]
    verdict = (
        "📈 copying beats sitting out — on THESE bets, in THIS simulation"
        if report["beat_baseline"]
        else "📉 copying loses to sitting out — the ape stayed home and won"
    )
    lines += ["", f"  verdict: {verdict}", "", "  honest fine print:"]
    for note in report.get("assumptions", []):
        lines.append(f"    • {note}")
    lines += [
        "",
        f"  {PAPER_STAMP} — not financial advice.",
    ]
    return assert_clean("\n".join(lines))
