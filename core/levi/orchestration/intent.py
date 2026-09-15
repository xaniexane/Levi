"""
Intent Map & Motivation Graph
Core LEVI behavior for substantial requests.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class Direction(str, Enum):
    WHY = "why"  # Backward / motivation
    DIRECT = "direct"  # Current solution
    NEXT = "next"  # Forward
    ADJACENT = "adjacent"  # Left
    CROSS = "cross"  # Right / cross-domain
    FRONTIER = "frontier"  # Outward


@dataclass
class IntentMap:
    literal_request: str
    objective: Optional[str] = None
    why: Optional[str] = None
    current_state: Optional[str] = None
    desired_outcome: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    time_horizon: Optional[str] = None
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "literal_request": self.literal_request,
            "objective": self.objective,
            "why": self.why,
            "current_state": self.current_state,
            "desired_outcome": self.desired_outcome,
            "constraints": self.constraints,
            "resources": self.resources,
            "success_criteria": self.success_criteria,
            "time_horizon": self.time_horizon,
            "confidence": self.confidence,
        }


@dataclass
class Possibility:
    direction: Direction
    description: str
    relevance: float = 0.5
    feasibility: float = 0.5
    confidence: float = 0.5
    dependencies: List[str] = field(default_factory=list)
    risk: str = "low"
    novelty: str = "medium"


@dataclass
class MotivationGraph:
    intent: IntentMap
    possibilities: List[Possibility] = field(default_factory=list)

    def ranked(self) -> List[Possibility]:
        return sorted(
            self.possibilities,
            key=lambda p: p.relevance * p.feasibility * p.confidence,
            reverse=True,
        )


# --- Turn-loop wiring -------------------------------------------------------
# Deterministic, stdlib-only intent sketch for a single user request.
# Heuristic by design: a routing signal, not a measured understanding.


_DIRECTION_HINTS = (
    ("why", ("why", "because", "reason", "motive")),
    ("next", ("next", "then", "after", "plan", "roadmap")),
    ("adjacent", ("also", "similar", "like", "compare")),
    ("cross", ("instead", "rather", "alternative", "or ")),
    ("frontier", ("new", "novel", "explore", "unknown", "future")),
)


def build_intent_map(literal_request: str) -> IntentMap:
    """Build an IntentMap sketch from raw user text.

    Used by Orchestrator.turn() as the UNDERSTAND step: the structured
    intent record every turn carries in its metadata.
    """
    text = (literal_request or "").strip()
    lower = text.lower()
    objective = text[:160]
    why = ""
    if lower.startswith("why ") or " why " in lower:
        why = "user is asking for reasons/motivation"
    elif any(w in lower for w in ("help", "how do i", "how to")):
        why = "user wants guidance or instruction"
    elif any(w in lower for w in ("build", "make", "create", "write")):
        why = "user wants something constructed"
    constraints: list = []
    if "offline" in lower or "local" in lower:
        constraints.append("local-first; no cloud dependency")
    return IntentMap(
        literal_request=text,
        objective=objective or None,
        why=why or None,
        constraints=constraints,
        confidence=0.5,
    )


def direction_for(text: str) -> Direction:
    """Best-guess exploration direction from keyword hints."""
    lower = (text or "").lower()
    for name, hints in _DIRECTION_HINTS:
        if any(h in lower for h in hints):
            return Direction(name)
    return Direction.DIRECT


def motivation_graph_for(literal_request: str, skill_ids: list) -> MotivationGraph:
    """MotivationGraph sketch: intent + one possibility per candidate skill."""
    intent = build_intent_map(literal_request)
    direction = direction_for(literal_request)
    possibilities = [
        Possibility(
            direction=direction,
            description=f"route via skill '{sid}'",
            relevance=0.7 if i == 0 else 0.5,
            feasibility=0.8,
            confidence=0.5,
        )
        for i, sid in enumerate(skill_ids or [])
    ]
    if not possibilities:
        possibilities.append(
            Possibility(
                direction=direction,
                description="default model generation path",
                relevance=0.6,
                feasibility=0.9,
                confidence=0.5,
            )
        )
    return MotivationGraph(intent=intent, possibilities=possibilities)
