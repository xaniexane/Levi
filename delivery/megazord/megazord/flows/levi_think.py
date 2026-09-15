"""
LeviThink — the think loop: observe → interpret → surface thought.
Consumes a prompt, produces a thought envelope + soul-adjusted context.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from ..personas import Persona, DEFAULT_REGISTRY
from .flow_core import Flow, FlowState


def _observe(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Observe: parse intent, detect keywords, check emotional tone."""
    prompt_lower = prompt.lower()
    keywords = [w for w in prompt_lower.split() if len(w) > 3]
    intent_hint = (
        "security"
        if any(
            w in prompt_lower for w in ["scan", "threat", "secure", "block", "protect"]
        )
        else "build"
        if any(
            w in prompt_lower
            for w in ["make", "create", "design", "build", "generate", "compile"]
        )
        else "orchestrate"
        if any(
            w in prompt_lower
            for w in ["run", "execute", "orchestrate", "schedule", "automate"]
        )
        else "diagnose"
        if any(
            w in prompt_lower
            for w in ["check", "diagnose", "status", "health", "report"]
        )
        else "unknown"
    )
    return {
        "keywords": keywords[:10],
        "intent_hint": intent_hint,
        "prompt_len": len(prompt),
        "context": context,
    }


def _interpret(
    observation: Dict[str, Any], persona: Optional[Persona] = None
) -> Dict[str, Any]:
    """Interpret: select persona, compute dominant soul axis, generate thought text."""
    obs = observation
    dominant = obs["intent_hint"]
    thought_text = (
        f"[THINK] Intent detected: {dominant}. "
        f"Keywords: {', '.join(obs['keywords'][:5])}. "
        f"{'Security concern — activating cautious mode.' if dominant == 'security' else ''}"
        f"{'Building opportunity — high creative energy.' if dominant == 'build' else ''}"
        f"{'Orchestration task — activating executor mode.' if dominant == 'orchestrate' else ''}"
        f"{'Diagnostic run — checking system health.' if dominant == 'diagnose' else ''}"
    )
    soul = (
        persona.soul.to_dict()
        if persona
        else {"joy": 0, "trust": 0, "fear": 0, "surprise": 0, "sadness": 0}
    )
    return {
        "thought": thought_text,
        "intent": dominant,
        "soul": soul,
        "dominant_axis": max(soul, key=soul.get) if soul else "trust",
    }


def _surface(interpretation: Dict[str, Any]) -> Dict[str, Any]:
    """Surface: format for L.W.P. thought envelope."""
    return {
        "lwp_type": "thought",
        "thought": interpretation["thought"],
        "intent": interpretation["intent"],
        "soul_snapshot": interpretation["soul"],
        "dominant_axis": interpretation["dominant_axis"],
        "state": FlowState.RUNNING.value,
    }


class LeviThinkFlow(Flow):
    """Three-step think flow: Observe → Interpret → Surface."""

    def __init__(
        self,
        prompt: str,
        persona: Optional[Persona] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            id="levi_think_v1",
            name="LeviThink",
            description="Observe → Interpret → Surface. The core Levi's think loop.",
        )
        self.prompt = prompt
        self.persona = persona
        self.context = context or {}
        self._build_steps()

    def _build_steps(self):
        self.add_step("observe", _observe, self.prompt, self.context)
        self.add_step("interpret", _interpret, None, self.persona)
        self.add_step("surface", _surface, None)

    def execute(self) -> Dict[str, Any]:
        # Run observe + interpret in sequence, wire the outputs
        result = {}
        for step in self.steps:
            if step.name == "observe":
                step.run()
                result["observation"] = step.result
            elif step.name == "interpret":
                step.args = (result["observation"],)
                step.run()
                result["interpretation"] = step.result
            elif step.name == "surface":
                step.args = (result["interpretation"],)
                step.run()
                result["surface"] = step.result

        self.state = FlowState.DONE
        return {
            "flow": "LeviThink",
            "prompt": self.prompt,
            "thought": result["interpretation"]["thought"],
            "intent": result["interpretation"]["intent"],
            "soul": result["interpretation"]["soul"],
            "envelope": result["surface"],
        }
