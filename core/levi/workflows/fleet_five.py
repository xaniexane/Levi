"""fleet-five: capped delegation — at most 5 specialists, one folded report.

The fleet pattern, LEVI-native (no external identity): a task too small to
decompose still deserves disciplined parallel thinking, so LEVI convenes a
*fleet* of at most FIVE specialists, each contributing exactly ONE section,
then folds all sections into ONE report and disbands the fleet. No standing
army: after the fold there is no fleet state left behind — no persistent
agents, no side registries, no residue. The only durable output is the
report the caller keeps.

Roles (fixed order of contribution):

  architect     — interfaces, plan, decomposition of the task
  implementer   — the smallest working slice (minimum viable construction)
  critic        — weaknesses: what breaks, what's wrong, what kills it
  scope_warden  — scope freeze: what is IN, what is OUT, and the boundary
  scribe        — digest: the folded summary the caller acts on

Honesty machinery:

  HARD CAP      — requesting a 6th specialist raises FleetError (a
                  ValueError): the cap is structural, never silently bent.
  NO TRUNCATION — a task that needs more than 5 specialists is REFUSED with
                  guidance to split it into smaller tasks (one fleet per
                  piece), never silently truncated to fit.
  OFFLINE       — sections are supplied by the caller (the real specialists:
                  subagents, operators, or fixtures). This module folds them;
                  it never fabricates a specialist's contribution.

Steps: summon (validate cap + specs) -> <one step per specialist> -> fold.
The fold step assembles the single report; disbanding is implicit (nothing
is written to the home dir).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._common import (
    emit,
    finish_step,
    new_step,
    resolve_home,
    workflow_result,
)

NAME = "fleet-five"
SUMMARY = (
    "Capped delegation: at most 5 specialists (architect -> implementer -> "
    "critic -> scope_warden -> scribe) each contribute exactly one section; "
    "the workflow folds them into ONE report and the fleet disbands — no "
    "persistent state left behind. A 6th specialist is refused; a task too "
    "big for 5 is refused with split guidance, never truncated."
)
STEP_NAMES = [
    "summon",
    "architect",
    "implementer",
    "critic",
    "scope_warden",
    "scribe",
    "fold",
]

MAX_SPECIALISTS = 5

VALID_ROLES = ("architect", "implementer", "critic", "scope_warden", "scribe")

# Expected contribution order — a fleet walks the roles in this order.
ROLE_ORDER = VALID_ROLES

ROLE_MANDATES = {
    "architect": "interfaces, plan, and decomposition of the task",
    "implementer": "the smallest working slice that actually works",
    "critic": "weaknesses — what breaks, what is wrong, what kills the slice",
    "scope_warden": "scope freeze — what is IN, what is OUT, the boundary",
    "scribe": "digest — the folded summary the caller acts on",
}

LARGE_TASK_SCOPE = "large"  # task_size value that triggers split guidance


class FleetError(ValueError):
    """Clear error for fleet-five violations: cap breaches and oversize tasks."""


def _validate_spec(spec: Any, index: int) -> Dict[str, Any]:
    """Validate one specialist spec; raise FleetError on any defect."""
    if not isinstance(spec, dict):
        raise FleetError(
            "specialist #%d: spec must be a dict with a 'role' key "
            "(got %s)" % (index, type(spec).__name__)
        )
    role = spec.get("role")
    if role not in VALID_ROLES:
        raise FleetError(
            "specialist #%d: role must be one of %s (got %r)"
            % (index, ", ".join(VALID_ROLES), role)
        )
    contribution = spec.get("contribution")
    if contribution is None:
        raise FleetError(
            "specialist #%d (%s): no 'contribution' supplied — "
            "fleet-five folds real contributions; it never fabricates them. "
            "Pass the specialist's section text as contribution=..." % (index, role)
        )
    if not isinstance(contribution, str) or not contribution.strip():
        raise FleetError(
            "specialist #%d (%s): contribution must be a non-empty string"
            % (index, role)
        )
    focus = spec.get("focus", "")
    if focus is not None and not isinstance(focus, str):
        raise FleetError(
            "specialist #%d (%s): 'focus' must be a string or omitted" % (index, role)
        )
    return {"role": role, "focus": focus or "", "contribution": contribution}


def _check_task(task: Any, task_size: Optional[str]) -> str:
    """Validate the task; refuse oversize tasks with split guidance."""
    if not isinstance(task, str) or not task.strip():
        raise FleetError(
            "empty task — fleet-five convenes a fleet FOR something; "
            'pass task="..." describing the work.'
        )
    if task_size is not None and not isinstance(task_size, str):
        raise FleetError(
            "task_size must be a string or None (got %r)" % (type(task_size).__name__,)
        )
    if task_size == LARGE_TASK_SCOPE:
        raise FleetError(
            "task refused: declared 'large' — too big for a fleet of 5. "
            "Split it into smaller sub-tasks (each honestly needing at most "
            "5 specialists) and run one fleet-five per sub-task; fold the "
            "sub-reports yourself. LEVI never silently truncates a task to "
            "fit the cap."
        )
    return task.strip()


def _check_specialists(specialists: Any) -> List[Dict[str, Any]]:
    """Validate the specialist list; enforce the HARD CAP."""
    if not isinstance(specialists, (list, tuple)):
        raise FleetError(
            "specialists must be an ordered list of role specs "
            "(got %s)" % type(specialists).__name__
        )
    if len(specialists) == 0:
        raise FleetError(
            "no specialists — a fleet of zero is just a report with no "
            "sections; pass 1-%d role specs." % MAX_SPECIALISTS
        )
    if len(specialists) > MAX_SPECIALISTS:
        raise FleetError(
            "HARD CAP: requested %d specialists, the fleet convenes at most "
            "%d. Remove %d or split the task into sub-tasks (one fleet per "
            "sub-task) — LEVI will not silently drop specialists."
            % (len(specialists), MAX_SPECIALISTS, len(specialists) - MAX_SPECIALISTS)
        )
    validated = [_validate_spec(spec, i) for i, spec in enumerate(specialists)]
    roles = [s["role"] for s in validated]
    if len(set(roles)) != len(roles):
        dupes = sorted({r for r in roles if roles.count(r) > 1})
        raise FleetError(
            "duplicate roles (%s) — each specialist contributes exactly one "
            "section; a role appears at most once per fleet." % ", ".join(dupes)
        )
    order = {r: i for i, r in enumerate(ROLE_ORDER)}
    validated.sort(key=lambda s: order[s["role"]])
    return validated


def _make_section(spec: Dict[str, Any], task: str, index: int) -> Dict[str, Any]:
    """Each specialist contributes exactly one section."""
    role = spec["role"]
    return {
        "index": index,
        "role": role,
        "mandate": ROLE_MANDATES[role],
        "focus": spec["focus"],
        "content": spec["contribution"],
    }


def _fold_report(task: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fold every section into ONE report dict; the fleet then disbands."""
    digest = ""
    scribes = [s for s in sections if s["role"] == "scribe"]
    if scribes:
        digest = scribes[-1]["content"]
    return {
        "report": "fleet-five",
        "task": task,
        "fleet_size": len(sections),
        "sections": sections,
        "digest": digest,
        "roles_present": [s["role"] for s in sections],
        "roles_missing": [
            r for r in VALID_ROLES if r not in {s["role"] for s in sections}
        ],
        "folded": True,  # the fleet is gone; this report is all that remains
    }


def run_fleet(
    task: str, specialists: List[Dict[str, Any]], task_size: Optional[str] = None
) -> Dict[str, Any]:
    """Convene a capped fleet, fold its sections, disband.

    Returns the single folded report dict. Raises FleetError (a ValueError)
    on: empty task, oversize task (needs > 5), empty/malformed specialist
    list, or a 6th+ specialist. Writes nothing anywhere — the fold leaves no
    state behind.
    """
    clean_task = _check_task(task, task_size)
    specs = _check_specialists(specialists)
    sections = [_make_section(s, clean_task, i) for i, s in enumerate(specs)]
    return _fold_report(clean_task, sections)


def run(
    home=None,
    task: Optional[str] = None,
    specialists: Optional[List[Dict[str, Any]]] = None,
    task_size: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    levi_home = resolve_home(home)
    emit("workflow.start", {"workflow": NAME, "home": str(levi_home)})
    steps: List[Dict[str, Any]] = []
    artifacts: Dict[str, Any] = {}

    # -- summon: validate cap + specs ------------------------------------
    step = new_step("summon")
    try:
        clean_task = _check_task(task, task_size)
        specs = _check_specialists(specialists)
    except FleetError as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False, "refused": True})
        return workflow_result(NAME, steps, artifacts)
    finish_step(
        step, True, {"fleet_size": len(specs), "roles": [s["role"] for s in specs]}
    )
    steps.append(step)

    # -- one step per specialist, in role order ---------------------------
    sections: List[Dict[str, Any]] = []
    for i, spec in enumerate(specs):
        step = new_step(spec["role"])
        try:
            section = _make_section(spec, clean_task, i)
        except Exception as exc:  # pragma: no cover — defensive
            finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
            steps.append(step)
            emit("workflow.done", {"workflow": NAME, "ok": False})
            return workflow_result(NAME, steps, artifacts)
        sections.append(section)
        finish_step(
            step, True, {"section": section["index"], "chars": len(section["content"])}
        )
        steps.append(step)

    # -- fold: one report; the fleet disbands ----------------------------
    step = new_step("fold")
    report = _fold_report(clean_task, sections)
    artifacts["report"] = report
    finish_step(step, True, {"sections": len(sections), "state_left_behind": None})
    steps.append(step)

    emit(
        "workflow.done",
        {"workflow": NAME, "ok": True, "fleet_size": len(sections), "folded": True},
    )
    return workflow_result(NAME, steps, artifacts)
