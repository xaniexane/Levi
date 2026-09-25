"""SupraStreet commerce engine: products, royalty splits, paper settlements.

Amounts are integers in the smallest currency unit (cents) — no
floats, so conservation is exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, List, Mapping


_BASIS = 10_000

#: The founder's strict cut, from the recovered original SER-18
#: SupraStreet spec (``SER18Orchestrator.tsx`` in the drive-sweep corpus):
#: "a strict 15% royalty cut allocated to the Founder wallet on every
#: settlement."
FOUNDER_CUT_BP = 1_500

#: Default recipient name for the founder's cut.
FOUNDER_WALLET = "founder"


class RoyaltyError(ValueError):
    """Any refusal: bad splits, unknown product, non-positive amounts."""


@dataclass(frozen=True)
class RoyaltyShare:
    recipient: str
    basis_points: int


@dataclass(frozen=True)
class Product:
    product_id: str
    title: str
    price: int
    # BLUE (RED-1): the registered Product is never handed out — every
    # read returns a snapshot with its own fresh ``shares`` list, so the
    # split table cannot be rewritten through a read accessor.
    shares: List[RoyaltyShare]


@dataclass(frozen=True)
class Settlement:
    sale_id: str
    product_id: str
    gross: int
    # BLUE (RED-1): payouts are sealed in a MappingProxyType at mint
    # time — the ledger entry is read-only. Any ``payouts[k] = v``
    # attempt raises TypeError instead of rewriting conservation.
    payouts: Mapping[str, int]
    at: str

    def total_distributed(self) -> int:
        return sum(self.payouts.values())


class SupraStreet:
    """Paper-only commerce: register products, record sales, settle splits."""

    def __init__(self) -> None:
        self._products: Dict[str, Product] = {}
        self._settlements: Dict[str, Settlement] = {}
        self._ledger: List[Settlement] = []  # append-only paper trail

    # -- products ------------------------------------------------------
    def register_product(self, product_id: str, title: str, price: int,
                         shares: List[RoyaltyShare]) -> Product:
        """Register a product. Splits must sum to exactly 10_000 bps."""
        if not isinstance(product_id, str) or not product_id.strip():
            raise RoyaltyError("product_id must be a non-empty string")
        if product_id in self._products:
            raise RoyaltyError(f"product already registered: {product_id!r}")
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            raise RoyaltyError("price must be a positive integer (cents)")
        if not shares:
            raise RoyaltyError("at least one royalty share required")
        seen = set()
        total = 0
        for share in shares:
            if not isinstance(share.recipient, str) or not share.recipient.strip():
                raise RoyaltyError("recipient must be a non-empty string")
            if share.recipient in seen:
                raise RoyaltyError(f"duplicate recipient: {share.recipient!r}")
            seen.add(share.recipient)
            if (not isinstance(share.basis_points, int)
                    or isinstance(share.basis_points, bool)
                    or share.basis_points <= 0):
                raise RoyaltyError("basis points must be a positive integer")
            total += share.basis_points
        if total != _BASIS:
            raise RoyaltyError(
                f"royalty splits must sum to {_BASIS} basis points, got {total}"
            )
        product = Product(product_id=product_id, title=title,
                          price=price, shares=list(shares))
        self._products[product_id] = product
        # BLUE (RED-1): return a snapshot, never the registered original —
        # mutating the returned ``shares`` cannot touch the registry.
        return Product(product_id=product_id, title=title,
                       price=price, shares=list(shares))

    def product(self, product_id: str) -> Product:
        """A snapshot copy of the registered product.

        BLUE (RED-1): the returned ``Product`` carries its own ``shares``
        list — mutating it cannot rewrite the registered split table, so
        a later sale still settles exactly the registered splits.
        """
        try:
            registered = self._products[product_id]
        except KeyError:
            raise RoyaltyError(f"unknown product: {product_id!r}") from None
        return Product(
            product_id=registered.product_id,
            title=registered.title,
            price=registered.price,
            shares=list(registered.shares),
        )

    # -- sales ---------------------------------------------------------
    @staticmethod
    def _distribute(gross: int, shares: List[RoyaltyShare]) -> Dict[str, int]:
        """Integer split; the remainder (if any) goes to the first share.

        Deterministic: recipients in registration order, so the dust
        lands in the same place every time.
        """
        payouts: Dict[str, int] = {}
        assigned = 0
        for share in shares:
            amount = (gross * share.basis_points) // _BASIS
            payouts[share.recipient] = amount
            assigned += amount
        remainder = gross - assigned
        if remainder:
            first = shares[0].recipient
            payouts[first] = payouts[first] + remainder
        return payouts

    def record_sale(self, sale_id: str, product_id: str,
                    quantity: int = 1, at: str = "") -> Settlement:
        """Record a sale and settle its royalty splits (paper ledger).

        Idempotent on ``sale_id``: a repeated call returns the original
        settlement without double-settling.
        """
        if not isinstance(sale_id, str) or not sale_id.strip():
            raise RoyaltyError("sale_id must be a non-empty string")
        if sale_id in self._settlements:
            return self._settlements[sale_id]
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise RoyaltyError("quantity must be a positive integer")
        product = self.product(product_id)
        gross = product.price * quantity
        payouts = self._distribute(gross, product.shares)
        # BLUE (RED-1): seal the payouts at mint time — the ledger entry
        # is read-only. ``record_sale`` returns this same object on repeat
        # calls (idempotency), so it must be immutable, not a copy.
        settlement = Settlement(sale_id=sale_id, product_id=product_id,
                                gross=gross,
                                payouts=MappingProxyType(payouts), at=at or "")
        self._settlements[sale_id] = settlement
        self._ledger.append(settlement)
        return settlement

    # -- founder's cut (original SER-18 mechanic) -----------------------
    @staticmethod
    def founder_cut_shares(seller: str,
                           founder: str = FOUNDER_WALLET) -> List[RoyaltyShare]:
        """The original split: 15% to the founder wallet, 85% to the seller.

        From the recovered SER-18 spec: SupraStreet "calculates payouts,
        automatically enforcing a strict 15% royalty cut allocated to the
        Founder wallet on every settlement."
        """
        if not isinstance(seller, str) or not seller.strip():
            raise RoyaltyError("seller must be a non-empty string")
        if not isinstance(founder, str) or not founder.strip():
            raise RoyaltyError("founder must be a non-empty string")
        return [RoyaltyShare(founder, FOUNDER_CUT_BP),
                RoyaltyShare(seller, _BASIS - FOUNDER_CUT_BP)]

    def register_product_with_founder_cut(
        self, product_id: str, title: str, price: int, seller: str,
        founder: str = FOUNDER_WALLET,
    ) -> Product:
        """Register a product carrying the original 15% founder's cut."""
        return self.register_product(
            product_id, title, price,
            self.founder_cut_shares(seller, founder),
        )

    # -- reads ---------------------------------------------------------
    def settlements(self) -> List[Settlement]:
        """The append-only paper trail — as detached snapshots.

        BLUE (RED-1) MONEY LAW: every read returns a fresh ``Settlement``
        carrying its own plain-``dict`` payouts copy. Mutating a returned
        object cannot rewrite the ledger: conservation
        (``total_distributed() == gross``) and the founder's cut survive
        any read-side access. Paper-only commerce — no chain, no rails,
        no funds move.
        """
        return [
            Settlement(
                sale_id=s.sale_id,
                product_id=s.product_id,
                gross=s.gross,
                payouts=dict(s.payouts),
                at=s.at,
            )
            for s in self._ledger
        ]

    def earnings(self, recipient: str) -> int:
        """Total paper earnings for a recipient across all settlements."""
        return sum(s.payouts.get(recipient, 0) for s in self._ledger)
