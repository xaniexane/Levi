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
]
