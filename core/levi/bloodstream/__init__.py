"""LEVI bloodstream — the one-turn pipeline of the organism.

Not a new psychology, not new physics: the wiring. One turn flows
through every strand in DNA order::

    USER TEXT
      → Companion + 5D EI          (levi.affect — UX/state, never sentience)
      → Persona lens               (levi.persona — interrogation ⊥ no_hero)
      → L.W.P. graph + governor    (levi.graph.lwp_primitives)
      → route: Factory cascade | organ (echo/mandella) | Model + specialists
      → Policy gate                (Plan → Preview → Permission → Execute → Verify → Receipt)
      → Memory + session + traces
      → Optional graph promotion (verified only)

Every turn emits a Trace record (see levi.bloodstream.trace).
Composites (see levi.bloodstream.composites) let persona + skills +
specialists + automations interpenetrate under one strict risk ceiling.
"""

from levi.bloodstream.stages import (
    BehaviorKind,
    RouteKind,
    StageRecord,
    TurnContext,
    TurnResult,
)
from levi.bloodstream.turn import run_turn
from levi.bloodstream.composites import Composite, CompositeRegistry
from levi.bloodstream.gate import GateOutcome, run_gated
from levi.bloodstream.trace import TraceWriter, new_trace_id

__all__ = [
    "BehaviorKind",
    "RouteKind",
    "StageRecord",
    "TurnContext",
    "TurnResult",
    "run_turn",
    "Composite",
    "CompositeRegistry",
    "GateOutcome",
    "run_gated",
    "TraceWriter",
    "new_trace_id",
]
