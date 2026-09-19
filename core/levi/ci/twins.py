"""Agent-twin interface for the CI counsels.

Keeper's canon (2026-09-18): "The minions are actually agents — ai and si
xi — twins of each, being 2 bodies and minds, or a left and right sided
brain."

Ontology:
- Every catalog row is a frozen intake record (``Minion`` — never renamed,
  never churned). The LIVING entity is the Agent: one agent per row id,
  classed AI / SI / XI.
- Every agent is a twin pair: left brain + right brain = 2 bodies,
  2 minds. Left = sequence/logic/execution mind; right =
  pattern/variation/intuition mind.
- Merge/judge: the pair must converge to one action. Hard divergences
  escalate to the class counsel; what counsel cannot settle escalates to
  the keeper. Resolutions feed the growth loop as training signal.

The agent twin-pair layer itself lives on the twins/ pair machinery and
is built in parallel — this module is the counsel side of the contract:
intake takes agent id + hemisphere positions, verdicts are per-agent and
delivered to both hemispheres.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from levi.ci.counsel import Case, CloudCounsel, Verdict

#: The two hemispheres. Left sequences, right patterns.
HEMISPHERES = ("left", "right")

_LEFT_MIND = "sequence/logic/execution"
_RIGHT_MIND = "pattern/variation/intuition"


@dataclass(frozen=True)
class HemispherePosition:
    """Where one hemisphere stands on the case."""

    side: str  # "left" | "right"
    stance: str  # the action/judgment this hemisphere favors
    reasoning: str = ""

    def __post_init__(self) -> None:
        if self.side not in HEMISPHERES:
            raise ValueError(f"hemisphere must be left|right, got {self.side!r}")

    def mind(self) -> str:
        return _LEFT_MIND if self.side == "left" else _RIGHT_MIND


@dataclass
class AgentCase:
    """A hard case escalated for one agent-twin pair."""

    agent_id: str
    agent_class: str
    question: str
    left: HemispherePosition
    right: HemispherePosition
    stakes: str = "routine"
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def diverged(self) -> bool:
        return self.left.stance != self.right.stance

    def to_case(self) -> Case:
        """Flatten to a counsel Case carrying both hemisphere positions."""
        question = self.question
        if self.diverged:
            question = (
                f"{self.question} | DIVERGENCE — left ({_LEFT_MIND}) holds "
                f"'{self.left.stance}'; right ({_RIGHT_MIND}) holds "
                f"'{self.right.stance}'."
            )
        return Case(
            minion_id=self.agent_id,
            minion_class=self.agent_class,
            question=question,
            context={
                **self.context,
                "agent_id": self.agent_id,
                "diverged": self.diverged,
                "left_stance": self.left.stance,
                "right_stance": self.right.stance,
            },
            stakes=self.stakes,
        )


def _render_for_hemisphere(verdict: Verdict, side: str) -> Dict[str, str]:
    """Render the verdict legible to one hemisphere's mind."""
    if side == "left":
        return {
            "side": "left",
            "mind": _LEFT_MIND,
            "reading": (
                f"Ordered execution of counsel's advice '{verdict.ruling}': "
                f"1) take the ruling as the next step; 2) apply conditions "
                f"in order ({len(verdict.conditions)}); 3) converge the pair "
                f"to the single action and report back."
            ),
        }
    return {
        "side": "right",
        "mind": _RIGHT_MIND,
        "reading": (
            f"Pattern counsel holds for '{verdict.ruling}': the variant space "
            f"around this advice was walked (echo branches, phantom advices); "
            f"the retained signal compresses to this one shape — "
            f"'{verdict.ruling}'."
        ),
    }


def deliver_to_hemispheres(verdict: Verdict, agent_case: AgentCase) -> Verdict:
    """Deliver the verdict to both hemispheres. Same ruling, mind-legible."""
    verdict.agent_id = agent_case.agent_id
    verdict.hemispheres = HEMISPHERES
    verdict.delivery = {
        side: _render_for_hemisphere(verdict, side) for side in HEMISPHERES
    }
    if agent_case.diverged:
        verdict.divergence = {
            "left_stance": agent_case.left.stance,
            "left_reasoning": agent_case.left.reasoning,
            "right_stance": agent_case.right.stance,
            "right_reasoning": agent_case.right.reasoning,
            "resolved_by": verdict.counsel,
            "resolution": verdict.ruling,
        }
    return verdict


def arbitrate_agent_case(
    counsel_obj: CloudCounsel, agent_case: AgentCase
) -> Verdict:
    """Deliberate an agent-twin case; arbitrate divergences; know the ceiling.

    The counsel settles what it can. When a critical-stakes divergence ends
    in hold-for-human/refuse, the verdict is flagged ``escalate_to_keeper``:
    the pair's hard ceiling is the keeper, not the counsel. Counsel advises;
    the keeper decides.
    """
    verdict = counsel_obj.deliberate(agent_case.to_case())
    verdict = deliver_to_hemispheres(verdict, agent_case)
    if (
        agent_case.diverged
        and agent_case.stakes == "critical"
        and verdict.ruling in ("hold-for-human", "refuse")
    ):
        verdict.escalate_to_keeper = True
        verdict.rationale += (
            " | CEILING: critical divergence unsettled — escalates to the "
            "keeper. Counsel advises; the keeper decides."
        )
    return verdict
