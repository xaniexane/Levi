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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: Default persistence location for the portfolio ledger.
DEFAULT_PATH: Path = Path.home() / ".levi" / "finance" / "portfolio.json"

_FINANCE_DIR_MODE = 0o700


def _r2(value: float) -> float:
    """Round to 2 decimals, normalizing -0.0 to 0.0 for clean output."""
    return round(value + 0.0, 2)


@dataclass
class Position:
    """One held (or previously held) symbol."""

    symbol: str
    qty: float
    avg_cost: float
    realized_pnl: float = 0.0

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

    # -- funding ---------------------------------------------------------

    def deposit(self, amount: float) -> None:
        """Add cash to the portfolio. ``amount`` must be positive."""
        if amount <= 0:
            raise ValueError(f"deposit amount must be positive, got {amount!r}")
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
        if qty <= 0:
            raise ValueError(f"qty must be positive, got {qty!r}")
        if price <= 0:
            raise ValueError(f"price must be positive, got {price!r}")

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
        """Load the ledger; a missing file yields an empty portfolio."""
        path = Path(path)
        if not path.exists():
            return cls(cash=0.0)
        data = json.loads(path.read_text())
        positions = {
            symbol: Position.from_dict(pdata)
            for symbol, pdata in data.get("positions", {}).items()
        }
        return cls(cash=float(data.get("cash", 0.0)), positions=positions)


def load(path: Path = DEFAULT_PATH) -> Portfolio:
    """Module-level convenience alias for ``Portfolio.load``."""
    return Portfolio.load(path)
