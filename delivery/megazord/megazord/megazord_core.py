"""
MegaZord core — the unified think-decide-act loop using a chosen persona.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from .personas import Persona, DEFAULT_REGISTRY
from .flows import LeviThinkFlow, LeviDecideFlow, LeviActFlow
from .bridges.levi_bridge import LeviBridge


class MegaZord:
    """The full Levi × L.W.P. organism."""

    def __init__(self, persona: str = "alpha"):
        self.registry = DEFAULT_REGISTRY
        p = self.registry.get(persona)
        if not p:
            raise ValueError(
                f"Unknown persona {persona!r}. "
                f"Available: {[p.name for p in self.registry.all()]}"
            )
        self.persona = p
        self.bridge = LeviBridge(persona=persona.lower())

    def think(self, prompt: str) -> Dict[str, Any]:
        """Run the think flow on a prompt."""
        return LeviThinkFlow(prompt, persona=self.persona).execute()

    def decide(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """Run the decide flow on a think result."""
        return LeviDecideFlow(thought, persona=self.persona).execute()

    def act(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Run the act flow on a decision."""
        return LeviActFlow(decision, soul=self.persona.soul.to_dict()).execute()

    def handle(self, prompt: str) -> Dict[str, Any]:
        """Run the full think → decide → act loop."""
        thought = self.think(prompt)
        decision = self.decide(thought)
        action = self.act(decision)
        return {
            "persona": self.persona.name,
            "prompt": prompt,
            "thought": thought,
            "decision": decision,
            "action": action,
        }

    def build_envelope(
        self, msg_type: str, payload: dict, soul: Optional[dict] = None
    ) -> dict:
        """Build a L.W.P. envelope using this persona's soul."""
        return self.bridge.build(msg_type, payload, soul or self.persona.soul.to_dict())
