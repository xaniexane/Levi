"""Context snapshots — suspend/resume for life.

One command captures the full working state so any interruption is
resumable: open commitments, open tracked items, the git working state
of a target repo, recent growth-journal entries, and the active
focus/mode. Stored as JSON under the LEVI home (resolved at call
time, never import time).

Honest contract: a snapshot reports exactly what was found. Stores
that do not exist yet are recorded as ``none`` — never invented.
"""

from .store import (
    SnapshotStore,
    capture,
    drop,
    list_snapshots,
    resume,
    resume_brief,
)

__all__ = [
    "SnapshotStore",
    "capture",
    "drop",
    "list_snapshots",
    "resume",
    "resume_brief",
    # Stage snapshots — versioned, sealed, restorable artifact captures
    # (boot camp stages; the ops-snapshot legion service).
    "StageSnapshot",
    "StageStore",
    "capture_stage",
    "diff_stage_snapshots",
    "fork_stage_snapshot",
    "implement_stage_snapshot",
    "materialize_stage",
    "recreate_stage_snapshot",
    "restore_stage_snapshot",
    "verify_stage_chain",
]

from levi.snapshots.stages import (  # noqa: E402
    StageSnapshot,
    StageStore,
    capture as capture_stage,
    diff_snapshots as diff_stage_snapshots,
    fork_snapshot as fork_stage_snapshot,
    implement_snapshot as implement_stage_snapshot,
    materialize as materialize_stage,
    recreate_snapshot as recreate_stage_snapshot,
    restore_snapshot as restore_stage_snapshot,
    verify_chain as verify_stage_chain,
)
