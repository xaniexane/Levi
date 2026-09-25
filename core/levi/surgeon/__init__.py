"""LEVI Surgeon — snapshots, cleanup, advancement proposals, code surgery gate.

Original LEVI-native implementation. The concept (snapshot/revert,
propose→analyze→HITL→apply) is adapted from the Levi-ai Stage-1 lineage
(source-sync entry ``levi-ai``); no source text is copied.

The canonical Triple Threat Elite core — the host-agnostic port of
Chauncey's original ``levi_surgeon.js`` — lives in
:mod:`levi.surgeon.triple_threat`. The top-level names exported here are
the earlier LEVI-native variants, kept working.
"""

from . import triple_threat
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
    "triple_threat",
]
