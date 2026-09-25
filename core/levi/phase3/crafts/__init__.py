"""C9 crafts pedagogy — the school for the minds (WORKING TITLE: naming is Chauncey's).

A staged apprenticeship curriculum for raising agents: indenture
(staged capability unlocks), Sloyd lessons (exactly one new variable
per lesson), compagnonnage (forced rotation across the four loop
roles), and chef-d'oeuvre (a graduation piece judged by a battery).

Plain rules:
- ``attempt()`` enforces stage gating: a capability the agent's stage
  has not unlocked is a receipted FAULT (a curriculum fact, not a
  permission denial), never an execution.
- Lessons name their single new variable; failures diagnose the new
  variable first.
- Rotations cover perceiver, reasoner, actor, verifier in fixed order.
- ``graduate()`` requires all rotations, a passed exit battery, and a
  chef-d'oeuvre piece that passes the judged battery. Double-failed
  exit batteries demote.
- Deterministic: apprentice records serialize byte-identically;
  timestamps live only inside receipts, never in record state.

No sentience or subjective-experience claims anywhere: an apprentice
record is a training log, not a childhood.
"""

from __future__ import annotations

from .curriculum import (
    ApprenticeRecord,
    Lesson,
    Stage,
    default_curriculum,
)
from .gates import (
    CapabilityGate,
    Fault,
    LocalGate,
    attempt,
    unlocked_capabilities,
)
from .school import (
    ROTATION_ROLES,
    complete_lesson,
    complete_rotation,
    diagnose_failure,
    graduate,
    record_lesson_failure,
    run_exit_battery,
)

__all__ = [
    "ApprenticeRecord",
    "CapabilityGate",
    "Fault",
    "Lesson",
    "LocalGate",
    "ROTATION_ROLES",
    "Stage",
    "attempt",
    "complete_lesson",
    "complete_rotation",
    "default_curriculum",
    "diagnose_failure",
    "graduate",
    "record_lesson_failure",
    "run_exit_battery",
    "unlocked_capabilities",
]
