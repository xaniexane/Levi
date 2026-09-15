"""
Echo Bridge — blueprint designer, builder, creator.
Echo designs specs and blueprints; Alpha compiles them.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from ..levi_bridge import LeviBridge
import uuid, time


class BlueprintStatus(Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    COMPILED = "compiled"
    FAILED = "failed"


@dataclass
class Blueprint:
    id: str
    name: str
    description: str
    spec: Dict[str, Any]  # the generated JSON spec
    status: BlueprintStatus
    views: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    workflows: List[str] = field(default_factory=list)
    automations: List[str] = field(default_factory=list)
    ts_created: float = field(default_factory=time.time)
    ts_updated: float = field(default_factory=time.time)


class EchoBridge:
    """
    Echo's design engine: generates L.W.P.-compatible app specs from natural language.
    """

    def __init__(self):
        self.levi = LeviBridge(persona="echo")
        self.blueprints: Dict[str, Blueprint] = {}

    def generate_blueprint(
        self, prompt: str, options: Optional[Dict[str, Any]] = None
    ) -> Blueprint:
        """Generate a JSON spec blueprint from a natural language prompt."""
        p_lower = prompt.lower()
        options = options or {}

        # Heuristic spec builder (mirrors omega_os/echo/spec_builder.py)
        app_name = "Generated App"
        if "job" in p_lower:
            app_name = "Hybrid Job Agent"
        if "social" in p_lower:
            app_name = "Social Network App"
        if "market" in p_lower:
            app_name = "Marketplace"
        if "chat" in p_lower:
            app_name = "Chat App"

        models, actions, views = self._infer_components(prompt, app_name)
        workflows = self._infer_workflows(prompt, actions)
        automations = self._infer_automations(prompt, actions)

        spec = {
            "app_name": app_name,
            "version": "1.0.0",
            "models": [
                {"name": m, "fields": ["id", "created_at", "status"]} for m in models
            ],
            "actions": [{"name": a, "type": "function", "params": []} for a in actions],
            "views": [
                {
                    "name": v,
                    "type": "list",
                    "data": models[0] if models else "item",
                    "fields": ["name", "status"],
                    "actions": [],
                }
                for v in views
            ],
            "workflows": workflows,
            "automations": automations,
        }

        bp = Blueprint(
            id=str(uuid.uuid4())[:12],
            name=app_name,
            description=prompt,
            spec=spec,
            status=BlueprintStatus.DRAFT,
            models=models,
            actions=actions,
            views=views,
            workflows=[w["name"] for w in workflows],
            automations=[a["name"] for a in automations],
        )
        self.blueprints[bp.id] = bp
        return bp

    def _infer_components(self, prompt: str, app_name: str):
        p = prompt.lower()
        if "job" in p:
            return (
                ["job", "application"],
                ["search_jobs", "prefill_application", "hitl_approve"],
                ["job_list", "hitl_queue", "dashboard"],
            )
        if "social" in p:
            return (
                ["post", "comment", "profile"],
                ["create_post", "comment", "follow", "block"],
                ["feed", "profile", "notifications"],
            )
        if "market" in p:
            return (
                ["product", "order", "user"],
                ["list_product", "buy", "rate", "refund"],
                ["product_grid", "cart", "order_history"],
            )
        return (["item"], ["process_item"], ["item_list"])

    def _infer_workflows(self, prompt: str, actions: List[str]) -> List[Dict[str, Any]]:
        p = prompt.lower()
        if "daily" in p or "every day" in p:
            return [
                {
                    "name": "daily_flow",
                    "trigger": "daily_schedule",
                    "steps": [
                        {
                            "action": actions[0] if actions else "process_item",
                            "with": {},
                        }
                    ],
                }
            ]
        return []

    def _infer_automations(
        self, prompt: str, actions: List[str]
    ) -> List[Dict[str, Any]]:
        p = prompt.lower()
        if "notify" in p or "alert" in p:
            return [
                {
                    "name": "notify_on_change",
                    "trigger": "status_changed",
                    "conditions": [],
                    "steps": [
                        {
                            "action": "send_notification",
                            "with": {"message": "Status changed."},
                        }
                    ],
                }
            ]
        return []

    def get_blueprint(self, bid: str) -> Optional[Blueprint]:
        return self.blueprints.get(bid)

    def list_blueprints(self) -> List[Blueprint]:
        return list(self.blueprints.values())

    def build_lwp_action(self, blueprint: Blueprint) -> Dict[str, Any]:
        """Produce a L.W.P. action envelope that asks Alpha to compile this blueprint."""
        return self.levi.build_action(
            intent="echo.compile",
            target="alpha.runtime",
            args={"blueprint_id": blueprint.id, "spec": blueprint.spec},
            priority="normal",
            soul={
                "joy": 0.7,
                "trust": 0.6,
                "fear": 0.1,
                "surprise": 0.8,
                "sadness": 0.0,
            },
        )
