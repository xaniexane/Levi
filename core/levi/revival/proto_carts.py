"""Commerce modules bolted onto an exchange: carts before the web.

Studied from: dead-networks-20260916/report.md (The Major BBS / Worldgroup).

The old mechanism: third-party commerce arrived as add-on modules
plugged into the host — a catalog here, a cart there, a checkout hook
from some other vendor's DLL. No platform owned the whole transaction;
the host just provided the rack the modules hung on. LEVI's
reimplementation is that rack: a catalog, a cart, an order book, and an
add-on hook row where third-party adjustments (discounts, shipping,
gift wrap) can attach without touching the core arithmetic.

Honest limits: money is integer minor units (cents) — no floats, no
rounding surprises. Checkout freezes an order record; no payment is
processed, no funds move, no tax authority is modeled (``tax_rate``
exists as a caller-supplied placeholder and defaults to 0.0 — the
module does not pretend to know your jurisdiction). Add-ons see a copy
of the order and may only add labeled adjustment lines, never rewrite
the core lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

ORIGIN = "levi-revival/proto_carts"


def fmt(minor: int, symbol: str = "$") -> str:
    """Format integer minor units for display."""
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return f"{sign}{symbol}{minor // 100}.{minor % 100:02d}"


@dataclass
class Item:
    sku: str
    name: str
    price: int  # minor units, >= 0
    stock: Optional[int] = None  # None = unlimited


@dataclass
class CartLine:
    sku: str
    name: str
    unit_price: int
    qty: int

    @property
    def line_total(self) -> int:
        return self.unit_price * self.qty


@dataclass
class Adjustment:
    """A labeled money line contributed by an add-on module."""

    label: str
    amount: int  # signed minor units; negative = discount
    addon: str


@dataclass
class Order:
    order_id: int
    lines: List[CartLine]
    adjustments: List[Adjustment] = field(default_factory=list)
    tax_rate: float = 0.0
    status: str = "placed"

    @property
    def subtotal(self) -> int:
        return sum(line.line_total for line in self.lines)

    @property
    def adjustments_total(self) -> int:
        return sum(a.amount for a in self.adjustments)

    @property
    def taxable(self) -> int:
        return max(0, self.subtotal + self.adjustments_total)

    @property
    def tax(self) -> int:
        # Caller-supplied placeholder rate; the module models no tax law.
        return int(self.taxable * self.tax_rate)

    @property
    def total(self) -> int:
        return self.taxable + self.tax


class Catalog:
    """The vendor's item list."""

    def __init__(self) -> None:
        self.items: Dict[str, Item] = {}

    def add_item(
        self, sku: str, name: str, price: int, stock: Optional[int] = None
    ) -> Item:
        sku = sku.strip()
        if not sku or sku in self.items:
            raise ValueError(f"bad or duplicate sku {sku!r}")
        if price < 0:
            raise ValueError("price must be >= 0")
        if stock is not None and stock < 0:
            raise ValueError("stock must be >= 0")
        item = Item(sku=sku, name=name.strip(), price=price, stock=stock)
        self.items[sku] = item
        return item

    def get(self, sku: str) -> Item:
        try:
            return self.items[sku]
        except KeyError:
            raise ValueError(f"no item {sku!r}") from None

    def search(self, text: str) -> List[Item]:
        needle = text.strip().lower()
        if not needle:
            return []
        return [
            i
            for i in self.items.values()
            if needle in i.name.lower() or needle in i.sku.lower()
        ]


class Cart:
    """The shopper's basket: holds lines, checks stock, freezes orders."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.lines: Dict[str, CartLine] = {}

    def add(self, sku: str, qty: int = 1) -> CartLine:
        if qty <= 0:
            raise ValueError("qty must be >= 1")
        item = self.catalog.get(sku)
        line = self.lines.get(sku)
        have = line.qty if line else 0
        if item.stock is not None and have + qty > item.stock:
            raise ValueError(f"only {item.stock} of {sku} in stock")
        if line is None:
            line = CartLine(sku=item.sku, name=item.name, unit_price=item.price, qty=0)
            self.lines[sku] = line
        line.qty += qty
        return line

    def set_qty(self, sku: str, qty: int) -> None:
        if qty < 0:
            raise ValueError("qty must be >= 0")
        if sku not in self.lines:
            raise ValueError(f"{sku} not in cart")
        item = self.catalog.get(sku)
        if item.stock is not None and qty > item.stock:
            raise ValueError(f"only {item.stock} of {sku} in stock")
        if qty == 0:
            del self.lines[sku]
        else:
            self.lines[sku].qty = qty

    def remove(self, sku: str) -> None:
        if sku not in self.lines:
            raise ValueError(f"{sku} not in cart")
        del self.lines[sku]

    @property
    def subtotal(self) -> int:
        return sum(line.line_total for line in self.lines.values())

    @property
    def count(self) -> int:
        return sum(line.qty for line in self.lines.values())

    def checkout(self, tax_rate: float = 0.0) -> Order:
        """Freeze the cart into an order and decrement catalog stock.
        The cart is emptied; the order is a record, not a payment."""
        if not self.lines:
            raise ValueError("cart is empty")
        if tax_rate < 0:
            raise ValueError("tax_rate must be >= 0")
        lines = [
            CartLine(line.sku, line.name, line.unit_price, line.qty)
            for line in self.lines.values()
        ]
        for line in lines:
            item = self.catalog.get(line.sku)
            if item.stock is not None:
                item.stock -= line.qty
        order = Order(order_id=0, lines=lines, tax_rate=tax_rate)
        self.lines.clear()
        return order


# Add-ons receive a read-only-ish view and return adjustment lines.
Addon = Callable[[Dict[str, object]], List[Adjustment]]


class AddonRack:
    """The host's module row: third-party commerce add-ons mount here
    and are offered each order. Mount order is call order."""

    def __init__(self) -> None:
        self.addons: Dict[str, Addon] = {}

    def mount(self, name: str, addon: Addon) -> None:
        if not name.strip() or name in self.addons:
            raise ValueError(f"bad or duplicate addon {name!r}")
        if not callable(addon):
            raise ValueError("addon must be callable")
        self.addons[name.strip()] = addon

    def unmount(self, name: str) -> None:
        if name not in self.addons:
            raise ValueError(f"no addon {name!r}")
        del self.addons[name]

    def run(self, order: Order) -> List[Adjustment]:
        """Offer the order to every mounted add-on. Each add-on gets a
        plain-data snapshot; returned adjustments are labeled with the
        add-on's name and appended to the order."""
        snapshot = {
            "order_id": order.order_id,
            "lines": [
                {
                    "sku": line.sku,
                    "name": line.name,
                    "unit_price": line.unit_price,
                    "qty": line.qty,
                }
                for line in order.lines
            ],
            "subtotal": order.subtotal,
        }
        collected: List[Adjustment] = []
        for name, addon in self.addons.items():
            for adj in addon(dict(snapshot)):
                collected.append(
                    Adjustment(label=adj.label, amount=adj.amount, addon=name)
                )
        order.adjustments.extend(collected)
        return collected


class OrderBook:
    """Placed orders, numbered in the order they arrive."""

    def __init__(self, rack: Optional[AddonRack] = None) -> None:
        self.rack = rack or AddonRack()
        self.orders: Dict[int, Order] = {}
        self._next_id = 0

    def place(self, order: Order) -> Order:
        self._next_id += 1
        order.order_id = self._next_id
        self.rack.run(order)
        self.orders[order.order_id] = order
        return order

    def get(self, order_id: int) -> Order:
        try:
            return self.orders[order_id]
        except KeyError:
            raise ValueError(f"no order {order_id}") from None

    def book_status(self) -> Dict[str, object]:
        return {
            "orders": len(self.orders),
            "gross": sum(o.total for o in self.orders.values()),
            "addons": list(self.rack.addons),
        }
