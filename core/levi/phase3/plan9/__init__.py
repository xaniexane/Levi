"""plan9 — Plan 9 interface discipline. WORKING TITLE.

Naming is Chauncey's; this name is never canon.  One verb set
(``read`` / ``write`` / ``list`` / ``run`` / ``watch``) over per-task
namespaces: least-privilege isolation with a single uniform audit
surface.
"""

from .namespace import (
    VERBS,
    Capability,
    DirectDispatch,
    DispatchError,
    Mount,
    Namespace,
    OpResult,
    Plan9Fault,
    audit_log,
    clear_audit_log,
    compose_namespace,
    operate,
)

__all__ = [
    "VERBS",
    "Capability",
    "DirectDispatch",
    "DispatchError",
    "Mount",
    "Namespace",
    "OpResult",
    "Plan9Fault",
    "audit_log",
    "clear_audit_log",
    "compose_namespace",
    "operate",
]
