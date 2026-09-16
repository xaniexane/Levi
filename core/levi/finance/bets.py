"""Paper YOLO bets for the LEVI finance domain.

A *paper bet* is a simulated directional wager: trader, symbol, side,
quantity, entry price, and a horizon in days. Bets are stored locally,
settled against caller-supplied exit prices (never invented), and scored
for win rate plus diamond-hands vs paper-hands stats.

Paper only, always: a bet moves no money, touches no broker, and every
ticket is stamped SIMULATED. Trader names are screened through the WSB
slur guard — a hostile name can never reach rendered output.

Stdlib-only: ``dataclasses``, ``json``, ``math``, ``pathlib``,
``datetime``, ``uuid``, ``warnings``.
"""

from __future__ import annotations

import json
import math
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from levi.finance.wsb import assert_clean

__all__ = [
    "Bet",
    "BetLedger",
    "DEFAULT_BETS_PATH",
    "InvalidBet",
    "BetNotFound",
    "BetAlreadySettled",
    "load",
]

#: Default persistence location for the paper-bet ledger.
DEFAULT_BETS_PATH: Path = Path.home() / ".levi" / "finance" / "bets.json"

_FINANCE_DIR_MODE = 0o700
_SOURCES = ("stooq", "binance", "synth")


class InvalidBet(ValueError):
    """Raised when a bet fails validation. Nothing was recorded."""


class BetNotFound(KeyError):
    """Raised when a bet id is unknown to the ledger."""


class BetAlreadySettled(ValueError):
    """Raised when settling a bet that is already settled."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _r2(value: float) -> float:
    return round(value + 0.0, 2)


def _require_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidBet(f"{name} must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise InvalidBet(f"{name} must be finite, got {value!r}")
    return result


def _require_positive(name: str, value: object) -> float:
    result = _require_number(name, value)
    if result <= 0:
        raise InvalidBet(f"{name} must be positive, got {value!r}")
    return result


def _clean_trader(trader: object) -> str:
    if not isinstance(trader, str) or not trader.strip():
        raise InvalidBet(f"trader must be a non-empty name, got {trader!r}")
    name = trader.strip()
    if len(name) > 32:
        raise InvalidBet(f"trader name too long (max 32 chars), got {name!r}")
    try:
        assert_clean(name)
    except Exception as exc:
        raise InvalidBet(f"trader name rejected: {exc}") from None
    return name


@dataclass
class Bet:
    """One paper bet. Construction validates; an invalid bet can never
    exist, let alone be "settled"."""

    id: str
    trader: str
    symbol: str
    side: str  # "buy" | "sell"
    qty: float
    entry_price: float
    placed_at: str = field(default_factory=_now_iso)
    horizon_days: int = 30
    source: str = "stooq"
    status: str = "open"
    exit_price: float | None = None
    exit_at: str | None = None
    early_exit: bool = False
    pnl: float | None = None
    #: Where the exit price came from: "manual" (caller-supplied), or a
    #: market-data source name ("stooq", "binance", "synth") when the bet
    #: was settled at the provider's latest close. Provenance for the
    #: settlement — the price is never invented, and the ticket says so.
    exit_price_source: str | None = None

    def __post_init__(self) -> None:
        self.trader = _clean_trader(self.trader)
        symbol = str(self.symbol or "").strip().upper()
        if not symbol:
            raise InvalidBet("symbol must be a non-empty string")
        self.symbol = symbol
        side = str(self.side or "").strip().lower()
        if side not in ("buy", "sell"):
            raise InvalidBet(f"side must be 'buy' or 'sell', got {self.side!r}")
        self.side = side
        self.qty = _require_positive("qty", self.qty)
        self.entry_price = _require_positive("entry_price", self.entry_price)
        if isinstance(self.horizon_days, bool) or not isinstance(
            self.horizon_days, int
        ):
            raise InvalidBet(
                f"horizon_days must be an int >= 1, got {self.horizon_days!r}"
            )
        if self.horizon_days < 1:
            raise InvalidBet(f"horizon_days must be >= 1, got {self.horizon_days!r}")
        if self.source not in _SOURCES:
            raise InvalidBet(f"source must be one of {_SOURCES}, got {self.source!r}")
        if self.status not in ("open", "settled"):
            raise InvalidBet(f"status must be 'open' or 'settled', got {self.status!r}")
        if self.exit_price is not None:
            self.exit_price = _require_positive("exit_price", self.exit_price)
        if self.pnl is not None:
            self.pnl = _require_number("pnl", self.pnl)
        if self.exit_price_source is not None:
            source = str(self.exit_price_source).strip().lower()
            if source not in _SOURCES and source != "manual":
                raise InvalidBet(
                    f"exit_price_source must be one of {(*_SOURCES, 'manual')}, "
                    f"got {self.exit_price_source!r}"
                )
            self.exit_price_source = source

    def signed_pnl(self, exit_price: float) -> float:
        """Simulated P&L at ``exit_price``: long wins when price rises."""
        px = _require_positive("exit_price", exit_price)
        sign = 1.0 if self.side == "buy" else -1.0
        return _r2(sign * (px - self.entry_price) * self.qty)

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("qty", "entry_price", "exit_price", "pnl"):
            if data[key] is not None:
                data[key] = _r2(float(data[key]))
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Bet":
        return cls(
            id=str(data["id"]),
            trader=data["trader"],
            symbol=data["symbol"],
            side=data["side"],
            qty=float(data["qty"]),
            entry_price=float(data["entry_price"]),
            placed_at=str(data.get("placed_at", _now_iso())),
            horizon_days=int(data.get("horizon_days", 30)),
            source=str(data.get("source", "stooq")),
            status=str(data.get("status", "open")),
            exit_price=(
                float(data["exit_price"])
                if data.get("exit_price") is not None
                else None
            ),
            exit_at=data.get("exit_at"),
            early_exit=bool(data.get("early_exit", False)),
            pnl=float(data["pnl"]) if data.get("pnl") is not None else None,
            exit_price_source=data.get("exit_price_source"),
        )


class BetLedger:
    """Local paper-bet book. All P&L is simulated."""

    def __init__(self, bets: list[Bet] | None = None) -> None:
        self.bets: list[Bet] = list(bets or [])

    # -- placement ------------------------------------------------------

    def place(
        self,
        *,
        trader: str,
        symbol: str,
        side: str,
        qty: float,
        entry_price: float,
        horizon_days: int = 30,
        source: str = "stooq",
    ) -> Bet:
        """Record a paper bet.

        ``entry_price`` must be supplied — it comes from real market data
        (or the synthetic provider) and is never invented here.
        """
        bet = Bet(
            id=f"bet-{uuid.uuid4().hex[:8]}",
            trader=trader,
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=entry_price,
            horizon_days=horizon_days,
            source=source,
        )
        self.bets.append(bet)
        return bet

    # -- settlement -----------------------------------------------------

    def get(self, bet_id: str) -> Bet:
        for bet in self.bets:
            if bet.id == bet_id:
                return bet
        raise BetNotFound(f"unknown bet id {bet_id!r} — nothing was settled.")

    def settle(
        self,
        bet_id: str,
        exit_price: float,
        *,
        early: bool = False,
        exit_price_source: str = "manual",
    ) -> Bet:
        """Settle an open bet at ``exit_price``.

        ``exit_price`` must be supplied (from market data, never
        invented). ``early=True`` marks a paper-hands exit — the bet was
        closed before its horizon played out. ``exit_price_source`` records
        where the price came from (``"manual"`` or a provider name like
        ``"stooq"``/``"binance"``/``"synth"``) so the ticket can show
        provenance.
        """
        bet = self.get(bet_id)
        if bet.status != "open":
            raise BetAlreadySettled(
                f"bet {bet_id} is already settled — nothing was changed."
            )
        pnl = bet.signed_pnl(exit_price)
        bet.exit_price = _require_positive("exit_price", exit_price)
        bet.exit_at = _now_iso()
        bet.early_exit = bool(early)
        bet.pnl = pnl
        bet.status = "settled"
        source = str(exit_price_source or "manual").strip().lower()
        if source not in _SOURCES and source != "manual":
            raise InvalidBet(
                f"exit_price_source must be one of {(*_SOURCES, 'manual')}, "
                f"got {exit_price_source!r}"
            )
        bet.exit_price_source = source
        return bet

    def settle_preview(self, bet_id: str, exit_price: float) -> dict:
        """What-if preview: simulated P&L at ``exit_price`` without
        settling anything. The bet is untouched — this is a read-only
        look at where the bet stands."""
        bet = self.get(bet_id)
        if bet.status != "open":
            raise BetAlreadySettled(
                f"bet {bet_id} is already settled — preview is for open bets."
            )
        pnl = bet.signed_pnl(exit_price)
        return {
            "bet_id": bet.id,
            "trader": bet.trader,
            "symbol": bet.symbol,
            "side": bet.side,
            "entry_price": bet.entry_price,
            "exit_price": _require_positive("exit_price", exit_price),
            "pnl": pnl,
            "status": "preview — nothing was settled (paper only)",
        }

    # -- queries --------------------------------------------------------

    def open_bets(self, trader: str | None = None) -> list[Bet]:
        return [
            b
            for b in self.bets
            if b.status == "open" and (trader is None or b.trader == trader)
        ]

    def settled_bets(self, trader: str | None = None) -> list[Bet]:
        return [
            b
            for b in self.bets
            if b.status == "settled" and (trader is None or b.trader == trader)
        ]

    def traders(self) -> list[str]:
        return sorted({b.trader for b in self.bets})

    # -- scoring --------------------------------------------------------

    @staticmethod
    def _score(bets: list[Bet]) -> dict:
        wins = sum(1 for b in bets if (b.pnl or 0) > 0)
        n = len(bets)
        return {
            "bets": n,
            "wins": wins,
            "losses": n - wins,
            "win_rate": round(wins / n, 4) if n else None,
            "total_pnl": _r2(sum(b.pnl or 0 for b in bets)),
        }

    def win_rate(self, trader: str | None = None) -> dict:
        """Win-rate over settled bets, optionally for one trader."""
        return self._score(self.settled_bets(trader))

    def hands_stats(self) -> dict:
        """Diamond-hands vs paper-hands: held to plan vs exited early."""
        settled = self.settled_bets()
        diamond = [b for b in settled if not b.early_exit]
        paper = [b for b in settled if b.early_exit]
        return {
            "diamond_hands": self._score(diamond),
            "paper_hands": self._score(paper),
            "note": (
                "diamond = held to the bet's horizon; "
                "paper = exited early (--paper-hands). Paper only."
            ),
        }

    # -- rendering ------------------------------------------------------

    _TICKET_WIDTH = 43  # box border width; content lines are fitted to it

    @staticmethod
    def _ticket_line(text: str) -> str:
        """Fit ``text`` inside the ticket box: truncate with an ellipsis
        marker when a long trader name or symbol would break the border."""
        inner = BetLedger._TICKET_WIDTH - 4  # "│  " … " │"
        text = str(text)
        if len(text) > inner:
            text = text[: inner - 1] + "…"
        return f"│  {text:<{inner}}│"

    @staticmethod
    def ticket(bet: Bet) -> str:
        """ASCII ticket for a paper bet — always stamped SIMULATED."""
        side_word = "LONG 📈" if bet.side == "buy" else "SHORT 📉"
        line = BetLedger._ticket_line
        border = "┌" + "─" * (BetLedger._TICKET_WIDTH - 2) + "┐"
        mid = "├" + "─" * (BetLedger._TICKET_WIDTH - 2) + "┤"
        bottom = "└" + "─" * (BetLedger._TICKET_WIDTH - 2) + "┘"
        lines = [
            border,
            line("🎰 PAPER YOLO TICKET (SIMULATED)"),
            mid,
            line(f"{bet.id}  trader: {bet.trader}"),
            line(f"{side_word}  {bet.qty:g} {bet.symbol} @ ${bet.entry_price:,.2f}"),
            line(f"horizon: {bet.horizon_days}d   source: {bet.source}"),
            line(f"placed: {bet.placed_at[:10]}"),
        ]
        if bet.status == "settled":
            hands = "💎 DIAMOND" if not bet.early_exit else "🧻 PAPER"
            source = f" (via {bet.exit_price_source})" if bet.exit_price_source else ""
            lines.append(line(f"SETTLED @ ${bet.exit_price:,.2f}{source}"))
            lines.append(line(f"P&L {_signed_money(bet.pnl or 0)}  {hands}"))
        else:
            lines.append(line("status: OPEN — fortune favors the bold (paper)"))
        lines += [
            mid,
            line("not financial advice · paper only"),
            bottom,
        ]
        return assert_clean("\n".join(lines))

    # -- persistence ----------------------------------------------------

    def save(self, path: Path = DEFAULT_BETS_PATH) -> Path:
        """Write the ledger as JSON, creating parent dirs (mode 0o700)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(_FINANCE_DIR_MODE)
        payload = {
            "bets": [b.to_dict() for b in self.bets],
            "saved_at": _now_iso(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_BETS_PATH) -> "BetLedger":
        """Load the ledger.

        A missing file yields an empty ledger. A corrupt file yields an
        empty ledger *with a loud warning* — never a traceback and never
        half-parsed bet data.
        """
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top level must be an object")
            raw = data.get("bets", [])
            if not isinstance(raw, list):
                raise ValueError("'bets' must be a list")
            return cls(bets=[Bet.from_dict(item) for item in raw])
        except Exception as exc:
            warnings.warn(
                f"bet ledger {path} is unreadable "
                f"({type(exc).__name__}); starting empty. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=2,
            )
            return cls()


def _signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def load(path: Path = DEFAULT_BETS_PATH) -> BetLedger:
    """Module-level convenience alias for ``BetLedger.load``."""
    return BetLedger.load(path)
