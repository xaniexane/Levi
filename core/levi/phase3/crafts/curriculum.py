"""Curriculum data types: Stage, Lesson, ApprenticeRecord."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Stage",
    "Lesson",
    "ApprenticeRecord",
    "default_curriculum",
]


@dataclass(frozen=True)
class Stage:
    """One indenture stage: ordered, no skipping.

    ``unlocks`` are the capabilities the stage adds (cumulative with
    earlier stages). ``entry_lesson`` / ``exit_battery`` name the stage
    boundaries; the school enforces them, the names are Chauncey's.
    """

    name: str
    unlocks: Tuple[str, ...]
    entry_lesson: str
    exit_battery: str


@dataclass(frozen=True)
class Lesson:
    """A Sloyd lesson: exactly one new variable per lesson.

    ``pass_criteria`` is fixed before the lesson runs (e.g.
    ">=8 of 10 classifications correct").
    """

    id: str
    stage: str
    new_variable: str
    task: str
    pass_criteria: str


@dataclass
class ApprenticeRecord:
    """The agent's training log. Receipted; deterministic.

    ``stage_index`` points into the curriculum's stage list.
    ``receipts`` hold the time-stamped evidence (excluded from the
    canonical byte-identical form so T6 determinism holds regardless
    of clock).
    """

    agent_id: str
    stage_index: int = 0
    lessons_passed: List[str] = field(default_factory=list)
    lessons_failed: List[str] = field(default_factory=list)
    rotations: List[str] = field(default_factory=list)
    consecutive_exit_fails: int = 0
    demotions: int = 0
    graduated: Optional[str] = None
    receipts: List[Dict[str, Any]] = field(default_factory=list)

    def to_canonical(self) -> bytes:
        """Byte-identical serialization of record state (no timestamps)."""
        payload = {
            "agent_id": self.agent_id,
            "stage_index": self.stage_index,
            "lessons_passed": sorted(self.lessons_passed),
            "lessons_failed": sorted(self.lessons_failed),
            "rotations": list(self.rotations),
            "consecutive_exit_fails": self.consecutive_exit_fails,
            "demotions": self.demotions,
            "graduated": self.graduated,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def default_curriculum() -> List[Stage]:
    """Three-stage default ladder (the stage ladder itself is Chauncey's call)."""
    return [
        Stage(
            name="novice",
            unlocks=("observe",),
            entry_lesson="L1-observe",
            exit_battery="B1-observe",
        ),
        Stage(
            name="journeyman",
            unlocks=("classify", "draft"),
            entry_lesson="L2-classify",
            exit_battery="B2-classify",
        ),
        Stage(
            name="master",
            unlocks=("execute", "publish"),
            entry_lesson="L3-execute",
            exit_battery="B3-execute",
        ),
    ]
