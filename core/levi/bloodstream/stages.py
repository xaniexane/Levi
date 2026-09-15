"""Typed stage contracts for the bloodstream turn pipeline.

Every stage speaks these dataclasses. The pipeline in levi.bloodstream.turn
is the only producer; traces, CLI, and tests are consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.policy.gates import RiskLevel


class BehaviorKind(str, Enum):
    NONE = "none"
    INTERROGATION = "interrogation"  # LEVI questions the user; withholds the answer
    NO_HERO = "no_hero"  # short, vague default; expands one layer on request
    REFRAME = "reframe"  # reframes the question back at the user


class RouteKind(str, Enum):
    SPECIAL = "special"  # persona special behavior short-circuited the turn
    FACTORY = "factory"  # constructive intent → Software Factory cascade
    ORGAN = "organ"  # branching organ (echo / mandella)
    MODEL = "model"  # provider chain + specialists (deterministic offline default)
    GOVERNED = "governed"  # governor/breaker refused the turn
    FAILED = "failed"  # a stage raised; failure was composted


@dataclass
class TurnContext:
    """Per-turn inputs. Pure data; the pipeline never mutates it."""

    session_id: str = "default"
    persona_id: Optional[str] = None
    provider: Optional[str] = (
        None  # explicit provider name; None → provider chain default
    )
    auto_approve_up_to: RiskLevel = RiskLevel.LOW
    confirm: Optional[Callable[[Any], bool]] = (
        None  # HITL callback; None → non-interactive
    )
    data_dir: Optional[Path] = None  # overrides ~/.levi (tests, hermetic runs)
    composite_name: Optional[str] = None
    dry_run: bool = False
    max_model_steps: int = 4


@dataclass
class StageRecord:
    """What one stage decided, in trace-friendly form."""

    stage: str
    decision: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"stage": self.stage, "decision": self.decision, "detail": self.detail}


@dataclass
class TurnResult:
    """The complete, honest outcome of one bloodstream turn."""

    reply: str
    route: RouteKind
    behavior: BehaviorKind
    persona_id: str
    risk_level: int
    receipt_summary: str
    trace_id: str
    policy_receipt_id: Optional[str] = None
    awaiting_permission: bool = False
    promotion_eligible: bool = False
    ok: bool = True
    error: Optional[str] = None
    stages: List[StageRecord] = field(default_factory=list)

    def stage_names(self) -> List[str]:
        return [s.stage for s in self.stages]
