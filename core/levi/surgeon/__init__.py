"""LEVI Surgeon — snapshots, cleanup, advancement proposals, code surgery gate.

Original LEVI-native implementation. The concept (snapshot/revert,
propose→analyze→HITL→apply) is adapted from the Levi-ai Stage-1 lineage
(source-sync entry ``levi-ai``); no source text is copied.
"""

from .surgeon import (
    EXPORT_HEADERS,
    Advancement,
    SnapshotManager,
    apply_advancement,
    cleanup_code,
    default_owner_name,
    propose_advancements,
    stamp_header,
)
from .sandbox import SandboxGate, SandboxReport

__all__ = [
    "EXPORT_HEADERS",
    "Advancement",
    "SnapshotManager",
    "SandboxGate",
    "SandboxReport",
    "apply_advancement",
    "cleanup_code",
    "default_owner_name",
    "propose_advancements",
    "stamp_header",
]
