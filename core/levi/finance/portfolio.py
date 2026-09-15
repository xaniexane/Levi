"""Portfolio ledger for LEVI's finance domain — paper trading only.

Tracks cash and per-symbol positions with fill accounting, realized and
unrealized P&L, and JSON persistence. There is no broker wiring here and
no path to live trading; this module is a ledger, not an order router.

Stdlib-only (dataclasses, json, pathlib, datetime). No pandas/numpy.

Design notes:
- Cash starts at 0.0. It only grows via ``deposit()`` — there is no fake
  starting balance.
- Positions are never negative. Selling more than held raises
  ``ValueError`` before anything is mutated.
- Sells realize P&L against the position's average cost (FIFO-simple).
- Valuations that lack a price never silently use 0: unknown symbols are
  valued at their average cost and reported in a ``warnings`` list.
- Full precision is kept internally; every outward-facing number is
  rounded to 2 decimals.
"""

from __future__ import annotations

import json
import math
import warnings
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: Default persistence location for the portfolio ledger.
DEFAULT_PATH: Path = Path.home() / ".levi" / "finance" / "portfolio.json"

_FINANCE_DIR_MODE = 0o700


def _r2(value: float) -> float:
    """Round to 2 decimals, normalizing -0.0 to 0.0 for clean output."""
    return round(value + 0.0, 2)


def _require_number(name: str, value: object) -> float:
    """Coerce to float, rejecting bools, non-numerics and non-finite."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return result


def _require_positive(name: str, value: object) -> float:
    result = _require_number(name, value)
    if result <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return result


def _require_prices(prices: object) -> dict[str, float]:
    """Validate a symbol->price map: every key a string, every price finite."""
    if not isinstance(prices, Mapping):
        raise ValueError(
            f"prices must be a mapping of symbol to price, got {type(prices).__name__}"
        )
    clean: dict[str, float] = {}
    for symbol, price in prices.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"price map has an invalid symbol key: {symbol!r}")
        clean[symbol] = _require_number(f"price for {symbol!r}", price)
    return clean


@dataclass
class Position:
    """One held (or previously held) symbol."""

    symbol: str
    qty: float
    avg_cost: float
    realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError(
                f"position symbol must be a non-empty string, got {self.symbol!r}"
            )
        self.qty = _require_number("position qty", self.qty)
        self.avg_cost = _require_number("position avg_cost", self.avg_cost)
        self.realized_pnl = _require_number("position realized_pnl", self.realized_pnl)
        if self.qty < 0:
            raise ValueError(f"position qty is never negative, got {self.qty!r}")
        if self.avg_cost < 0:
            raise ValueError(
                f"position avg_cost is never negative, got {self.avg_cost!r}"
            )

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("qty", "avg_cost", "realized_pnl"):
            data[key] = _r2(data[key])
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(
            symbol=data["symbol"],
            qty=float(data["qty"]),
            avg_cost=float(data["avg_cost"]),
            realized_pnl=float(data.get("realized_pnl", 0.0)),
        )


@dataclass
class Portfolio:
    """Cash + position ledger. All accounting happens via fills."""

    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = _require_number("portfolio cash", self.cash)
        if not isinstance(self.positions, dict):
            raise ValueError(
                f"positions must be a dict, got {type(self.positions).__name__}"
            )
        for symbol, pos in self.positions.items():
            if not isinstance(pos, Position):
                raise ValueError(
                    f"positions[{symbol!r}] must be a Position, "
                    f"got {type(pos).__name__}"
                )

    # -- funding ---------------------------------------------------------

    def deposit(self, amount: float) -> None:
        """Add cash to the portfolio. ``amount`` must be positive."""
        amount = _require_positive("deposit amount", amount)
        self.cash += amount

    # -- fills -----------------------------------------------------------

    def apply_fill(self, symbol: str, side: str, qty: float, price: float) -> None:
        """Apply a buy or sell fill.

        Buy: cash decreases, average cost is the quantity-weighted blend.
        Sell: quantity must not exceed what is held (else ``ValueError``
        and nothing is mutated); realized P&L is booked against average
        cost, cash increases by the proceeds.
        """
        if side not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"symbol must be a non-empty string, got {symbol!r}")
        qty = _require_positive("qty", qty)
        price = _require_positive("price", price)

        if side == "buy":
            self.cash -= qty * price
            pos = self.positions.get(symbol)
            if pos is None:
                self.positions[symbol] = Position(
                    symbol=symbol, qty=qty, avg_cost=price
                )
            else:
                total_cost = pos.qty * pos.avg_cost + qty * price
                pos.qty += qty
                pos.avg_cost = total_cost / pos.qty
            return

        # sell — validate before mutating anything
        pos = self.positions.get(symbol)
        if pos is None:
            raise ValueError(f"cannot sell {symbol}: no position held")
        if qty > pos.qty:
            raise ValueError(
                f"cannot sell {qty} {symbol}: only {pos.qty} held "
                "(positions are never negative)"
            )
        self.cash += qty * price
        pos.realized_pnl += qty * (price - pos.avg_cost)
        pos.qty -= qty
        # Flat positions stay in the dict (qty 0) so their realized P&L
        # survives in summaries; they contribute nothing to valuations.

    # -- valuation -------------------------------------------------------

    def _price_for(
        self, symbol: str, prices: dict[str, float], warnings: list[str]
    ) -> float:
        price = prices.get(symbol)
        if price is None:
            warnings.append(symbol)
            return self.positions[symbol].avg_cost
        return price

    def market_value(self, prices: dict[str, float]) -> tuple[float, list[str]]:
        """Cash + sum(qty * price). Returns ``(value, warnings)``.

        Symbols missing from ``prices`` are valued at their average cost
        and listed in ``warnings`` — never silently priced at 0.
        """
        prices = _require_prices(prices)
        warnings: list[str] = []
        total = self.cash
        for symbol, pos in self.positions.items():
            total += pos.qty * self._price_for(symbol, prices, warnings)
        return _r2(total), warnings

    def unrealized_pnl(
        self, prices: dict[str, float]
    ) -> tuple[dict[str, float], float]:
        """Per-position unrealized P&L and its total.

        Symbols missing from ``prices`` are valued at average cost, so
        their unrealized P&L is 0 rather than silently mis-priced.
        """
        prices = _require_prices(prices)
        warnings: list[str] = []
        per: dict[str, float] = {}
        for symbol, pos in self.positions.items():
            price = self._price_for(symbol, prices, warnings)
            per[symbol] = _r2(pos.qty * (price - pos.avg_cost))
        return per, _r2(sum(per.values()))

    def realized_pnl_total(self) -> float:
        """Sum of realized P&L across all positions (incl. flat ones)."""
        return _r2(sum(pos.realized_pnl for pos in self.positions.values()))

    # -- snapshot --------------------------------------------------------

    def summary(self, prices: dict[str, float] | None = None) -> dict:
        """JSON-serializable snapshot of the portfolio.

        With ``prices`` given, includes market value and unrealized P&L
        (plus any missing-price warnings); without, only cash, positions
        and realized P&L.
        """
        positions_out: dict[str, dict] = {}
        for symbol, pos in self.positions.items():
            positions_out[symbol] = pos.to_dict()

        out: dict = {
            "cash": _r2(self.cash),
            "positions": positions_out,
            "realized_pnl": self.realized_pnl_total(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if prices is not None:
            value, warnings = self.market_value(prices)
            per, total = self.unrealized_pnl(prices)
            for symbol in per:
                positions_out[symbol]["unrealized_pnl"] = per[symbol]
            out["market_value"] = value
            out["unrealized_pnl"] = total
            out["total_pnl"] = _r2(self.realized_pnl_total() + total)
            out["warnings"] = warnings
        return out

    # -- persistence -----------------------------------------------------

    def save(self, path: Path = DEFAULT_PATH) -> Path:
        """Write the ledger as JSON, creating parent dirs (mode 0o700)."""
        path = Path(path)
        finance_dir = path.parent
        finance_dir.mkdir(parents=True, exist_ok=True)
        finance_dir.chmod(_FINANCE_DIR_MODE)
        payload = {
            "cash": self.cash,
            "positions": {
                symbol: {
                    "symbol": pos.symbol,
                    "qty": pos.qty,
                    "avg_cost": pos.avg_cost,
                    "realized_pnl": pos.realized_pnl,
                }
                for symbol, pos in self.positions.items()
            },
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "Portfolio":
        """Load the ledger.

        A missing file yields an empty portfolio. A corrupt file yields
        an empty portfolio *with a loud warning* — never a traceback and
        never half-parsed accounting data.
        """
        path = Path(path)
        if not path.exists():
            return cls(cash=0.0)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top level must be an object")
            cash = _require_number("cash", data.get("cash", 0.0))
            raw_positions = data.get("positions", {})
            if not isinstance(raw_positions, dict):
                raise ValueError("'positions' must be an object")
            positions = {}
            for symbol, pdata in raw_positions.items():
                if not isinstance(symbol, str) or not isinstance(pdata, dict):
                    raise ValueError(f"invalid position entry for {symbol!r}")
                positions[symbol] = Position.from_dict(pdata)
            return cls(cash=cash, positions=positions)
        except Exception as exc:
            warnings.warn(
                f"portfolio file {path} is unreadable "
                f"({type(exc).__name__}); starting with an empty ledger. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=2,
            )
            return cls(cash=0.0)


def load(path: Path = DEFAULT_PATH) -> Portfolio:
    """Module-level convenience alias for ``Portfolio.load``."""
    return Portfolio.load(path)
