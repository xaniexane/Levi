"""UniForge native planner — assemble BuildPlans from targets.

The planner is pure: it orders steps, checks tool readiness, and
describes what *would* run. Execution lives in
:mod:`levi.uniforge.si.executor`. stdlib only; never imports the
AI counterpart bridge.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..plan import BuildPlan
from ..targets import make_steps, target_ids, validate_target_ids


def assemble_plan(
    target_list: List[str],
    workdir: str,
    name: str = "",
) -> BuildPlan:
    """Build a :class:`BuildPlan` for the requested targets.

    Raises ``ValueError`` for unknown target ids. Steps keep their
    declared order per target and are topologically ordered across
    targets by :meth:`BuildPlan.ordered_steps`.
    """
    ids = validate_target_ids(target_list)
    plan_name = name or "forge-" + "-".join(ids)
    steps = []
    for tid in ids:
        steps.extend(make_steps(tid, workdir, plan_name))
    plan = BuildPlan(name=plan_name, targets=ids, steps=steps)
    # Fail fast: an unorderable plan must never reach the executor.
    plan.ordered_steps()
    return plan


def plan_readiness(plan: BuildPlan) -> Dict[str, Any]:
    """Readiness report: hermetic checks + tool status + target ids.

    Returns ``{"ready": bool, ...}``; ``ready`` is True only when every
    required tool is present and the plan orders cleanly.
    """
    checks = plan.hermetic_checks()
    missing = checks["tools_missing"]
    ready = checks["steps_orderable"] and not missing
    return {
        "ready": ready,
        "plan": plan.name,
        "targets": list(plan.targets),
        "known_target_ids": target_ids(),
        "step_count": len(plan.steps),
        "tools_present": checks["tools_present"],
        "tools_missing": missing,
        "checks": checks,
    }
