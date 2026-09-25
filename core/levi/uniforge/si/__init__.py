"""UniForge native SI core — the planner and executor.

This is the authoritative core. It imports nothing from
:mod:`levi.uniforge.ai` (the AI counterpart bridge); the bridge is a
conventional-protocol interface and claims nothing the core does not do.
stdlib only.
"""

from __future__ import annotations

from .executor import forge, forge_dry_run
from .planner import assemble_plan, plan_readiness

__all__ = ["assemble_plan", "plan_readiness", "forge", "forge_dry_run"]
