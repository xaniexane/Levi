"""Secondlife — the zero-capex home server: a retired laptop, honestly scored.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§8] (repurpose-old-laptop-as-server: zero-capex home server — the cheapest
host is hardware already owned).

This is an original, from-scratch implementation for LEVI. A ``Laptop``
describes the retired machine: age, battery health, idle/active draw, RAM,
storage, and which roles it must fill. ``Secondlife`` scores it as a server
candidate:

- ``capex`` is always $0 — the machine is already owned; the model says so
  explicitly instead of hiding it.
- ``yearly_energy_cost`` from its draw profile and your $/kWh (or the
  $1/watt-year rule when no price is given).
- ``suitability``: a weighted checklist (battery safety, thermals, RAM,
  storage, NIC, uptime needs) producing a 0–100 score plus the *reasons*
  behind it — and hard ``blockers`` (e.g. a swollen battery) that veto the
  idea regardless of score.
- ``setup_plan``: the ordered, generic steps to convert it (power, storage
  health, OS role, monitoring) as data the caller can render — no
  OS-specific commands, no privileged actions taken here.
- ``compare_vs_new``: TCO against buying a new low-power host, showing the
  honest trade: $0 capex vs higher draw and shorter remaining life.

Honest limits: this is a planning model. It cannot inspect your hardware;
every spec is caller-supplied, and the scores are heuristics — labeled as
such in the docstrings and the report.

Public surface:
- ``Laptop`` / ``BatteryHealth``: the candidate machine.
- ``Secondlife``: ``suitability``, ``yearly_energy_cost``, ``setup_plan``,
  ``compare_vs_new``.
- ``SecondlifeError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

ORIGIN = "levi-revival/laptop_server"

DOLLARS_PER_WATT_YEAR = 1.0
KWH_PER_WATT_YEAR = 8.76


class SecondlifeError(ValueError):
    """Raised when a laptop profile or comparison cannot be honored."""


class BatteryHealth(str, Enum):
    GOOD = "good"  # holds charge, no swelling, stays cool
    WEAK = "weak"  # short runtime but physically sound
    SWOLLEN = "swollen"  # physical deformation — hard blocker
    REMOVED = "removed"  # battery taken out, runs on AC only


@dataclass(frozen=True)
class Laptop:
    """The retired machine, as its owner describes it."""

    name: str
    age_years: float
    battery: BatteryHealth
    idle_watts: float
    active_watts: float
    utilization: float = 0.25
    ram_gb: float = 8.0
    storage_gb: float = 256.0
    storage_healthy: bool = True  # SMART/prior errors clean, to owner's knowledge
    has_ethernet: bool = False
    always_on: bool = True  # must serve 24/7, not just on demand
    max_acceptable_watts: float = 25.0  # owner's power ceiling for the role

    def __post_init__(self) -> None:
        if not self.name:
            raise SecondlifeError("laptop name must be non-empty")
        if self.age_years < 0:
            raise SecondlifeError("age cannot be negative")
        if self.idle_watts < 0 or self.active_watts < self.idle_watts:
            raise SecondlifeError("invalid watt figures")
        if not (0.0 <= self.utilization <= 1.0):
            raise SecondlifeError("utilization must be in 0..1")
        if self.ram_gb <= 0 or self.storage_gb <= 0:
            raise SecondlifeError("ram and storage must be positive")


@dataclass
class Suitability:
    """Score plus the reasoning: factors for, factors against, blockers."""

    score: int  # 0..100, heuristic
    strengths: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    @property
    def viable(self) -> bool:
        return not self.blockers and self.score >= 50


class Secondlife:
    """Scores a retired laptop as a zero-capex server."""

    #: capex is always zero — the machine is already owned.
    CAPEX_DOLLARS = 0.0

    def __init__(self, dollars_per_kwh: Optional[float] = None) -> None:
        if dollars_per_kwh is not None and dollars_per_kwh < 0:
            raise SecondlifeError("electricity price cannot be negative")
        self.dollars_per_kwh = dollars_per_kwh

    @staticmethod
    def avg_watts(laptop: Laptop) -> float:
        return (
            laptop.idle_watts
            + (laptop.active_watts - laptop.idle_watts) * laptop.utilization
        )

    def yearly_energy_cost(self, laptop: Laptop) -> float:
        avg = self.avg_watts(laptop)
        if self.dollars_per_kwh is None:
            return avg * DOLLARS_PER_WATT_YEAR
        return avg * KWH_PER_WATT_YEAR * self.dollars_per_kwh

    def suitability(self, laptop: Laptop) -> Suitability:
        """Heuristic 0–100 score with explicit reasons and hard blockers."""
        score = 60  # a working laptop starts viable; evidence moves it
        strengths: List[str] = []
        concerns: List[str] = []
        blockers: List[str] = []

        # Battery: safety first — a hard veto, not a deduction.
        if laptop.battery is BatteryHealth.SWOLLEN:
            blockers.append(
                "battery is swollen: do not run unattended — replace or remove it first"
            )
        elif laptop.battery is BatteryHealth.REMOVED:
            strengths.append("battery removed: no battery fire risk on 24/7 AC power")
            score += 8
        elif laptop.battery is BatteryHealth.WEAK:
            concerns.append("weak battery: fine on AC, but no ride-through on outages")
            score -= 4
        else:
            strengths.append("battery healthy: built-in UPS for short outages")

        # Thermals / power envelope.
        avg = self.avg_watts(laptop)
        if avg <= laptop.max_acceptable_watts:
            strengths.append(
                f"average draw {avg:.1f}W within your {laptop.max_acceptable_watts:.0f}W ceiling"
            )
            score += 8
        else:
            concerns.append(
                f"average draw {avg:.1f}W exceeds your {laptop.max_acceptable_watts:.0f}W ceiling"
            )
            score -= 12

        # Age and remaining life.
        if laptop.age_years <= 4:
            strengths.append(
                f"only {laptop.age_years:.0f} years old: reasonable remaining life"
            )
            score += 6
        elif laptop.age_years <= 7:
            concerns.append(
                f"{laptop.age_years:.0f} years old: budget for sudden failure"
            )
            score -= 6
        else:
            concerns.append(
                f"{laptop.age_years:.0f} years old: treat as disposable, keep backups current"
            )
            score -= 14

        # Storage health is a data-safety question.
        if laptop.storage_healthy:
            strengths.append("storage reported healthy")
            score += 6
        else:
            blockers.append(
                "storage health suspect: replace the drive before trusting it"
            )

        # Capability floor for a useful server.
        if laptop.ram_gb >= 8:
            strengths.append(f"{laptop.ram_gb:g}GB RAM: comfortable for services")
            score += 4
        else:
            concerns.append(f"{laptop.ram_gb:g}GB RAM: fine for light duties only")
            score -= 6
        if laptop.storage_gb >= 256:
            score += 4
        else:
            concerns.append(
                f"{laptop.storage_gb:g}GB storage: tight for media or backups"
            )
            score -= 4

        # Connectivity and duty.
        if laptop.has_ethernet:
            strengths.append("wired ethernet: stable, lower latency than Wi-Fi")
            score += 4
        else:
            concerns.append(
                "Wi-Fi only: consider a USB ethernet adapter for reliability"
            )
            score -= 3
        if not laptop.always_on:
            concerns.append(
                "not required 24/7: on-demand duty is kinder to old hardware"
            )
            score += 2

        return Suitability(
            score=max(0, min(100, score)),
            strengths=strengths,
            concerns=concerns,
            blockers=blockers,
        )

    def setup_plan(self, laptop: Laptop) -> List[Dict[str, str]]:
        """Ordered, OS-neutral conversion steps — data for the caller to render."""
        suit = self.suitability(laptop)
        steps = [
            {
                "phase": "safety",
                "step": "Inspect the battery; if swollen, remove it and run on AC only.",
            },
            {
                "phase": "safety",
                "step": "Verify storage health (SMART long test) before trusting data to it.",
            },
            {
                "phase": "power",
                "step": "Run on AC with the lid closed; set the machine to stay awake when the lid shuts.",
            },
            {
                "phase": "power",
                "step": "If the battery stays in, cap charge at 60–80% to slow wear.",
            },
            {
                "phase": "thermal",
                "step": "Give it airflow (raised stand, not a cushion); clean the fans.",
            },
            {
                "phase": "os",
                "step": "Install a minimal server OS or strip the desktop install to services only.",
            },
            {
                "phase": "os",
                "step": "Enable automatic security updates and unattended reboot windows you choose.",
            },
            {
                "phase": "network",
                "step": "Prefer wired ethernet (USB adapter if needed); assign a static address.",
            },
            {
                "phase": "data",
                "step": "Back it up like any server — age makes sudden death likelier, not rarer.",
            },
            {
                "phase": "monitor",
                "step": "Watch temperature, disk health, and uptime; alert on anomalies.",
            },
        ]
        if suit.blockers:
            steps.insert(
                0,
                {
                    "phase": "blocker",
                    "step": "Resolve blockers first: " + "; ".join(suit.blockers),
                },
            )
        return steps

    def compare_vs_new(
        self,
        laptop: Laptop,
        new_host_capex: float,
        new_host_avg_watts: float,
        horizon_years: float = 3.0,
    ) -> Dict[str, float]:
        """TCO of the $0 laptop vs buying a new low-power host."""
        if new_host_capex < 0 or new_host_avg_watts < 0 or horizon_years <= 0:
            raise SecondlifeError("comparison inputs must be positive")
        laptop_energy = self.yearly_energy_cost(laptop) * horizon_years
        if self.dollars_per_kwh is None:
            new_energy = new_host_avg_watts * DOLLARS_PER_WATT_YEAR * horizon_years
        else:
            new_energy = (
                new_host_avg_watts
                * KWH_PER_WATT_YEAR
                * self.dollars_per_kwh
                * horizon_years
            )
        laptop_tco = self.CAPEX_DOLLARS + laptop_energy
        new_tco = new_host_capex + new_energy
        return {
            "laptop_tco_dollars": round(laptop_tco, 2),
            "new_host_tco_dollars": round(new_tco, 2),
            "laptop_saves_dollars": round(new_tco - laptop_tco, 2),
            "horizon_years": horizon_years,
        }
