"""Carrier micropay — packet billing plus low-take content billing.

Studied from: dead-networks-20260916, report.md [i-mode] — NTT DoCoMo's
i-mode: packet-based billing for transport plus carrier billing for
content with only a ~9% revenue take, creating a real mobile content
economy of frictionless micropayments.

This module models that two-layer pattern: a ``Device`` accrues
per-packet transport charges; ``ContentSite`` purchases are billed
through the carrier, which passes ~91% to the site and keeps a declared
take. Micropayment records settle into per-site payouts. Integer minor
units, local ledger, no network and no money.

Honesty: toy ledger. Packet sizes are caller-supplied units, not real
bytes; there is no congestion pricing, no roaming, no credit risk.
The preserved pattern is the economics: cheap metered transport plus a
small-take content toll so small payments clear.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

ORIGIN = "levi-revival/carrier-micropay"

# The i-mode-era carrier take, as a documented default, not a claim of
# exactness: the point is a *small* declared cut, not the precise value.
DEFAULT_CARRIER_TAKE = 0.09


@dataclass(frozen=True)
class ContentSite:
    """A content provider selling through carrier billing."""

    site_id: str
    name: str


@dataclass
class Device:
    """A subscriber device: packet usage and content bill, metered."""

    device_id: str
    packet_units: int = 0  # transport charge accrued
    content_units: int = 0  # content purchases accrued


@dataclass(frozen=True)
class Micropayment:
    """One content purchase cleared through the carrier."""

    site_id: str
    device_id: str
    price_units: int

    def __post_init__(self) -> None:
        if self.price_units <= 0:
            raise ValueError("price_units must be > 0")


class CarrierMicropay:
    """Carrier running packet billing and low-take content settlement."""

    def __init__(
        self, packet_rate_units: int = 1, carrier_take: float = DEFAULT_CARRIER_TAKE
    ) -> None:
        if packet_rate_units <= 0:
            raise ValueError("packet_rate_units must be > 0")
        if not 0.0 <= carrier_take < 1.0:
            raise ValueError("carrier_take must be in [0, 1)")
        self.packet_rate_units = packet_rate_units
        self.carrier_take = carrier_take
        self.devices: Dict[str, Device] = {}
        self.sites: Dict[str, ContentSite] = {}
        self.payments: List[Micropayment] = []
        self.site_balances: Dict[str, int] = {}
        self.transport_revenue_units: int = 0

    def register_device(self, device: Device) -> None:
        if device.device_id in self.devices:
            raise ValueError(f"duplicate device {device.device_id!r}")
        self.devices[device.device_id] = device

    def register_site(self, site: ContentSite) -> None:
        if site.site_id in self.sites:
            raise ValueError(f"duplicate site {site.site_id!r}")
        self.sites[site.site_id] = site

    def meter_packets(self, device_id: str, packets: int) -> int:
        """Bill transport per packet; returns units charged."""
        if packets < 0:
            raise ValueError("packets must be >= 0")
        device = self.devices.get(device_id)
        if device is None:
            raise ValueError(f"unknown device {device_id!r}")
        charge = packets * self.packet_rate_units
        device.packet_units += charge
        self.transport_revenue_units += charge
        return charge

    def buy(self, device_id: str, site_id: str, price_units: int) -> Micropayment:
        """One frictionless micropayment, cleared through the carrier."""
        if site_id not in self.sites:
            raise ValueError(f"unknown site {site_id!r}")
        device = self.devices.get(device_id)
        if device is None:
            raise ValueError(f"unknown device {device_id!r}")
        payment = Micropayment(site_id, device_id, price_units)
        self.payments.append(payment)
        device.content_units += price_units
        site_share = int(round(price_units * (1.0 - self.carrier_take)))
        self.site_balances[site_id] = self.site_balances.get(site_id, 0) + site_share
        return payment

    def settle_site(self, site_id: str) -> int:
        """Pay out a site's accumulated share; returns units paid."""
        if site_id not in self.sites:
            raise ValueError(f"unknown site {site_id!r}")
        amount = self.site_balances.get(site_id, 0)
        self.site_balances[site_id] = 0
        return amount

    def monthly_bill(self, device_id: str) -> Dict[str, int]:
        """One device's combined transport + content bill."""
        device = self.devices.get(device_id)
        if device is None:
            raise ValueError(f"unknown device {device_id!r}")
        return {
            "device_id": device_id,
            "transport_units": device.packet_units,
            "content_units": device.content_units,
            "total_units": device.packet_units + device.content_units,
        }
