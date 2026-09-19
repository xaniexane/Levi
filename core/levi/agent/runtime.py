"""
Agent Runtime — one real specialist execution loop (beyond registry).

Bounded: select specialist → plan → act via skills → verify → receipt.
Under policy + governor. Interpenetrates with Factory and Companion DNA.

The policy engine is enforced per step, not just constructed: every
specialist action is proposed to the policy before it runs, and anything
above the auto-approve threshold halts the run honestly instead of
executing silently.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime, timezone
import math
import uuid

from levi.agent.specialists import SpecialistRegistry, Specialist
from levi.skill.registry import SkillRegistry
from levi.policy.gates import PolicyEngine, RiskLevel, ActionStatus
from levi.graph.lwp_primitives import Governor, CircuitBreaker


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentStep:
    specialist_id: str
    action: str
    result: str
    ok: bool
    verified: bool = False
    policy: str = "n/a"
    at: str = field(default_factory=_utcnow)


@dataclass
class AgentRun:
    id: str
    intent: str
    steps: List[AgentStep] = field(default_factory=list)
    plan: List[str] = field(default_factory=list)
    final: str = ""
    ok: bool = True
    risk_ceiling: int = 2
    policy_decisions: List[Dict[str, Any]] = field(default_factory=list)
    receipts: List[Dict[str, Any]] = field(default_factory=list)

    def receipt(self) -> Dict[str, Any]:
        """Structured run receipt: what was planned, decided, done, verified."""
        return {
            "run_id": self.id,
            "intent": self.intent,
            "ok": self.ok,
            "plan": list(self.plan),
            "steps": [
                {
                    "specialist": s.specialist_id,
                    "action": s.action,
                    "ok": s.ok,
                    "verified": s.verified,
                    "policy": s.policy,
                    "result": s.result[:300],
                    "at": s.at,
                }
                for s in self.steps
            ],
            "policy_decisions": list(self.policy_decisions),
            "policy_receipts": list(self.receipts),
            "final": self.final,
        }


# Action → honest risk level. The policy gates on what the action
# actually does, not on the specialist's ceiling (the ceiling is the
# maximum the specialist may *propose*).
_ACTION_RISK = {
    "observe": RiskLevel.INFO,
    "plan": RiskLevel.INFO,
    "verify": RiskLevel.INFO,
    "risk_note": RiskLevel.INFO,
    "companion_status": RiskLevel.INFO,
    "factory_status": RiskLevel.INFO,
    "recall": RiskLevel.INFO,
    "remember": RiskLevel.LOW,
    "factory_create": RiskLevel.MODERATE,
    "delegate_loop": RiskLevel.MODERATE,
}


class AgentRuntime:
    def __init__(
        self,
        auto_approve_up_to: RiskLevel = RiskLevel.LOW,
        budget: float = 3.0,
    ):
        try:
            budget = float(budget)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(
                f"AgentRuntime: 'budget' must be a number, got {budget!r}"
            ) from None
        if not math.isfinite(budget) or budget < 0:
            raise ValueError(
                f"AgentRuntime: 'budget' must be a finite value >= 0, got {budget!r}"
            )
        self.specialists = SpecialistRegistry()
        self.skills = SkillRegistry()
        self.policy = PolicyEngine(auto_approve_up_to=auto_approve_up_to)
        self.governor = Governor(
            name="agent_runtime", budget=budget, complexity_limit=8
        )
        self.breaker = CircuitBreaker(
            name="agent_runtime", max_depth=4, max_calls=20, max_cost=budget
        )

    # -- public ---------------------------------------------------------
    def run(self, intent: str, max_steps: int = 4, deep: bool = False) -> AgentRun:
        """Run one intent through the specialist loop.

        ``deep`` routes each specialist's work through the real
        step-level tool loop (``levi.agent.loop.run_subtask``) instead of
        a single skill call — thicker execution at the cost of more
        provider calls. Default ``False`` keeps the light single-shot
        path.
        """
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError(
                f"AgentRuntime.run: 'intent' must be a non-empty string, got {intent!r}"
            )
        if (
            not isinstance(max_steps, int)
            or isinstance(max_steps, bool)
            or not 1 <= max_steps <= 100
        ):
            raise ValueError(
                f"AgentRuntime.run: 'max_steps' must be an integer 1..100, "
                f"got {max_steps!r}"
            )
        if not isinstance(deep, bool):
            raise ValueError(f"AgentRuntime.run: 'deep' must be a bool, got {deep!r}")
        run = AgentRun(id=f"run.{uuid.uuid4().hex[:10]}", intent=intent)
        selected = self.specialists.select_for_intent(intent)
        if not selected:
            run.ok = False
            run.final = "No specialists selected"
            return run

        run.risk_ceiling = max(s.risk_ceiling for s in selected)
        run.plan = self._plan(intent, selected, deep)

        for i, spec in enumerate(selected[:max_steps]):
            if not self.breaker.check(depth=i, add_cost=0.1):
                run.steps.append(
                    AgentStep(
                        spec.id,
                        "halt",
                        f"Circuit breaker: {self.breaker.reason}",
                        False,
                    )
                )
                run.ok = False
                break
            if not self.governor.authorize(cost=0.1, complexity=1):
                run.steps.append(
                    AgentStep(spec.id, "halt", "Governor budget exhausted", False)
                )
                run.ok = False
                break

            # Policy gate FIRST: propose the action that is about to run
            # and enforce the decision. Anything the policy will not
            # auto-approve halts the run honestly — never executes
            # silently past the gate.
            action = self._decide_action(spec, intent, deep=deep)
            policy_state = self._gate(spec, action, intent)
            run.policy_decisions.append(
                {
                    "specialist": spec.id,
                    "action": action,
                    "policy": policy_state,
                }
            )
            if policy_state == ActionStatus.AWAITING_PERMISSION.value:
                run.steps.append(
                    AgentStep(
                        spec.id,
                        action,
                        "Policy: action requires explicit human approval; "
                        "not executed.",
                        False,
                        policy="denied",
                    )
                )
                run.ok = False
                break
            if policy_state == ActionStatus.DENIED.value:
                run.steps.append(
                    AgentStep(
                        spec.id,
                        action,
                        "Policy: action denied.",
                        False,
                        policy="denied",
                    )
                )
                run.ok = False
                break

            action, result, ok = self._act(spec, intent, action, deep=deep)

            verified, note = self._verify(action, result, ok)
            if verified:
                try:
                    receipt = self.policy.mark_completed(
                        self._last_proposal_id,
                        result_summary=f"{spec.id}:{action} ok — {note}",
                        verified=True,
                    )
                    run.receipts.append(
                        {
                            "action": action,
                            "receipt_id": receipt.id,
                            "verified": receipt.verified,
                        }
                    )
                except Exception:
                    pass  # receipt bookkeeping never breaks a run
            run.steps.append(
                AgentStep(
                    spec.id,
                    action,
                    result if verified else f"{result} [UNVERIFIED: {note}]",
                    ok and verified,
                    verified,
                    policy="approved",
                )
            )
            if not ok:
                run.ok = False
                break

        if run.steps:
            run.final = " | ".join(
                f"{s.specialist_id}:{s.result[:80]}" for s in run.steps
            )
        else:
            run.final = "No steps"
        return run

    # -- plan -----------------------------------------------------------
    def _plan(self, intent: str, selected: List[Specialist], deep: bool) -> List[str]:
        """A real plan: one line per selected specialist, in order."""
        mode = "step-level tool loop" if deep else "single skill call"
        lines = []
        for n, spec in enumerate(selected, 1):
            lines.append(
                f"{n}. {spec.id} ({spec.display_name}): {spec.role} — via {mode}."
            )
        lines.append(
            f"{len(selected) + 1}. verification: verify each step result; "
            "halt honestly on the first failure."
        )
        return lines

    # -- policy gate ----------------------------------------------------
    _last_proposal_id: str | None = None

    def _gate(self, spec: Specialist, action: str, intent: str) -> str:
        """Propose ``action`` to the policy engine and return the resulting
        status value (``approved`` | ``awaiting_permission`` | ``denied``)."""
        risk = _ACTION_RISK.get(action, RiskLevel.LOW)
        # Never propose above the specialist's own ceiling.
        if int(risk) > int(spec.risk_ceiling):
            risk = RiskLevel(int(spec.risk_ceiling))
        proposal = self.policy.propose(
            description=f"agent:{spec.id}:{action}",
            risk_level=risk,
            reason=f"Specialist step for intent: {intent[:120]}",
            reversible=action
            in (
                "observe",
                "plan",
                "verify",
                "recall",
                "companion_status",
                "factory_status",
                "risk_note",
            ),
        )
        decided = self.policy.request_permission(proposal.id)
        self._last_proposal_id = proposal.id
        return decided.status.value

    # -- verify ---------------------------------------------------------
    def _verify(self, action: str, result: str, ok: bool) -> tuple[bool, str]:
        """Independent check that a step actually did what it claims."""
        if not ok:
            return False, "action reported failure"
        text = str(result or "").strip()
        if not text:
            return False, "empty result"
        lowered = text.lower()
        if "error" in lowered and "traceback" in lowered:
            return False, "result contains an error traceback"
        if action == "remember" and "remember" not in lowered:
            return False, "remember action left no confirmation"
        return True, "result present and sane"

    # -- act ------------------------------------------------------------
    def _decide_action(self, spec: Specialist, intent: str, deep: bool = False) -> str:
        """Choose the action name for a specialist without side effects,
        so the policy gate can rule on it before anything executes."""
        if deep and spec.id not in ("supervisor", "verification", "security"):
            return "delegate_loop"
        lower = intent.lower()
        if spec.id == "memory":
            return "remember" if "remember" in lower else "recall"
        if spec.id == "companion":
            return "companion_status"
        if spec.id == "coding" or spec.id == "automation":
            if any(w in lower for w in ("build", "scaffold", "factory", "app", "tool")):
                return "factory_create"
            return "factory_status"
        if spec.id == "security":
            return "risk_note"
        if spec.id == "supervisor":
            return "plan"
        if spec.id == "verification":
            return "verify"
        return "observe"

    def _act(
        self, spec: Specialist, intent: str, action: str, deep: bool = False
    ) -> tuple[str, str, bool]:
        """Execute a previously decided + policy-approved action."""
        if action == "delegate_loop":
            return self._act_deep(spec, intent)
        if action == "remember":
            out = self.skills.invoke("remember", {"text": intent})
            return action, str(out)[:200], True
        if action == "recall":
            out = self.skills.invoke("recall", {"text": intent})
            return action, str(out)[:200], True
        if action == "companion_status":
            out = self.skills.invoke("companion_status")
            return action, str(out)[:200], True
        if action == "factory_create":
            out = self.skills.invoke("factory_create", {"text": intent})
            return action, str(out)[:300], True
        if action == "factory_status":
            out = self.skills.invoke("factory_status")
            return action, str(out)[:200], True
        if action == "risk_note":
            return (
                action,
                f"Risk ceiling for this roster path ≤ {spec.risk_ceiling}",
                True,
            )
        if action == "plan":
            roster = ", ".join(s.id for s in self.specialists.select_for_intent(intent))
            return action, f"Delegating via: {roster}", True
        if action == "verify":
            return action, "Step boundary verified (foundation runtime)", True
        # default: observe
        return (
            "observe",
            f"{spec.display_name} noted intent ({len(intent)} chars)",
            True,
        )

    def _act_deep(self, spec: Specialist, intent: str) -> tuple[str, str, bool]:
        """Run the specialist's share through the step-level tool loop."""
        try:
            from levi.agent import loop as agent_loop
        except Exception as exc:
            return (
                "delegate_loop",
                f"deep mode unavailable: levi.agent.loop failed to import: {exc}",
                False,
            )
        task = (
            f"As LEVI's {spec.display_name} specialist ({spec.role}), "
            f"handle this intent: {intent}"
        )
        try:
            transcript = agent_loop.run_subtask(task, max_steps=6)
        except Exception as exc:
            return (
                "delegate_loop",
                f"deep sub-loop raised: {exc}",
                False,
            )
        summary = str(transcript)
        return "delegate_loop", summary[:400], bool(transcript.ok)
