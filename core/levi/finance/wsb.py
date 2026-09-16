"""WSB presentation skin for the LEVI finance domain.

Renders signals, portfolios, and quotes with WallStreetBets energy —
DD posts, "positions or ban", gain/loss porn, diamond-hands lore —
while LEVI's own signal engine does the analysis underneath.

Binding rules for this module:

* CLEAN SLANG ONLY. ``BANNED_TOKENS`` is a hard denylist; every public
  renderer runs ``assert_clean`` over its output, and trader names are
  screened at bet placement. A slur is never rendered, whatever the
  input.
* HONESTY. Confidence is always presented as *heuristic agreement*,
  never as a probability. Every renderer stamps its output
  ``PAPER ONLY — SIMULATED`` and advisory output carries
  ``not financial advice``. The skin changes the voice, never the
  numbers: it renders ``Signal``/ledger data verbatim.
* PAPER ONLY. Nothing here can place, route, or suggest a real order.

Stdlib-only: ``re``.
"""

from __future__ import annotations

import re

__all__ = [
    "BANNED_TOKENS",
    "SlurDetected",
    "assert_clean",
    "dd_post",
    "positions_or_ban",
    "gain_loss_porn",
    "ticker_tape",
    "wsb_quote",
    "ADVISORY_FOOTER",
    "PAPER_STAMP",
]

#: Hard denylist — WSB-flavored slurs and general hate terms. Matched on
#: word boundaries, case-insensitive. This list is about refusal, not
#: vocabulary: these tokens never appear in LEVI output, ever.
BANNED_TOKENS: tuple[str, ...] = (
    "retard",
    "retards",
    "retarded",
    "autist",
    "autists",
    "faggot",
    "faggots",
    "nigger",
    "niggers",
    "chink",
    "chinks",
    "kike",
    "kikes",
    "spic",
    "spics",
    "tranny",
    "trannies",
    "dyke",
    "dykes",
)

_BANNED_RE = re.compile(
    # Letter-adjacency lookarounds (not \b): underscores and digits count
    # as separators, so "retard_ape" and "x-retard-2" are still caught
    # while "autistic" (clinical term) is not.
    r"(?<![A-Za-z])("
    + "|".join(re.escape(tok) for tok in BANNED_TOKENS)
    + r")(?![A-Za-z])",
    re.IGNORECASE,
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
    naming the offending token otherwise. Every public renderer calls
    this on its final output so a hostile input (e.g. a trader name)
    can never smuggle a slur into rendered output.
    """
    if not isinstance(text, str):
        raise SlurDetected(f"expected text, got {type(text).__name__}")
    hit = _BANNED_RE.search(text)
    if hit:
        raise SlurDetected(
            f"blocked term {hit.group(0)!r}: WSB mode uses clean slang only."
        )
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
