"""
LeviAct — execute the decided action and produce a reaction envelope.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from ..personas import Persona, DEFAULT_REGISTRY
from .flow_core import Flow, FlowState
import uuid, datetime

def _prepare_action(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Translate decision into an L.W.P. action payload."""
    action = decision["decision"]
    intent_map = {
        "safe_act":        ("system.safe_act",       "levi",   {"mode": "conservative"}),
        "explore":        ("system.explore",         "levi",   {}),
        "creative_leap":  ("system.creative_leap",  "levi",   {}),
        "lockdown":       ("security.lockdown",     "cybrus", {}),
    }
    intent, target, args = intent_map.get(action, ("system.unknown", "levi", {}))
    return {
        "lwp_type": "action",
        "intent":   intent,
        "target":   target,
        "args":     args,
        "correlation_id": str(uuid.uuid4()),
        "priority": "high" if action == "lockdown" else "normal",
        "ts":       datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

def _dispatch_action(prepared: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch the action — stub: returns what would be sent over L.W.P."""
    return {
        "dispatched": True,
        "action": prepared,
        "note": "In production this sends over L.W.P. to the workspace bridge.",
    }

def _await_reaction(dispatched: Dict[str, Any]) -> Dict[str, Any]:
    """Stub reaction — in production this blocks on a future/callback."""
    return {
        "reaction_type": "ok",
        "correlation_id": dispatched["action"]["correlation_id"],
        "status": "awaiting",
        "note": "Reaction received asynchronously via L.W.P. bridge.",
    }


class LeviActFlow(Flow):
    """Act: Prepare action → Dispatch → Await reaction."""

    def __init__(self, decision: Dict[str, Any], soul: Optional[Dict[str, float]] = None):
        super().__init__(
            id="levi_act_v1",
            name="LeviAct",
            description="Execute the decided action via L.W.P.",
        )
        self.decision = decision
        self.soul = soul or {"joy": 0.5, "trust": 0.7, "fear": 0.1, "surprise": 0.2, "sadness": 0.0}
        self._build_steps()

    def _build_steps(self):
        self.add_step("prepare_action",  _prepare_action,  self.decision)
        self.add_step("dispatch_action", _dispatch_action, None)
        self.add_step("await_reaction",  _await_reaction,  None)

    def execute(self) -> Dict[str, Any]:
        result = {}
        for step in self.steps:
            if step.name == "prepare_action":
                step.run()
                result["prepared"] = step.result
            elif step.name == "dispatch_action":
                step.args = (result["prepared"],)
                step.run()
                result["dispatched"] = step.result
            elif step.name == "await_reaction":
                step.args = (result["dispatched"],)
                step.run()
                result["reaction"] = step.result

        self.state = FlowState.DONE
        return {
            "flow":      "LeviAct",
            "decision":  self.decision["decision"],
            "action":    result["prepared"],
            "dispatched": result["dispatched"],
            "reaction":  result["reaction"],
            "soul":      self.soul,
            "state":     self.state.value,
        }
