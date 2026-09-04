"""
Intent Map & Motivation Graph
Core LEVI behavior for substantial requests.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class Direction(str, Enum):
    WHY = "why"           # Backward / motivation
    DIRECT = "direct"     # Current solution
    NEXT = "next"         # Forward
    ADJACENT = "adjacent" # Left
    CROSS = "cross"       # Right / cross-domain
    FRONTIER = "frontier" # Outward


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
            key=lambda p: (p.relevance * p.feasibility * p.confidence),
            reverse=True,
        )
