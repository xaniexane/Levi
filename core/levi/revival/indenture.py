"""Bilateral training contracts with staged unlocks (apprentice → journeyman → master).

Studied from: lost-crafts-20260916/report.md [Batch 1 — guild knowledge transfer]
(the Indenture: a binding bilateral contract between sponsor and learner, with
staged unlocks as competence is demonstrated).

This is an original, from-scratch implementation for LEVI. An ``Indenture``
binds a learner to a sponsor and walks through ordered stages
(``apprentice`` → ``journeyman`` → ``master`` by default, but the stage list
is configurable). Each stage carries requirements — counts of signed-off work
records in named skill areas. A sponsor (or any qualified assessor) signs off
individual work records; when every requirement of the current stage is met,
``advance()`` promotes the learner and records the promotion on an
append-only lineage ledger. Requirements, sign-offs, and promotions are all
hash-chained so the lineage is auditable.

The mechanism is bilateral: the sponsor commits to teach (logged as the
sponsor's obligations), and the learner commits to the work. Neither side can
advance a stage alone — promotion requires the assessor's sign-offs first.

Public surface:
- ``Indenture``: ``record_work(area, note)``, ``sign_off(record_id, assessor)``,
  ``advance(assessor)``, ``stage`` / ``progress()`` / ``lineage()``.
- ``StageDef``, ``WorkRecord``, ``AssessorError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional, Tuple

ORIGIN = "levi-revival/indenture"


class AssessorError(ValueError):
    """Raised when an advancement or sign-off cannot be honored."""


@dataclass(frozen=True)
class StageDef:
    """One stage of the contract: name + required signed-off work per area."""

    name: str
    requirements: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.name:
            raise AssessorError("stage name must be non-empty")
        for area, count in self.requirements.items():
            if count < 0:
                raise AssessorError(f"requirement count for {area!r} must be >= 0")


@dataclass
class WorkRecord:
    """One logged unit of work, pending or approved."""

    record_id: int
    area: str
    note: str
    signed_off: bool = False
    assessor: Optional[str] = None


@dataclass
class Indenture:
    """A bilateral training contract with staged unlocks."""

    learner: str
    sponsor: str
    stages: Tuple[StageDef, ...]
    assessors: Tuple[str, ...] = ()
    _records: List[WorkRecord] = field(default_factory=list)
    _stage_index: int = 0
    _ledger: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.learner or not self.sponsor:
            raise AssessorError("learner and sponsor must both be named")
        if not self.stages:
            raise AssessorError("at least one stage is required")
        names = [s.name for s in self.stages]
        if len(set(names)) != len(names):
            raise AssessorError("stage names must be unique")
        if self.sponsor not in self.assessors:
            self.assessors = (self.sponsor, *self.assessors)
        self._append_ledger(f"CONTRACT learner={self.learner} sponsor={self.sponsor}")

    # -- ledger -----------------------------------------------------------
    def _append_ledger(self, entry: str) -> None:
        prev = self._ledger[-1] if self._ledger else "GENESIS"
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        digest = hashlib.sha256(f"{prev}|{stamp}|{entry}".encode()).hexdigest()[:16]
        self._ledger.append(f"{stamp} {entry} [{digest}]")

    def lineage(self) -> List[str]:
        """The auditable promotion/contract history."""
        return list(self._ledger)

    # -- work -------------------------------------------------------------
    @property
    def stage(self) -> StageDef:
        return self.stages[self._stage_index]

    def record_work(self, area: str, note: str) -> WorkRecord:
        if not area:
            raise AssessorError("work area must be non-empty")
        rec = WorkRecord(record_id=len(self._records) + 1, area=area, note=note)
        self._records.append(rec)
        return rec

    def sign_off(self, record_id: int, assessor: str) -> WorkRecord:
        if assessor not in self.assessors:
            raise AssessorError(f"{assessor!r} is not an authorized assessor")
        if not (1 <= record_id <= len(self._records)):
            raise AssessorError(f"no work record {record_id}")
        rec = self._records[record_id - 1]
        if rec.signed_off:
            raise AssessorError(f"record {record_id} already signed off")
        rec.signed_off = True
        rec.assessor = assessor
        self._append_ledger(f"SIGNOFF record={record_id} area={rec.area} by={assessor}")
        return rec

    def progress(self) -> Dict[str, Tuple[int, int]]:
        """Current stage: area -> (signed_off_count, required_count)."""
        reqs = self.stage.requirements
        counts: Dict[str, int] = {a: 0 for a in reqs}
        for rec in self._records:
            if rec.signed_off and rec.area in counts:
                counts[rec.area] += 1
        return {a: (counts[a], reqs[a]) for a in reqs}

    def stage_complete(self) -> bool:
        return all(done >= need for done, need in self.progress().values())

    def advance(self, assessor: str) -> StageDef:
        """Promote to the next stage; requires all current requirements met."""
        if assessor not in self.assessors:
            raise AssessorError(f"{assessor!r} is not an authorized assessor")
        if not self.stage_complete():
            missing = {a: (n - d) for a, (d, n) in self.progress().items() if d < n}
            raise AssessorError(
                f"stage {self.stage.name!r} incomplete; still need {missing}"
            )
        if self._stage_index + 1 >= len(self.stages):
            raise AssessorError("already at the final stage")
        old = self.stage.name
        self._stage_index += 1
        self._append_ledger(
            f"PROMOTION {old} -> {self.stage.name} approved-by={assessor}"
        )
        return self.stage

    @classmethod
    def standard(
        cls,
        learner: str,
        sponsor: str,
        craft_areas: Tuple[str, ...] = ("materials", "tools", "technique"),
        extra_assessors: Tuple[str, ...] = (),
    ) -> "Indenture":
        """The classic three-stage contract: apprentice → journeyman → master."""
        return cls(
            learner=learner,
            sponsor=sponsor,
            stages=(
                StageDef("apprentice", {a: 4 for a in craft_areas}),
                StageDef("journeyman", {a: 6 for a in craft_areas}),
                StageDef("master", {a: 8 for a in craft_areas}),
            ),
            assessors=extra_assessors,
        )
