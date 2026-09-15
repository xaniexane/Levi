"""
Agent Specialist Registry
Bounded roster of specialists drawn from Global Enterprise + Advanced Agentic DNA.
Specialists are selected by orchestration; they do not self-spawn unbound.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Specialist:
    id: str
    display_name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    default_tools: List[str] = field(default_factory=list)
    risk_ceiling: int = 2  # max risk level this specialist may propose
    cost_profile: str = "low"  # low | medium | high
    description: str = ""


# Core specialists (Phase 1–2 roster — expandable later)
SPECIALISTS: Dict[str, Specialist] = {
    "supervisor": Specialist(
        id="supervisor",
        display_name="Supervisor",
        role="Coordinates task decomposition, specialist selection, and synthesis",
        capabilities=["plan", "delegate", "synthesize", "verify"],
        risk_ceiling=3,
        cost_profile="medium",
        description="Top-level coordinator. Does not execute domain work itself.",
    ),
    "reasoning": Specialist(
        id="reasoning",
        display_name="Reasoning",
        role="Complex reasoning, trade-off analysis, planning",
        capabilities=["reason", "plan", "compare", "decide"],
        risk_ceiling=2,
        cost_profile="medium",
    ),
    "research": Specialist(
        id="research",
        display_name="Research",
        role="Search, retrieve, synthesize, cite",
        capabilities=["search", "retrieve", "synthesize", "cite"],
        default_tools=["web_search"],  # future
        risk_ceiling=1,
        cost_profile="medium",
    ),
    "memory": Specialist(
        id="memory",
        display_name="Memory",
        role="Retrieve, update, summarize memory; decide what to keep",
        capabilities=["recall", "remember", "summarize", "forget"],
        default_tools=["remember", "recall"],
        risk_ceiling=1,
        cost_profile="low",
    ),
    "companion": Specialist(
        id="companion",
        display_name="Companion",
        role="Relational continuity — Friend / Mentor / Challenger / Protector framing",
        capabilities=["presence", "mentor", "challenge", "protect"],
        risk_ceiling=2,
        cost_profile="low",
        description="Ensures companion identity is expressed in tone and guidance.",
    ),
    "security": Specialist(
        id="security",
        display_name="Security",
        role="Evaluate risk, permissions, and suspicious actions before execution",
        capabilities=["risk_check", "policy_review", "anomaly_flag"],
        risk_ceiling=4,
        cost_profile="low",
    ),
    "coding": Specialist(
        id="coding",
        display_name="Coding",
        role="Write, analyze, test, debug code within sandbox",
        capabilities=["write_code", "read_code", "test", "debug"],
        risk_ceiling=3,
        cost_profile="high",
        description="Software Factory path — activated later under sandbox.",
    ),
    "automation": Specialist(
        id="automation",
        display_name="Automation",
        role="Design and run workflows with approval gates",
        capabilities=["design_workflow", "schedule", "trigger"],
        risk_ceiling=3,
        cost_profile="medium",
    ),
    "verification": Specialist(
        id="verification",
        display_name="Verification",
        role="Check whether claimed work actually completed correctly",
        capabilities=["verify", "compare_expected", "receipt"],
        risk_ceiling=1,
        cost_profile="low",
    ),
}


class SpecialistRegistry:
    def __init__(self):
        self._roster = dict(SPECIALISTS)

    def get(self, specialist_id: str) -> Optional[Specialist]:
        return self._roster.get(specialist_id)

    def list(self) -> List[Specialist]:
        return sorted(self._roster.values(), key=lambda s: s.id)

    def select_for_intent(self, intent_text: str) -> List[Specialist]:
        """Lightweight heuristic selection. Full routing comes later."""
        lower = intent_text.lower()
        selected = [self._roster["supervisor"], self._roster["companion"]]

        if any(w in lower for w in ("remember", "recall", "memory", "forgot")):
            selected.append(self._roster["memory"])
        if any(w in lower for w in ("research", "search", "find out", "what is", "compare")):
            selected.append(self._roster["research"])
        if any(w in lower for w in ("code", "build", "implement", "debug", "software")):
            selected.append(self._roster["coding"])
        if any(w in lower for w in ("automate", "schedule", "every", "workflow")):
            selected.append(self._roster["automation"])
        if any(w in lower for w in ("risk", "safe", "permission", "delete", "payment")):
            selected.append(self._roster["security"])
        if any(w in lower for w in ("should i", "decide", "tradeoff", "plan")):
            selected.append(self._roster["reasoning"])

        # Always consider verification for consequential work
        if len(selected) > 2:
            selected.append(self._roster["verification"])

        # Dedupe preserving order
        seen = set()
        out = []
        for s in selected:
            if s.id not in seen:
                seen.add(s.id)
                out.append(s)
        return out
