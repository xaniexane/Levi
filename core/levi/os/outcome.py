"""Outcome intake — state the outcome, get a skill-backed plan.

``state_outcome(text)`` decomposes plain language into ordered steps.
It is the Workflow Processor stage of the Automation Engine's HISTORIC
CANON (Chauncey's ruling 2026-09-22): outcome text becomes the step
workflow that the Logic Module, Routine Generator, and Execution Hub
(see levi.os.runner) then resolve and run.

LAW 1: every step is backed by a real pool skill, or planning fails loudly
with :class:`OSPlanError` naming the unplannable clauses. Steps are matched
with the shared pool's ``find_skill`` (trigger keywords), shaped to a rank
rung (the member's mastery rank when a member is given, else the provisional
default), and routed to a device by capability.

Decomposition is clause-based (v0.1): the outcome is split on sentence and
clause boundaries and each clause must match at least one skill. This is
deliberately conservative — an outcome the pool cannot cover is refused at
plan time, never hallucinated into fake steps.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.legion.skill_pool import find_skill, skill_at
from levi.legion.skill_pool.mastery import mastery_for

from levi.os.devices import Device, required_capabilities, route_step

__all__ = [
    "DEFAULT_RANK",
    "OSPlanError",
    "Plan",
    "PlanStep",
    "state_outcome",
]

#: Provisional default rung when no member mastery is recorded.
#: Chauncey's word on the default later.
DEFAULT_RANK = "II"

_CLAUSE_SPLIT = re.compile(r"[.!?;\n]+|\s*\bthen\b\s*", re.IGNORECASE)


class OSPlanError(ValueError):
    """Planning failed: the outcome (or part of it) has no backing skill."""


@dataclass
class PlanStep:
    step_id: str
    clause: str
    skill_id: str
    skill_name: str
    rank: str
    rank_description: str
    backend: str
    required_capabilities: List[str]
    device_id: Optional[str]
    executable_now: bool


@dataclass
class Plan:
    plan_id: str
    outcome_text: str
    steps: List[PlanStep] = field(default_factory=list)
    created_ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "outcome_text": self.outcome_text,
            "created_ts": self.created_ts,
            "steps": [vars(s) for s in self.steps],
        }


def _clauses(text: str) -> List[str]:
    parts = [p.strip(" ,") for p in _CLAUSE_SPLIT.split(text)]
    return [p for p in parts if p]


def state_outcome(
    text: str,
    member: Any = None,
    devices: Optional[List[Device]] = None,
) -> Plan:
    """Decompose an outcome statement into skill-backed plan steps.

    Raises :class:`OSPlanError` when the text is empty or any clause
    matches no pool skill. ``member`` (optional) is resolved through the
    mastery registry so steps use the member's own rank rungs.
    """
    text = (text or "").strip()
    if not text:
        raise OSPlanError("empty outcome — nothing to plan")

    clauses = _clauses(text)
    if not clauses:
        raise OSPlanError("empty outcome — nothing to plan")

    misses: List[str] = []
    scored: List[Dict[str, Any]] = []
    for clause in clauses:
        matches = find_skill(clause)
        if not matches:
            misses.append(clause)
            continue
        scored.append(matches[0])  # best trigger hit wins
    if misses:
        raise OSPlanError("no pool skill covers: " + "; ".join(repr(m) for m in misses))

    steps: List[PlanStep] = []
    for i, match in enumerate(scored):
        skill_id = match["id"]
        rank = DEFAULT_RANK
        if member is not None:
            held = mastery_for(member, skill_id)
            if held:
                rank = held
        shaped = skill_at(skill_id, rank)  # fails loudly on bad rank
        caps = sorted(required_capabilities(shaped["backend"]))
        device = route_step(set(caps), devices=devices)
        steps.append(
            PlanStep(
                step_id=f"s{i + 1}",
                clause=clauses[i],
                skill_id=skill_id,
                skill_name=shaped["name"],
                rank=rank,
                rank_description=shaped["rank_description"],
                backend=shaped["backend"],
                required_capabilities=caps,
                device_id=device.id if device else None,
                executable_now=bool(match.get("executable_now", True)),
            )
        )

    return Plan(
        plan_id="plan-" + uuid.uuid4().hex[:12],
        outcome_text=text,
        steps=steps,
        created_ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
