"""Door 2 — Hicomb dock: seasoned / complex dev work.

The dock contract lives in :mod:`levi.hicomb.dock` (home-agnostic, lazy,
never raises for sibling flux). This door is the builders-side handle:
it delegates docking to that contract and offers the same single engine
for complex builds. The door adds the *editor surface* — session attach,
command registration — never different generation logic.
"""

from __future__ import annotations

from typing import Optional

from levi.builders.doors.project import DoorReport, Project, open_project
from levi.builders.economy import BuildLedger
from levi.builders.pipeline import build as _engine_build

DOOR_NAME = "hicomb"
DEMAND_CLASS = "seasoned / complex"


def dock(session, registry=None, engine=None):
    """Attach builders to a Hicomb session via the existing dock contract.

    Imported lazily so a sibling's in-flight refactor of either package
    can never break this import — same rule :mod:`levi.hicomb.dock`
    follows in the other direction. Returns its :class:`DockReport`.

    ``engine`` passes straight through: give a ``ScaffoldEngine`` (or a
    :class:`DoorReport`) to attach it, or leave it ``None`` for the
    contract's default path — which reports honestly instead of raising
    when the engine cannot be constructed without a prompt.
    """
    from levi.hicomb.dock import dock_builders  # lazy; never at module import

    return dock_builders(session, registry, engine=engine)


def build_complex(
    prompt: str,
    workdir: Optional[str] = None,
    ledger: Optional[BuildLedger] = None,
) -> DoorReport:
    """Scaffold through the Hicomb door — the same engine, tagged.

    "Complex" is a property of the work done in the editor afterwards
    (buffer, tabs, journal, command bar); generation itself is identical
    across doors by construction — see ``DoorReport.continue_via``.
    """
    return DoorReport(
        door=DOOR_NAME,
        prompt=prompt,
        build_report=_engine_build(prompt, workdir=workdir, ledger=ledger),
    )


__all__ = [
    "DEMAND_CLASS",
    "DOOR_NAME",
    "Project",
    "build_complex",
    "dock",
    "open_project",
]
