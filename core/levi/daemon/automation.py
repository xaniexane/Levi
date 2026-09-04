"""
Automation Registry
Trigger → Conditions → Actions → Verification

Automations interpenetrate with skills, specialists, genres, personas, and composites.
Policy-gated. Bounded execution.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid
import json
from pathlib import Path


class TriggerKind(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"
    CONDITION = "condition"


class AutomationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class AutomationAction:
    skill_id: str
    args: Dict[str, Any] = field(default_factory=dict)
    risk_level: int = 1


@dataclass
class Automation:
    id: str
    name: str
    description: str
    trigger: TriggerKind
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    actions: List[AutomationAction] = field(default_factory=list)
    status: AutomationStatus = AutomationStatus.DRAFT
    risk_ceiling: int = 1
    run_count: int = 0
    last_run: Optional[str] = None
    last_result: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Interpenetration links
    linked_personas: List[str] = field(default_factory=list)
    linked_genres: List[str] = field(default_factory=list)
    linked_composites: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger.value,
            "trigger_config": self.trigger_config,
            "conditions": self.conditions,
            "actions": [{"skill_id": a.skill_id, "args": a.args, "risk_level": a.risk_level} for a in self.actions],
            "status": self.status.value,
            "risk_ceiling": self.risk_ceiling,
            "run_count": self.run_count,
            "last_run": self.last_run,
            "last_result": self.last_result,
            "tags": self.tags,
            "created_at": self.created_at,
            "linked_personas": self.linked_personas,
            "linked_genres": self.linked_genres,
            "linked_composites": self.linked_composites,
        }


DEFAULT_AUTO_DIR = Path.home() / ".levi" / "automations"


class AutomationRegistry:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_AUTO_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._autos: Dict[str, Automation] = {}
        self._load()

    def _load(self) -> None:
        path = self.data_dir / "automations.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for a in raw.get("automations", []):
                    actions = [
                        AutomationAction(
                            skill_id=x["skill_id"],
                            args=x.get("args", {}),
                            risk_level=x.get("risk_level", 1),
                        )
                        for x in a.get("actions", [])
                    ]
                    auto = Automation(
                        id=a["id"],
                        name=a["name"],
                        description=a.get("description", ""),
                        trigger=TriggerKind(a.get("trigger", "manual")),
                        trigger_config=a.get("trigger_config", {}),
                        conditions=a.get("conditions", []),
                        actions=actions,
                        status=AutomationStatus(a.get("status", "draft")),
                        risk_ceiling=a.get("risk_ceiling", 1),
                        run_count=a.get("run_count", 0),
                        last_run=a.get("last_run"),
                        last_result=a.get("last_result"),
                        tags=a.get("tags", []),
                        created_at=a.get("created_at", ""),
                        linked_personas=a.get("linked_personas", []),
                        linked_genres=a.get("linked_genres", []),
                        linked_composites=a.get("linked_composites", []),
                    )
                    self._autos[auto.id] = auto
            except Exception:
                pass

    def _persist(self) -> None:
        path = self.data_dir / "automations.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "automations": [a.to_dict() for a in self._autos.values()],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def create(
        self,
        name: str,
        description: str,
        actions: List[AutomationAction],
        trigger: TriggerKind = TriggerKind.MANUAL,
        risk_ceiling: int = 1,
        linked_personas: Optional[List[str]] = None,
        linked_genres: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Automation:
        # Risk ceiling at least max of action risks
        action_risk = max((a.risk_level for a in actions), default=0)
        ceiling = max(risk_ceiling, action_risk)
        auto = Automation(
            id=f"auto.{uuid.uuid4().hex[:10]}",
            name=name,
            description=description,
            trigger=trigger,
            actions=actions,
            risk_ceiling=ceiling,
            linked_personas=linked_personas or [],
            linked_genres=linked_genres or [],
            tags=tags or [],
        )
        self._autos[auto.id] = auto
        self._persist()
        return auto

    def activate(self, auto_id: str) -> Automation:
        a = self._autos[auto_id]
        a.status = AutomationStatus.ACTIVE
        self._persist()
        return a

    def run_manual(self, auto_id: str, skill_registry=None) -> str:
        """Execute automation actions under simple sequential flow. Policy should gate callers."""
        a = self._autos[auto_id]
        if a.status not in (AutomationStatus.ACTIVE, AutomationStatus.DRAFT):
            return f"Automation {auto_id} is {a.status.value}"
        results = []
        if skill_registry is None:
            from levi.skill.registry import SkillRegistry
            skill_registry = SkillRegistry()
        for action in a.actions:
            try:
                out = skill_registry.invoke(action.skill_id, action.args)
                results.append(f"{action.skill_id}: {str(out)[:100]}")
            except Exception as e:
                results.append(f"{action.skill_id}: ERROR {e}")
                a.last_result = "; ".join(results)
                a.last_run = datetime.now(timezone.utc).isoformat()
                a.run_count += 1
                self._persist()
                return a.last_result
        a.run_count += 1
        a.last_run = datetime.now(timezone.utc).isoformat()
        a.last_result = "; ".join(results) if results else "no actions"
        self._persist()
        return a.last_result

    def list(self) -> List[Automation]:
        return sorted(self._autos.values(), key=lambda x: x.name)

    def get(self, auto_id: str) -> Optional[Automation]:
        return self._autos.get(auto_id)

    def status(self) -> Dict[str, Any]:
        by = {}
        for a in self._autos.values():
            by[a.status.value] = by.get(a.status.value, 0) + 1
        return {
            "count": len(self._autos),
            "by_status": by,
            "data_dir": str(self.data_dir),
        }
