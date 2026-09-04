"""
LeviDecide — decide what to do next given a thought context.
Routes to the correct persona + action based on intent + soul.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from ..personas import Persona, DEFAULT_REGISTRY
from .flow_core import Flow, FlowState

INTENT_ROUTING = {
    "security":    "CYBRUS",
    "build":       "ECHO",
    "orchestrate": "OMEGA",
    "diagnose":    "KAI",
    "unknown":     "ALPHA",
}

def _rank_options(thought: Dict[str, Any]) -> list:
    """Rank action options based on intent and dominant soul axis."""
    intent = thought.get("intent", "unknown")
    dominant = thought.get("dominant_axis", "trust")
    options = [
        {"rank": 1, "action": "safe_act", "confidence": 0.9,
         "description": "Act safely and conservatively — high trust mode"},
        {"rank": 2, "action": "explore", "confidence": 0.6,
         "description": "Explore alternatives — moderate risk"},
    ]
    if dominant in ("joy", "surprise"):
        options.insert(0, {"rank": 0, "action": "creative_leap", "confidence": 0.7,
                            "description": "Creative leap — high surprise/joy"})
    if intent == "security":
        options.insert(0, {"rank": 0, "action": "lockdown", "confidence": 0.95,
                            "description": "Security lockdown — cybrus mode"})
    return options

def _select_option(ranked: list) -> Dict[str, Any]:
    """Pick the highest-confidence option."""
    return max(ranked, key=lambda x: x["confidence"])


class LeviDecideFlow(Flow):
    """Decide: Rank options → Select → Produce decision dict."""

    def __init__(self, thought_context: Dict[str, Any], persona: Optional[Persona] = None):
        super().__init__(
            id="levi_decide_v1",
            name="LeviDecide",
            description="Rank action options and make a decision.",
        )
        self.thought_context = thought_context
        self.persona = persona
        self._build_steps()

    def _build_steps(self):
        self.add_step("rank_options",   _rank_options,   self.thought_context)
        self.add_step("select_option",  _select_option,  None)

    def execute(self) -> Dict[str, Any]:
        result = {}
        for step in self.steps:
            if step.name == "rank_options":
                step.run()
                result["ranked"] = step.result
            elif step.name == "select_option":
                step.args = (result["ranked"],)
                step.run()
                result["selected"] = step.result

        self.state = FlowState.DONE
        intent = self.thought_context.get("intent", "unknown")
        return {
            "flow":       "LeviDecide",
            "intent":     intent,
            "persona":    self.persona.name if self.persona else "ALPHA",
            "options":    result["ranked"],
            "decision":   result["selected"]["action"],
            "confidence": result["selected"]["confidence"],
            "description": result["selected"]["description"],
            "state":      self.state.value,
        }
