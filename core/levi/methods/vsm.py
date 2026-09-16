"""Beer's Viable System Model: the five-system organizational diagnostic.

Origin: Stafford Beer's cybernetic model of *any* viable organization — a
company, a body, a household. Five recursively nested functions:

- **S1 Operations** — the things that do the work (the viable units themselves)
- **S2 Coordination** — anti-oscillation between S1 units (schedules, standards)
- **S3 Control** — internal regulation, resource bargaining ("inside and now")
- **S3\\* Audit** — the sporadic direct-look channel that bypasses hierarchy filters
- **S4 Intelligence** — outward- and future-looking ("outside and then")
- **S5 Policy/Identity** — what we are, what we will become

What it is in LEVI: a diagnostic. Map recurring activities onto the five
systems; the model finds the missing or colonized function. Most personal
systems lack an S4 — nobody is scanning the future — so the assistant can
*become* your S4 (weekly outside-world briefing) and your S3* (a weekly
direct-look report that bypasses your own narrative filters).

Honesty label: LOAD-BEARING — recursion + "find the missing function" is a
concrete diagnostic mechanism. (Beer's prose is oracular and the jargon
forbidding; this module keeps the mechanism and drops the mystique.)

Deny-closed inputs: unknown system codes, empty unit names, and duplicate
units are rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

__all__ = ["SYSTEMS", "Unit", "Finding", "VSM", "SystemCode"]

SYSTEMS: dict[str, str] = {
    "1": "Operations — the viable units doing the work",
    "2": "Coordination — anti-oscillation between S1 units",
    "3": "Control — internal regulation, resource bargaining (inside & now)",
    "3*": "Audit — sporadic direct-look channel bypassing hierarchy filters",
    "4": "Intelligence — outward- and future-looking (outside & then)",
    "5": "Policy/Identity — what we are, what we will become",
}

SystemCode = str  # one of "1".."5" or "3*"

_SYSTEM_NOTES = {
    "1": "no operations mapped — there is nothing doing the work",
    "2": "no coordination mapped — S1 units will oscillate and clash",
    "3": "no control mapped — no internal regulation or resource bargaining",
    "3*": "no audit channel — management sees S1 only through hierarchy filters",
    "4": "no intelligence mapped — nobody is scanning the outside and the future",
    "5": "no policy mapped — no identity deciding what this is and will become",
}


@dataclass
class Unit:
    name: str
    system: SystemCode
    description: str = ""


@dataclass
class Finding:
    system: SystemCode
    severity: str  # "high" | "medium" | "info"
    message: str


class VSM:
    """One viable system under diagnosis; S1 units may nest sub-diagnostics."""

    def __init__(self, name: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("system name must be a non-empty string")
        self.name = name.strip()
        self.units: list[Unit] = []
        self.subsystems: dict[str, "VSM"] = {}  # S1 unit name -> its own VSM (recursion)

    def add_unit(self, name: str, system: SystemCode, description: str = "") -> Unit:
        if system not in SYSTEMS:
            raise ValueError(f"unknown system {system!r}; use one of {sorted(SYSTEMS)}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("unit name must be a non-empty string")
        name = name.strip()
        if any(u.name.lower() == name.lower() for u in self.units):
            raise ValueError(f"duplicate unit: {name!r}")
        unit = Unit(name=name, system=system, description=description or "")
        self.units.append(unit)
        return unit

    def decompose(self, s1_unit_name: str, sub_name: Optional[str] = None) -> "VSM":
        """Recursion: an S1 unit is itself a viable system — diagnose it too."""
        unit = next((u for u in self.units
                     if u.name.lower() == s1_unit_name.strip().lower() and u.system == "1"), None)
        if unit is None:
            raise ValueError(f"no S1 unit named {s1_unit_name!r} to decompose")
        sub = VSM(sub_name or unit.name)
        self.subsystems[unit.name] = sub
        return sub

    def _units_in(self, system: SystemCode) -> list[Unit]:
        return [u for u in self.units if u.system == system]

    def diagnose(self) -> list[Finding]:
        """Find the missing or colonized function."""
        findings: list[Finding] = []
        present = {s for s in SYSTEMS if self._units_in(s)}

        for code in ("1", "2", "3", "4", "5"):
            if code not in present:
                findings.append(Finding(
                    system=code,
                    severity="high" if code in ("1", "4", "5") else "medium",
                    message=f"S{code} absent: {_SYSTEM_NOTES[code]}."))

        if "3*" not in present:
            findings.append(Finding(system="3*", severity="medium",
                                    message=f"S3* absent: {_SYSTEM_NOTES['3*']}."))

        s1, s2, s3 = (len(self._units_in(c)) for c in ("1", "2", "3"))
        if s1 and s2 > s1:
            findings.append(Finding(
                system="2", severity="medium",
                message=f"Coordination overhead: {s2} coordination units for {s1} "
                        "operational units — S2 may be strangling S1's autonomy."))
        if s3 > s1 and s1:
            findings.append(Finding(
                system="3", severity="medium",
                message=f"Control heavy: {s3} control units over {s1} operational "
                        "units — S3 may have colonized S1 (micromanagement)."))
        if s1 == 0 and (self._units_in("3") or self._units_in("5")):
            findings.append(Finding(
                system="1", severity="high",
                message="Control/policy exist with no operations — governing nothing."))

        for unit_name, sub in self.subsystems.items():
            for f in sub.diagnose():
                findings.append(Finding(
                    system=f.system, severity=f.severity,
                    message=f"[recursion via S1 unit {unit_name!r}] {f.message}"))

        undecomposed = [u.name for u in self._units_in("1")
                        if u.name not in self.subsystems]
        for name in undecomposed:
            findings.append(Finding(
                system="1", severity="info",
                message=f"S1 unit {name!r} not decomposed — recursion unchecked; "
                        "call decompose() to verify it is itself viable."))
        return findings

    def viability_report(self) -> dict:
        findings = self.diagnose()
        by_severity: dict[str, int] = {"high": 0, "medium": 0, "info": 0}
        for f in findings:
            by_severity[f.severity] += 1
        return {
            "system": self.name,
            "units": len(self.units),
            "systems_present": sorted({u.system for u in self.units}),
            "findings": [{"system": f.system, "severity": f.severity,
                          "message": f.message} for f in findings],
            "by_severity": by_severity,
            "verdict": ("VIABLE" if by_severity["high"] == 0
                        else "NOT VIABLE — missing load-bearing functions"),
        }
