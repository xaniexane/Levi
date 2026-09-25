"""Capped five-agent delegation fleet: a locked task, five roles, one report, death.

Origin: the 2026 "KAI-9000" method entry in the archive — instead of a swarm,
exactly five specialist roles spin up for a locked fat task, produce one
folded report, then die. No standing army: the fleet exists for one task and
one task only, so bloat is structurally impossible.

What it is in LEVI: ``DelegationFleet``. The task is locked first; then
exactly the five fixed roles each submit their section — ``architect`` defines
interfaces, ``builder`` builds the smallest working slice, ``redteam`` attacks
weaknesses, ``scopesentry`` guards scope, ``scribe`` writes the digest. The
sections fold into one report in role order, the fleet is terminated, and any
reuse raises — a second task needs a new fleet.

Honesty label: LOAD-BEARING — lock -> five fixed roles -> folded report ->
terminated is a concrete, enforceable lifecycle.

Deny-closed inputs: empty task titles, locking twice, submitting before the
task is locked, submitting for an unknown or already-submitted role,
submitting an empty section, reporting before all five roles have submitted,
and any use after the fleet is terminated are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["ROLES", "ROLE_DEFS", "FleetSection", "DelegationFleet"]

ROLES = ("architect", "builder", "redteam", "scopesentry", "scribe")

ROLE_DEFS = {
    "architect": "defines the interfaces",
    "builder": "builds the smallest working slice",
    "redteam": "attacks weaknesses",
    "scopesentry": "guards scope",
    "scribe": "writes the digest",
}


@dataclass
class FleetSection:
    """One role's contribution to the folded report."""

    role: str
    text: str


class DelegationFleet:
    """Exactly five specialists, one locked task, one folded report, then death."""

    def __init__(self) -> None:
        self._task: Optional[str] = None
        self._sections: dict[str, FleetSection] = {}
        self._terminated = False

    # -- lifecycle ------------------------------------------------------
    @property
    def is_terminated(self) -> bool:
        return self._terminated

    def _require_live(self) -> None:
        if self._terminated:
            raise ValueError(
                "fleet is terminated: it died with its one report; "
                "start a new DelegationFleet for a new task"
            )

    def lock(self, task_title: str) -> None:
        """Lock the single fat task this fleet exists for. Exactly once."""
        self._require_live()
        if not isinstance(task_title, str) or not task_title.strip():
            raise ValueError("task title must be a non-empty string")
        if self._task is not None:
            raise ValueError(f"task already locked: {self._task!r}")
        self._task = task_title.strip()

    def submit(self, role: str, section: str) -> FleetSection:
        """One role submits its section. Each role submits exactly once."""
        self._require_live()
        if self._task is None:
            raise ValueError("submit refused: no task locked yet")
        if role not in ROLES:
            raise ValueError(
                f"unknown role {role!r}: the five fixed roles are {list(ROLES)}"
            )
        if role in self._sections:
            raise ValueError(f"role {role!r} already submitted its section")
        if not isinstance(section, str) or not section.strip():
            raise ValueError(f"role {role!r}: section must be a non-empty string")
        entry = FleetSection(role=role, text=section.strip())
        self._sections[role] = entry
        return entry

    def pending_roles(self) -> list[str]:
        """Roles that have not submitted yet, in fleet order."""
        self._require_live()
        return [r for r in ROLES if r not in self._sections]

    def report(self) -> str:
        """Fold the five sections into one report, in role order, then die."""
        self._require_live()
        if self._task is None:
            raise ValueError("report refused: no task locked yet")
        missing = [r for r in ROLES if r not in self._sections]
        if missing:
            raise ValueError(f"report refused: roles not yet submitted: {missing}")
        lines = [f"# {self._task}", ""]
        for role in ROLES:
            lines.append(f"## {role} — {ROLE_DEFS[role]}")
            lines.append(self._sections[role].text)
            lines.append("")
        self._terminated = True
        return "\n".join(lines).rstrip() + "\n"
