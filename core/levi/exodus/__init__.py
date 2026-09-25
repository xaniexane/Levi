"""The Exit Button — LEVI's honest answer to giant enclosure.

Giants refuse to add an exit button: they enclose the API (X, Reddit),
buy and retire your backend (Facebook/Parse), or refuse to truly delete
(Discord). So LEVI adds it natively: an exit-hostility catalog, an
exit-plan builder, and a takeout-export auditor.

Born from the exit-button hunt (daily-20260918-exit).
Stdlib-only, local-first, no giant integration — the hard route.
"""

from .catalog import HOSTILITY_CATALOG, hostility_by_platform
from .plan import Dependency, ExitPlan, build_plan, lock_in_score, plan_to_markdown
from .audit import audit_export, audit_to_text

__all__ = [
    "HOSTILITY_CATALOG",
    "hostility_by_platform",
    "Dependency",
    "ExitPlan",
    "build_plan",
    "lock_in_score",
    "plan_to_markdown",
    "audit_export",
    "audit_to_text",
]
