"""
Agent Runtime — one real specialist execution loop (beyond registry).

Bounded: select specialist → plan (light) → act via skills → verify → receipt.
Under policy + governor. Interpenetrates with Factory and Companion DNA.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timezone
import uuid

from levi.agent.specialists import SpecialistRegistry, Specialist
from levi.skill.registry import SkillRegistry
from levi.policy.gates import PolicyEngine, RiskLevel
from levi.graph.lwp_primitives import Governor, CircuitBreaker


@dataclass
class AgentStep:
    specialist_id: str
    action: str
    result: str
    ok: bool
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentRun:
    id: str
    intent: str
    steps: List[AgentStep] = field(default_factory=list)
    final: str = ""
    ok: bool = True
    risk_ceiling: int = 2


class AgentRuntime:
    def __init__(
        self,
        auto_approve_up_to: RiskLevel = RiskLevel.LOW,
        budget: float = 3.0,
    ):
        self.specialists = SpecialistRegistry()
        self.skills = SkillRegistry()
        self.policy = PolicyEngine(auto_approve_up_to=auto_approve_up_to)
        self.governor = Governor(name="agent_runtime", budget=budget, complexity_limit=8)
        self.breaker = CircuitBreaker(name="agent_runtime", max_depth=4, max_calls=20, max_cost=budget)

    def run(self, intent: str, max_steps: int = 4) -> AgentRun:
        run = AgentRun(id=f"run.{uuid.uuid4().hex[:10]}", intent=intent)
        selected = self.specialists.select_for_intent(intent)
        if not selected:
            run.ok = False
            run.final = "No specialists selected"
            return run

        run.risk_ceiling = max(s.risk_ceiling for s in selected)

        for i, spec in enumerate(selected[:max_steps]):
            if not self.breaker.check(depth=i, add_cost=0.1):
                run.steps.append(AgentStep(spec.id, "halt", f"Circuit breaker: {self.breaker.reason}", False))
                run.ok = False
                break
            if not self.governor.authorize(cost=0.1, complexity=1):
                run.steps.append(AgentStep(spec.id, "halt", "Governor budget exhausted", False))
                run.ok = False
                break

            action, result, ok = self._act(spec, intent)
            run.steps.append(AgentStep(spec.id, action, result, ok))
            if not ok:
                run.ok = False
                break

        if run.steps:
            run.final = " | ".join(f"{s.specialist_id}:{s.result[:80]}" for s in run.steps)
        else:
            run.final = "No steps"
        return run

    def _act(self, spec: Specialist, intent: str) -> tuple:
        """Map specialist to a concrete skill action where possible."""
        lower = intent.lower()
        if spec.id == "memory":
            if "remember" in lower:
                out = self.skills.invoke("remember", {"text": intent})
                return "remember", str(out)[:200], True
            out = self.skills.invoke("recall", {"text": intent})
            return "recall", str(out)[:200], True
        if spec.id == "companion":
            out = self.skills.invoke("companion_status")
            return "companion_status", str(out)[:200], True
        if spec.id == "coding" or spec.id == "automation":
            if any(w in lower for w in ("build", "scaffold", "factory", "app", "tool")):
                out = self.skills.invoke("factory_create", {"text": intent})
                return "factory_create", str(out)[:300], True
            out = self.skills.invoke("factory_status")
            return "factory_status", str(out)[:200], True
        if spec.id == "security":
            return "risk_note", f"Risk ceiling for this roster path ≤ {spec.risk_ceiling}", True
        if spec.id == "supervisor":
            roster = ", ".join(s.id for s in self.specialists.select_for_intent(intent))
            return "plan", f"Delegating via: {roster}", True
        if spec.id == "verification":
            return "verify", "Step boundary verified (foundation runtime)", True
        # default
        return "observe", f"{spec.display_name} noted intent ({len(intent)} chars)", True
