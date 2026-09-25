"""One engine, three doors.

``levi.builders`` is the single shared engine — all scaffold logic,
stdlib-only, deterministic, ternary outcomes, provenance, the no-meter
ledger. The product home is DECIDED (Chauncey, 2026-09-21): one engine
with three thin surface doors, named here:

- :mod:`levi.builders.doors.standalone` — door 1: general /
  low-production / simple users.
- :mod:`levi.builders.doors.hicomb` — door 2: seasoned / complex dev
  work, via the Hicomb dock contract.
- :mod:`levi.builders.doors.hub` — door 3: developers / enterprise,
  via the Hub surface.

Doors add surface, never logic: every door delegates to
:func:`levi.builders.pipeline.build`. A project scaffolded through one
door opens identically through the others — see
:func:`levi.builders.doors.open_project` and
:meth:`levi.builders.doors.project.DoorReport.continue_via`.
Graduation is a change of surface, never a rebuild.
"""

from __future__ import annotations

from levi.builders.doors import hicomb, hub, standalone
from levi.builders.doors.project import (
    DoorReport,
    GraduationMismatch,
    NotABuilderProject,
    Project,
    open_project,
)

DOORS = {
    "standalone": standalone,
    "hicomb": hicomb,
    "hub": hub,
}

__all__ = [
    "DOORS",
    "DoorReport",
    "GraduationMismatch",
    "NotABuilderProject",
    "Project",
    "hub",
    "hicomb",
    "open_project",
    "standalone",
]
