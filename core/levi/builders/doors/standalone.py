"""Door 1 — standalone: general / low-production / simple users.

One call, sensible defaults, zero duplicated engine logic. Everything
below delegates to :func:`levi.builders.pipeline.build` — the single
shared engine. The door is a surface: it names the demand class it
serves and tags the report, nothing more.
"""

from __future__ import annotations

from typing import Optional

from levi.builders.doors.project import DoorReport, Project, open_project
from levi.builders.economy import BuildLedger
from levi.builders.pipeline import build as _engine_build

DOOR_NAME = "standalone"
DEMAND_CLASS = "general / low-production / simple"


def build_simple(
    prompt: str,
    workdir: Optional[str] = None,
    ledger: Optional[BuildLedger] = None,
) -> DoorReport:
    """Scaffold a simple project through the standalone door.

    Same engine as every other door — the report's ``door`` tag is the
    only thing this function adds.
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
    "build_simple",
    "open_project",
]
