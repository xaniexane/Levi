"""Capability gating: attempt() + CapabilityGate protocol + local stub.

Locked capabilities produce receipted FAULTs — a curriculum fact, not
a permission denial. The middle team's minds consume this gate via the
``CapabilityGate`` protocol; until it is pinned, use ``LocalGate``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Sequence, Set, Tuple

from .curriculum import ApprenticeRecord, Stage

__all__ = [
    "CapabilityGate",
    "Fault",
    "LocalGate",
    "attempt",
    "unlocked_capabilities",
]


@dataclass(frozen=True)
class Fault:
    """A receipted fault: a locked capability was attempted."""

    kind: str = "fault"
    agent_id: str = ""
    capability: str = ""
    stage: str = ""
    reason: str = "capability locked by curriculum"


class CapabilityGate(Protocol):
    """Protocol the middle team's minds implement to execute tasks."""

    def execute(self, capability: str, task: object) -> object: ...


class LocalGate:
    """Local stub gate: executes the task callable immediately."""

    def execute(self, capability: str, task: Callable[[], object]) -> object:
        return task()


def unlocked_capabilities(
    record: ApprenticeRecord, stages: Sequence[Stage]
) -> Set[str]:
    """Cumulative unlocks for the record's current stage."""
    caps: Set[str] = set()
    for stage in stages[: record.stage_index + 1]:
        caps.update(stage.unlocks)
    return caps


def _receipt(record: ApprenticeRecord, now: Optional[float], **fields) -> None:
    stamp = time.time() if now is None else now
    entry = {"ts": stamp, "agent_id": record.agent_id}
    entry.update(fields)
    record.receipts.append(entry)


def attempt(
    record: ApprenticeRecord,
    stages: Sequence[Stage],
    capability: str,
    task: Callable[[], object],
    gate: Optional[CapabilityGate] = None,
    now: Optional[float] = None,
) -> Tuple[bool, object]:
    """Try to exercise ``capability`` under stage gating.

    Returns ``(True, result)`` when unlocked and executed,
    ``(False, Fault)`` when locked. Locked attempts NEVER execute the
    task callable (T1: zero executions).
    """
    if capability in unlocked_capabilities(record, stages):
        result = (gate or LocalGate()).execute(capability, task)
        _receipt(
            record,
            now,
            kind="attempt_ok",
            capability=capability,
            stage=stages[record.stage_index].name,
        )
        return True, result
    fault = Fault(
        agent_id=record.agent_id,
        capability=capability,
        stage=stages[record.stage_index].name,
    )
    _receipt(
        record,
        now,
        kind="fault",
        capability=capability,
        stage=fault.stage,
        reason=fault.reason,
    )
    return False, fault


def stage_names(record: ApprenticeRecord, stages: Sequence[Stage]) -> List[str]:
    return [s.name for s in stages[: record.stage_index + 1]]
