"""Wattledger — host power economics: the dollar-per-watt-year rule.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§8] (low-power ARM/SBC hosts: Pi-class and N100 mini PCs drawing 4–9W
instead of 55–140W towers; idle draw dominates; rule of thumb ~$1 per
watt-year).

This is an original, from-scratch implementation for LEVI. A ``Host``
describes a machine by what actually drives its bill: idle watts, active
watts, utilization, capex, and expected service life. ``Wattledger``
applies the studied rule of thumb — each watt of *average* draw costs about
$1 per year at typical residential rates — then refines it with the real
inputs when given (electricity price, duty cycle, idle fraction), and
computes total cost of ownership over a horizon so a $45 SBC and a $0
scrap tower can be compared honestly:

- ``avg_watts``: idle + (active − idle) × utilization.
- ``yearly_energy_cost``: avg watts × $/watt-year, or exact kWh math when a
  $/kWh price is supplied.
- ``tco``: capex + energy over N years (+ optional yearly maintenance).
- ``compare`` / ``payback``: rank hosts by TCO, and months for a pricier
  efficient host to earn back its premium over a cheaper thirsty one.

The $1/watt-year figure assumes ~$0.11–0.12/kWh continuous draw; the exact
path uses your price instead. No hardware database is bundled — profiles
are user-supplied, so no spec claim can go stale.

Public surface:
- ``Host``: idle_watts, active_watts, utilization, capex_dollars,
  lifespan_years, yearly_maintenance_dollars.
- ``Wattledger``: ``avg_watts``, ``yearly_energy_cost``, ``tco``,
  ``compare``, ``payback_months``, ``rule_of_thumb``.
- ``HostError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

ORIGIN = "levi-revival/arm_hosts"

#: The studied rule of thumb: one average watt ≈ $1/year at ~$0.11/kWh.
DOLLARS_PER_WATT_YEAR = 1.0
#: kWh drawn by one watt running continuously for a year.
KWH_PER_WATT_YEAR = 8.76


class HostError(ValueError):
    """Raised when a host profile or comparison cannot be honored."""


@dataclass(frozen=True)
class Host:
    """One candidate machine, described by its power profile and price."""

    name: str
    idle_watts: float
    active_watts: float
    utilization: float = 0.2  # fraction of time at active draw
    capex_dollars: float = 0.0
    lifespan_years: float = 5.0
    yearly_maintenance_dollars: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise HostError("host name must be non-empty")
        if self.idle_watts < 0 or self.active_watts < 0:
            raise HostError("watt figures cannot be negative")
        if self.active_watts < self.idle_watts:
            raise HostError("active_watts should be >= idle_watts")
        if not (0.0 <= self.utilization <= 1.0):
            raise HostError("utilization must be in 0..1")
        if self.capex_dollars < 0 or self.yearly_maintenance_dollars < 0:
            raise HostError("costs cannot be negative")
        if self.lifespan_years <= 0:
            raise HostError("lifespan must be positive")


class Wattledger:
    """Power economics over a set of candidate hosts."""

    def __init__(self, dollars_per_kwh: Optional[float] = None) -> None:
        # None → use the $1/watt-year rule of thumb.
        if dollars_per_kwh is not None and dollars_per_kwh < 0:
            raise HostError("electricity price cannot be negative")
        self.dollars_per_kwh = dollars_per_kwh

    @staticmethod
    def avg_watts(host: Host) -> float:
        """Average draw: idle dominates at low utilization — the studied point."""
        return (
            host.idle_watts + (host.active_watts - host.idle_watts) * host.utilization
        )

    @staticmethod
    def rule_of_thumb(avg_watts: float) -> float:
        """Yearly energy cost via the $1 per watt-year rule."""
        if avg_watts < 0:
            raise HostError("watts cannot be negative")
        return avg_watts * DOLLARS_PER_WATT_YEAR

    def yearly_energy_cost(self, host: Host) -> float:
        avg = self.avg_watts(host)
        if self.dollars_per_kwh is None:
            return self.rule_of_thumb(avg)
        return avg * KWH_PER_WATT_YEAR * self.dollars_per_kwh

    def tco(self, host: Host, years: Optional[float] = None) -> float:
        """Total cost of ownership over the horizon (default: host lifespan)."""
        horizon = years if years is not None else host.lifespan_years
        if horizon <= 0:
            raise HostError("horizon must be positive")
        energy = self.yearly_energy_cost(host) * horizon
        capex_share = host.capex_dollars * min(1.0, horizon / host.lifespan_years)
        return capex_share + energy + host.yearly_maintenance_dollars * horizon

    def compare(
        self, hosts: List[Host], years: Optional[float] = None
    ) -> List[Tuple[Host, float, float]]:
        """Rank hosts by TCO: (host, tco, yearly_energy_cost), cheapest first."""
        if not hosts:
            raise HostError("no hosts to compare")
        ranked = [(h, self.tco(h, years), self.yearly_energy_cost(h)) for h in hosts]
        return sorted(ranked, key=lambda r: r[1])

    def payback_months(self, efficient: Host, thirsty: Host) -> Optional[float]:
        """Months for the efficient host's premium to pay back via energy.

        Returns None when it never pays back (no yearly savings).
        """
        premium = efficient.capex_dollars - thirsty.capex_dollars
        yearly_saving = self.yearly_energy_cost(thirsty) - self.yearly_energy_cost(
            efficient
        )
        if yearly_saving <= 0:
            return None
        if premium <= 0:
            return 0.0  # cheaper AND thriftier: payback is immediate
        return premium / yearly_saving * 12.0

    def report(self, hosts: List[Host], years: Optional[float] = None) -> List[dict]:
        rows = []
        for host, tco, energy in self.compare(hosts, years):
            rows.append(
                {
                    "host": host.name,
                    "avg_watts": round(self.avg_watts(host), 2),
                    "yearly_energy_dollars": round(energy, 2),
                    "tco_dollars": round(tco, 2),
                }
            )
        return rows
