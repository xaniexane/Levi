"""WSB presentation skin for the LEVI finance domain.

Renders signals, portfolios, and quotes with WallStreetBets energy —
DD posts, "positions or ban", gain/loss porn, diamond-hands lore —
while LEVI's own signal engine does the analysis underneath.

Binding rules for this module:

* CLEAN SLANG ONLY. ``_BANNED_DIGESTS`` is a hard denylist (SHA-256
  digests of the denylisted tokens — no literal ever appears in source);
  every public renderer runs ``assert_clean`` over its output, and trader
  names are screened at bet placement. A slur is never rendered, whatever
  the input.
* HONESTY. Confidence is always presented as *heuristic agreement*,
  never as a probability. Every renderer stamps its output
  ``PAPER ONLY — SIMULATED`` and advisory output carries
  ``not financial advice``. The skin changes the voice, never the
  numbers: it renders ``Signal``/ledger data verbatim.
* PAPER ONLY. Nothing here can place, route, or suggest a real order.

Stdlib-only: ``re``, ``hashlib``.
"""

from __future__ import annotations

import hashlib
import re

__all__ = [
    "BANNED_DIGEST_COUNT",
    "SlurDetected",
    "assert_clean",
    "dd_post",
    "positions_or_ban",
    "gain_loss_porn",
    "hands_report",
    "ticker_tape",
    "wsb_quote",
    "ADVISORY_FOOTER",
    "PAPER_STAMP",
]

#: Hard denylist — WSB-flavored slurs and general hate terms, stored as
#: SHA-256 hex digests of the normalized (lowercased) tokens. No literal
#: denylisted token appears in this file or anywhere else in the public
#: tree: digests screen input, they do not reproduce the tokens. (The
#: digests themselves are one-way; knowing them reveals nothing.)
#:
#: Maintainer note (offline, safety review only): the canonical token
#: list is kept with the safety review notes, not in source. To
#: regenerate this set, lowercase each canonical token and take
#: ``hashlib.sha256(token.encode("utf-8")).hexdigest()``.
_BANNED_DIGESTS: frozenset[str] = frozenset(
    {
        "158869a97379229b7681efae9d7f9c9214134e836d649ba53477c0c111414d59",
        "c1cabb6f6e431f9c4dea4c3b3264d6fe3829241d674f3496a2dfff6658f0363e",
        "bd331fb1d24298f52943034a243a341877957b895f4372b11babb87262904ed6",
        "e35a01bb6bf5a69f9ab2c9a1c00538f17cd2c7448f7646a679a61f6817840429",
        "07578d48f69854113fabff750a97fc46eec71dcaaef4cde8bdb33cb59ce346d3",
        "8f5083e3e5c7dc8932f2bf58212f963f3a44752618c96297f82623f736c52738",
        "1e02eec4f1095143be282056557034d4e8ab915342c1af508223141d472d2347",
        "120f6e5b4ea32f65bda68452fcfaaef06b0136e1d0e4a6f60bc3771fa0936dd6",
        "5b3ae48be122f7ed19b4cc587649f41f9d2565df51cfa332f8e7806f4ebb9032",
        "f9d0d9b18ae9033a5ea36df19bf279b059e887a9ae785db81117bceaecc95933",
        "45cd3e1bb472d8e285a160a95f6409ec5ce86102e9caaaf0b63fc11db04ab559",
        "c3de533e9b7fe63b79f648687a30d2861edd92fe7c3cd1f2c485e0a605367624",
        "268651b3ece980102f18871fde07189372961e056f858ca147a28d004f876b03",
        "98b52c4b6b7d1f48e7477a5ccc10955dd195d0ac5a38c8281bfeb08762634909",
        "044eb98b18769b887d5a0258f675e413058b8e9fc9b9786b418bfc6f03f26c98",
        "16ea09fc78ca83ca502cbcf2377acdf280bf18f61e259153f0868405eedab5ef",
        "402f7ebd98864afed4817ff4718d357dbfa95458aa4236d6c5959536956fa4e5",
        "886d51e97ad7931d0d2af8439ca6d9e4887e3c2b469ed247cbd68ceb3649ccde",
        "92a9bf818e7e00021b6d6959f877f5df11b0f989e486db38f35853ebbd552086",
    }
)

#: Public count of denylisted tokens (the tokens themselves stay out of
#: source; the count lets operators confirm the set is intact).
BANNED_DIGEST_COUNT: int = len(_BANNED_DIGESTS)

#: Maximal lowercase letter runs. Underscores, digits, punctuation, and
#: whitespace all count as separators, so a hostile token cannot hide
#: behind ``_`` or ``2`` — while clinical words stay clean.
_TOKEN_RE = re.compile(r"[a-z]+")


def _is_banned(text: str) -> bool:
    """True if any normalized token of ``text`` hash-matches the denylist."""
    lowered = text.lower()
    return any(
        hashlib.sha256(tok.encode("utf-8")).hexdigest() in _BANNED_DIGESTS
        for tok in _TOKEN_RE.findall(lowered)
    )


#: Stamped on every rendering from this module.
PAPER_STAMP = "PAPER ONLY — SIMULATED"
#: Stamped on every advisory rendering from this module.
ADVISORY_FOOTER = (
    "🦍 PAPER ONLY — SIMULATED — not financial advice 🦍\n"
    "Confidence is heuristic agreement between LEVI's signal rules, "
    "not a probability. Paper P&L is not real money."
)


class SlurDetected(ValueError):
    """Raised when ``assert_clean`` finds a denylisted token."""


def assert_clean(text: object) -> str:
    """Screen ``text`` against the slur denylist.

    Returns the text unchanged when clean; raises :class:`SlurDetected`
    otherwise. The offending token is deliberately *not* echoed back in
    the error: LEVI output carries no denylisted terms, ever. Every
    public renderer calls this on its final output so a hostile input
    (e.g. a trader name) can never smuggle a slur into rendered output.
    """
    if not isinstance(text, str):
        raise SlurDetected(f"expected text, got {type(text).__name__}")
    if _is_banned(text):
        raise SlurDetected("blocked term detected: WSB mode uses clean slang only.")
    return text


def _money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def dd_post(signal) -> str:
    """Render an advisory ``Signal`` as a WSB-style DD post.

    Takes ``levi.finance.signals.Signal`` (duck-typed: ``symbol``,
    ``direction``, ``confidence``, ``rationale``, ``indicator_snapshot``)
    and renders it verbatim — the skin never alters the numbers.
    """
    direction = str(getattr(signal, "direction", "neutral"))
    symbol = str(getattr(signal, "symbol", "?")).upper()
    try:
        confidence = float(getattr(signal, "confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    rationale = list(getattr(signal, "rationale", []) or [])
    snapshot = dict(getattr(signal, "indicator_snapshot", {}) or {})

    if direction == "bullish":
        call = "BULLISH 🚀 — APES TOGETHER STRONG"
        play = (
            f"LEVI's signal engine scores {symbol} BULLISH. "
            "The rules agree with each other — that is all this means."
        )
    elif direction == "bearish":
        call = "BEARISH 🐻 — PAPER HANDS INCOMING?"
        play = (
            f"LEVI's signal engine scores {symbol} BEARISH. "
            "Diamond hands are a choice, not a strategy."
        )
    else:
        call = "NEUTRAL 🦧 — HOLDING BANANAS"
        play = (
            f"LEVI's signal engine scores {symbol} NEUTRAL. "
            "Sometimes the play is no play."
        )

    lines = [
        f"🚀🚀 DD: {symbol} — {call} 🚀🚀",
        f"   ({PAPER_STAMP} — not financial advice)",
        "",
        "THE PLAY",
        f"  {play}",
        "",
        "HEURISTIC AGREEMENT (not a probability)",
        f"  {confidence:.0%} of LEVI's signal rules point {direction}.",
        "",
        "THE NUMBERS",
    ]
    for key, value in list(snapshot.items())[:8]:
        lines.append(f"  • {key}: {value}")
    if rationale:
        lines.append("")
        lines.append("WHY APES CARE")
        for line in rationale[:6]:
            lines.append(f"  • {line}")
    lines += [
        "",
        "DIAMOND HANDS CHECK",
        "  This DD is paper. If it were real money, position size like",
        "  you could lose it all — because in the market, you can.",
        "",
        ADVISORY_FOOTER,
    ]
    return assert_clean("\n".join(lines))


def positions_or_ban(summary: dict) -> str:
    """Render a portfolio summary dict as "POSITIONS OR BAN".

    ``summary`` is the dict from ``Portfolio.summary(prices)``.
    """
    positions = summary.get("positions", {}) or {}
    lines = [
        "💎🙌 POSITIONS OR BAN — PAPER LEDGER 💎🙌",
        f"   ({PAPER_STAMP} — no real money)",
        "",
    ]
    shown = False
    for symbol, pos in positions.items():
        qty = float(pos.get("qty", 0) or 0)
        if qty <= 0:
            continue
        shown = True
        line = f"  {symbol}: {qty:g} @ avg ${pos.get('avg_cost', 0):,.2f}"
        if "unrealized_pnl" in pos:
            upl = float(pos["unrealized_pnl"] or 0)
            tag = "💎" if upl >= 0 else "💀"
            line += f"  unrealized {_money(upl)} {tag}"
        lines.append(assert_clean(line))
    if not shown:
        lines.append("  (no open positions — apes have left the building)")
    lines += [
        "",
        f"  realized P&L:   {_money(float(summary.get('realized_pnl', 0) or 0))}",
        f"  unrealized P&L: {_money(float(summary.get('unrealized_pnl', 0) or 0))}",
        f"  market value:   ${float(summary.get('market_value', 0) or 0):,.2f}",
        f"  total P&L:      {_money(float(summary.get('total_pnl', 0) or 0))}",
        "",
        ADVISORY_FOOTER,
    ]
    return assert_clean("\n".join(lines))


def gain_loss_porn(summary: dict) -> str:
    """Render the portfolio's total P&L as gain/loss porn."""
    total = float(summary.get("total_pnl", 0) or 0)
    if total > 0:
        banner = "🚀🚀🚀 GAIN PORN — TENDIES SECURED 🚀🚀🚀"
        flavor = "Apes together strong. Don't forget what green feels like."
    elif total < 0:
        banner = "💀💀💀 LOSS PORN — BANANA PEEL 💀💀💀"
        flavor = "It's paper. Breathe. The market humbles everyone eventually."
    else:
        banner = "🦧 FLAT — CRAB MARKET ENERGY 🦧"
        flavor = "Sideways is a direction too. Barely."
    return assert_clean(
        "\n".join(
            [
                banner,
                f"  total P&L: {_money(total)} ({PAPER_STAMP})",
                f"  {flavor}",
                "",
                ADVISORY_FOOTER,
            ]
        )
    )


def hands_report(hands: dict) -> str:
    """Render diamond-hands vs paper-hands stats, WSB-flavored.

    ``hands`` is the dict from ``BetLedger.hands_stats()``: per-cohort
    ``bets``/``wins``/``win_rate``/``total_pnl``. The skin reports the
    cohorts verbatim and names a winner only on settled paper P&L —
    holding longer is not automatically better, and the report says so.
    """
    diamond = dict(hands.get("diamond_hands", {}) or {})
    paper = dict(hands.get("paper_hands", {}) or {})

    def _row(label: str, emoji: str, cohort: dict) -> str:
        n = int(cohort.get("bets", 0) or 0)
        wr = cohort.get("win_rate")
        wr_text = f"{wr:.0%}" if wr is not None else "n/a"
        return (
            f"  {emoji} {label:<13} {n:>3} bets   win {wr_text:>4}   "
            f"P&L {_money(float(cohort.get('total_pnl', 0) or 0))}"
        )

    d_pnl = float(diamond.get("total_pnl", 0) or 0)
    p_pnl = float(paper.get("total_pnl", 0) or 0)
    d_n = int(diamond.get("bets", 0) or 0)
    p_n = int(paper.get("bets", 0) or 0)
    if d_n and p_n:
        if d_pnl > p_pnl:
            verdict = (
                "💎 DIAMOND HANDS WIN THIS ROUND — holding paid (this time, on paper)"
            )
        elif p_pnl > d_pnl:
            verdict = "🧻 PAPER HANDS WIN THIS ROUND — exiting early paid (this time, on paper)"
        else:
            verdict = "🦧 DEAD HEAT — hands made no difference (this time, on paper)"
    elif d_n:
        verdict = "💎 only diamond-hands exits so far — no paper cohort to compare"
    elif p_n:
        verdict = "🧻 only paper-hands exits so far — no diamond cohort to compare"
    else:
        verdict = "🦧 no settled bets yet — settle some paper to grow hands"

    return assert_clean(
        "\n".join(
            [
                "💎🙌 DIAMOND HANDS vs PAPER HANDS 🧻🙌",
                f"   ({PAPER_STAMP} — settled paper bets only)",
                "",
                _row("diamond", "💎", diamond),
                _row("paper", "🧻", paper),
                "",
                f"  verdict: {verdict}",
                "  note: diamond = held to the bet's horizon; paper = exited",
                "  early. Neither is a strategy — this is a scoreboard.",
                "",
                ADVISORY_FOOTER,
            ]
        )
    )


def ticker_tape(items: list[tuple[str, float, float | None]]) -> str:
    """Render a meme ticker tape.

    ``items``: ``(symbol, price, day_change_pct_or_None)``.
    """
    parts = []
    for symbol, price, chg in items:
        token = f"{str(symbol).upper()} ${float(price):,.2f}"
        if chg is not None:
            arrow = "🚀" if chg >= 0 else "🔻"
            token += f" ({chg:+.1f}%) {arrow}"
        parts.append(token)
    body = "  •  ".join(parts) if parts else "(no quotes — the tape is empty)"
    return assert_clean(f"📈 MEME TAPE — {body}  [{PAPER_STAMP}]")


def wsb_quote(symbol: str, price: float, as_of: str, source: str) -> str:
    """Render a single quote, WSB-flavored."""
    return assert_clean(
        "\n".join(
            [
                f"🦍 {str(symbol).upper()}  ${float(price):,.2f}  (as of {as_of})",
                f"   source: {source}  [{PAPER_STAMP} — not financial advice]",
            ]
        )
    )
