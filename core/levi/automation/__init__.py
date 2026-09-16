"""LEVI automation — plans, primitives, and device bridges.

Original LEVI-native implementation. Browser/CDP concepts adapted from
the Levi-ai Stage-1 lineage (source-sync entry ``levi-ai``); no source
text copied.

Boundary (binding): this package PLANS automation and emits helper
scripts. It never drives a browser or device on its own — execution is
always the user's action (Termux/CDP/device) or a HITL-gated step.
"""

from .browser import BrowserPlan, emit_termux_helper, format_plan, plan_browser_job
from .primitives import PRIMITIVES, Primitive, get_primitive, list_primitives

__all__ = [
    "BrowserPlan",
    "PRIMITIVES",
    "Primitive",
    "emit_termux_helper",
    "format_plan",
    "get_primitive",
    "list_primitives",
    "plan_browser_job",
]
