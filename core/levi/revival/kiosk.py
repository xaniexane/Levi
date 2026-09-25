"""kiosk — network-bundled identity + billing: the Kiosque.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 17).

Load-bearing idea: services are reached by short codes; identity, usage
metering, billing, and revenue-sharing are *bundled* — a session carries
identity, usage meters to a bill, and revenue splits to service owners.
Zero-signup friction: identity *is* the session token.

LEVI's take: ``Kiosk`` is a registry of ``Service``s keyed by short
code. ``open_session()`` mints a token — that token is the user's whole
identity, no signup, no profile. ``use(token, code, units)`` runs the
service and meters the units. ``bill(token)`` totals the meter.
``settle()`` pays out: each service owner gets ``owner_share`` of their
service's revenue, the kiosk keeps the platform remainder. All local,
in-process — the model of bundled identity/billing, not a real network.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/kiosk"


class KioskError(Exception):
    """Misuse of the kiosk: unknown code, dead session, bad share."""


@dataclass
class Service:
    """A service behind a short code."""

    code: str  # short code, e.g. "411"
    name: str
    owner: str
    price_per_unit: float
    owner_share: float  # 0.0..1.0 of revenue to the owner
    handler: Callable[[str, float], str]  # (session_token, units) -> result

    def __post_init__(self) -> None:
        if not (0.0 <= self.owner_share <= 1.0):
            raise KioskError(f"owner_share must be 0..1, got {self.owner_share}")
        if self.price_per_unit < 0:
            raise KioskError("price_per_unit cannot be negative")


@dataclass
class Session:
    """Identity = the token. Nothing else is asked of the user."""

    token: str
    opened_at: float
    meter: Dict[str, float] = field(default_factory=dict)  # code -> units used
    closed: bool = False


@dataclass
class BillLine:
    code: str
    service: str
    units: float
    unit_price: float
    total: float


@dataclass
class Bill:
    token: str
    lines: List[BillLine]
    total: float


@dataclass
class Payout:
    owner: str
    code: str
    units: float
    gross: float
    owner_cut: float
    platform_cut: float


class Kiosk:
    """The bundled kiosk: short codes in, metered sessions, split payouts."""

    def __init__(self) -> None:
        self.services: Dict[str, Service] = {}
        self.sessions: Dict[str, Session] = {}

    # -- registry ------------------------------------------------------

    def register(self, service: Service) -> None:
        if service.code in self.services:
            raise KioskError(f"code {service.code!r} already registered")
        self.services[service.code] = service

    def directory(self) -> Dict[str, str]:
        """Short code -> service name. The whole public face."""
        return {code: svc.name for code, svc in self.services.items()}

    # -- sessions: identity ---------------------------------------------

    def open_session(self, now: Optional[float] = None) -> str:
        """Mint a session token. No signup — the token IS the identity."""
        token = uuid.uuid4().hex
        self.sessions[token] = Session(
            token=token, opened_at=now if now is not None else time.time()
        )
        return token

    def close_session(self, token: str) -> Bill:
        bill = self.bill(token)
        self.sessions[token].closed = True
        return bill

    def _session(self, token: str) -> Session:
        try:
            sess = self.sessions[token]
        except KeyError:
            raise KioskError("unknown session token") from None
        if sess.closed:
            raise KioskError("session is closed")
        return sess

    # -- usage: metering -------------------------------------------------

    def use(self, token: str, code: str, units: float = 1.0) -> str:
        """Run the service behind ``code``, meter ``units`` to the session."""
        if units < 0:
            raise KioskError("units cannot be negative")
        try:
            svc = self.services[code]
        except KeyError:
            raise KioskError(f"unknown service code {code!r}") from None
        sess = self._session(token)
        result = svc.handler(token, units)
        sess.meter[code] = sess.meter.get(code, 0.0) + units
        return result

    # -- billing --------------------------------------------------------

    def bill(self, token: str) -> Bill:
        sess = self._session(token)
        lines = [
            BillLine(
                code=code,
                service=self.services[code].name,
                units=units,
                unit_price=self.services[code].price_per_unit,
                total=units * self.services[code].price_per_unit,
            )
            for code, units in sess.meter.items()
        ]
        return Bill(token=token, lines=lines, total=sum(line.total for line in lines))

    # -- revenue sharing -------------------------------------------------

    def settle(self) -> List[Payout]:
        """Split all metered usage: owners get their share, kiosk keeps rest."""
        payouts: List[Payout] = []
        for _token, sess in self.sessions.items():
            for code, units in sess.meter.items():
                svc = self.services[code]
                gross = units * svc.price_per_unit
                owner_cut = gross * svc.owner_share
                payouts.append(
                    Payout(
                        owner=svc.owner,
                        code=code,
                        units=units,
                        gross=gross,
                        owner_cut=owner_cut,
                        platform_cut=gross - owner_cut,
                    )
                )
        return payouts

    def platform_revenue(self) -> float:
        return sum(p.platform_cut for p in self.settle())
