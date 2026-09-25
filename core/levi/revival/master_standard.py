"""LEVI's master-standard registry: one canonical measure, checked copies, drift watch.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(Egyptian Royal Cubit)

The studied mechanism:

* one granite master standard held the canonical length — the single
  source of truth, rarely touched;
* working rods were checked *against* it and re-checked over time, with
  drift recorded rather than silently absorbed;
* derived units and ratios (the seked: slope encoded as run-per-rise,
  i.e. a cotangent) were defined from the master, so every derived
  measure carried its lineage.

This module rebuilds that as LEVI's own mechanism. A
:class:`MasterStandard` holds a canonical definition (value in a base
unit, plus a definition string) and a *versioned* history: every
redefinition is a new version, never an edit of the past. Working
instruments (:class:`WorkingRod`) are calibrated against a master
version and carry their own error; a drift watch compares fresh audit
measurements against the recorded value and raises
:class:`DriftAlert` past tolerance. Derived units register with their
lineage, and :func:`seked_ratio` encodes a slope as run-per-rise the way
the studied builders did.

Honest limits: a software registry cannot *be* a granite bar. The
"canonical value" here is a declared number; the module's honest work
is versioning, lineage, and drift *detection* on reported measurements
— it trusts the measurer, then checks their math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/master_standard"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StandardError(Exception):
    """Base error for master-standard failures."""


class DriftAlert(StandardError):
    """Raised/recorded when an audit measurement exceeds tolerance."""


# ---------------------------------------------------------------------------
# Versions of the one true measure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StandardVersion:
    """One version of the master's definition.

    value: canonical length in the base unit of the registry.
    definition: human-readable definition ("length of the granite bar in
    the vault").
    supersedes: the previous version number, or None for the first.
    """

    version: int
    value: float
    definition: str
    supersedes: Optional[int] = None


@dataclass
class WorkingRod:
    """A working copy checked against one master version.

    serial: the rod's identifier. error: the measured deviation from the
    master at last check, in base units. readings: audit history of
    (value, note) pairs.
    """

    serial: str
    master_version: int
    error: float = 0.0
    readings: List[Tuple[float, str]] = field(default_factory=list)

    def audit(
        self, measured: float, master_value: float, tolerance: float
    ) -> Optional[DriftAlert]:
        """Record an audit measurement; return a DriftAlert if out of tolerance."""
        self.readings.append((measured, f"vs master {master_value}"))
        drift = measured - master_value
        self.error = drift
        if abs(drift) > tolerance:
            return DriftAlert(
                f"rod {self.serial}: drift {drift:+.6f} exceeds tolerance {tolerance}"
            )
        return None


class MasterStandard:
    """The registry: one canonical measure, versioned; rods checked against it."""

    def __init__(self, name: str, base_unit: str) -> None:
        self.name = name
        self.base_unit = base_unit
        self._versions: List[StandardVersion] = []
        self._rods: Dict[str, WorkingRod] = {}
        self._derived: Dict[str, Tuple[float, str]] = {}  # name -> (factor, lineage)
        self.alerts: List[DriftAlert] = []

    # -- the master ------------------------------------------------------

    def define(self, value: float, definition: str) -> StandardVersion:
        """Issue a new version of the master. Never edits the past."""
        version = StandardVersion(
            version=len(self._versions) + 1,
            value=value,
            definition=definition,
            supersedes=self._versions[-1].version if self._versions else None,
        )
        self._versions.append(version)
        return version

    def current(self) -> StandardVersion:
        if not self._versions:
            raise StandardError(f"master {self.name!r} has no definition yet")
        return self._versions[-1]

    def history(self) -> List[StandardVersion]:
        return list(self._versions)

    # -- the rods --------------------------------------------------------

    def check_rod(self, serial: str) -> WorkingRod:
        """Check (or re-check) a working rod against the current master."""
        rod = WorkingRod(
            serial=serial, master_version=self.current().version, error=0.0
        )
        self._rods[serial] = rod
        return rod

    def audit_rod(
        self, serial: str, measured: float, tolerance: float
    ) -> Optional[DriftAlert]:
        rod = self._rods.get(serial)
        if rod is None:
            raise StandardError(f"unknown rod {serial!r}")
        alert = rod.audit(measured, self.current().value, tolerance)
        if alert is not None:
            self.alerts.append(alert)
        return alert

    # -- derived measures ------------------------------------------------

    def derive(self, name: str, factor: float, lineage: str = "") -> float:
        """Define a derived unit: ``factor`` × the current master value.

        The lineage note records *why* (e.g. "1/7 of the master"). The
        derived value is bound to the master version current at
        definition time — redefining the master does not rewrite history.
        """
        value = self.current().value * factor
        self._derived[name] = (
            factor,
            lineage or f"{factor} × {self.name} v{self.current().version}",
        )
        return value

    def derived_value(self, name: str) -> float:
        if name not in self._derived:
            raise StandardError(f"unknown derived unit {name!r}")
        factor, _ = self._derived[name]
        return self.current().value * factor


def seked_ratio(rise: float, run: float) -> float:
    """Encode a slope as run-per-rise (cotangent), the seked way.

    The studied builders did not record angles; they recorded the
    horizontal run for a fixed vertical rise — a ratio a mason can lay
    out with a rod and a plumb line, no protractor required. A vertical
    wall (run 0) is a seked of 0; shallower slopes give larger sekeds.
    """
    if rise <= 0:
        raise StandardError("rise must be positive")
    return run / rise
