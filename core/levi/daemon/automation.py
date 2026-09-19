"""
Automation Registry
Trigger → Conditions → Actions → Verification

Automations interpenetrate with skills, specialists, genres, personas, and composites.
Policy-gated. Bounded execution.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import os
import sys
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
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
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
            "actions": [
                {"skill_id": a.skill_id, "args": a.args, "risk_level": a.risk_level}
                for a in self.actions
            ],
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


class AutomationError(Exception):
    """Domain error for automation registry failures (bad input, bad data)."""


def _validate_action(action: Any, *, what: str = "action") -> AutomationAction:
    if not isinstance(action, AutomationAction):
        raise AutomationError(
            f"invalid automation {what}: expected AutomationAction, "
            f"got {type(action).__name__}"
        )
    if not isinstance(action.skill_id, str) or not action.skill_id.strip():
        raise AutomationError(
            f"invalid automation {what}: 'skill_id' must be a non-empty string"
        )
    if not isinstance(action.args, dict):
        raise AutomationError(f"invalid automation {what}: 'args' must be a dict")
    if (
        not isinstance(action.risk_level, int)
        or isinstance(action.risk_level, bool)
        or action.risk_level < 0
    ):
        raise AutomationError(
            f"invalid automation {what}: 'risk_level' must be a non-negative "
            f"integer, got {action.risk_level!r}"
        )
    return action


def _action_from_record(x: Any) -> AutomationAction:
    """Parse one stored action record; raises AutomationError when bad."""
    if not isinstance(x, dict):
        raise AutomationError(f"invalid action record {x!r}: must be an object")
    return _validate_action(
        AutomationAction(
            skill_id=x.get("skill_id", ""),
            args=x.get("args", {}),
            risk_level=x.get("risk_level", 1),
        )
    )


def _automation_from_record(a: Any) -> Automation:
    """Parse one stored automation record; raises AutomationError when bad."""
    if not isinstance(a, dict):
        raise AutomationError(f"invalid automation record {a!r}: must be an object")
    auto_id = a.get("id")
    name = a.get("name")
    if not isinstance(auto_id, str) or not auto_id.strip():
        raise AutomationError("automation record is missing a valid 'id'")
    if not isinstance(name, str) or not name.strip():
        raise AutomationError(
            f"automation {auto_id!r}: 'name' must be a non-empty string"
        )
    try:
        trigger = TriggerKind(a.get("trigger", "manual"))
    except ValueError:
        raise AutomationError(
            f"automation {auto_id!r}: unknown trigger {a.get('trigger')!r}"
        ) from None
    try:
        status = AutomationStatus(a.get("status", "draft"))
    except ValueError:
        raise AutomationError(
            f"automation {auto_id!r}: unknown status {a.get('status')!r}"
        ) from None
    actions = [_action_from_record(x) for x in a.get("actions", []) or []]
    risk_ceiling = a.get("risk_ceiling", 1)
    if (
        not isinstance(risk_ceiling, int)
        or isinstance(risk_ceiling, bool)
        or risk_ceiling < 0
    ):
        raise AutomationError(
            f"automation {auto_id!r}: 'risk_ceiling' must be a non-negative "
            f"integer, got {risk_ceiling!r}"
        )
    return Automation(
        id=auto_id,
        name=name,
        description=a.get("description", "") or "",
        trigger=trigger,
        trigger_config=a.get("trigger_config", {}) or {},
        conditions=a.get("conditions", []) or [],
        actions=actions,
        status=status,
        risk_ceiling=risk_ceiling,
        run_count=a.get("run_count", 0) or 0,
        last_run=a.get("last_run"),
        last_result=a.get("last_result"),
        tags=a.get("tags", []) or [],
        created_at=a.get("created_at", "") or "",
        linked_personas=a.get("linked_personas", []) or [],
        linked_genres=a.get("linked_genres", []) or [],
        linked_composites=a.get("linked_composites", []) or [],
    )


class AutomationRegistry:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_AUTO_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._autos: Dict[str, Automation] = {}
        self._load()

    def _load(self) -> None:
        path = self.data_dir / "automations.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Corrupt store: degrade to empty rather than crashing, but
            # say so — silently discarding automations is worse.
            print(
                f"[levi:automation] cannot read {path}: {exc} — "
                "starting with no automations.",
                file=sys.stderr,
            )
            return
        records = raw.get("automations", []) if isinstance(raw, dict) else []
        if not isinstance(records, list):
            return
        for a in records:
            try:
                auto = _automation_from_record(a)
            except AutomationError as exc:
                # Preserve the valid records; skip the broken one loudly.
                print(f"[levi:automation] skipping bad record: {exc}", file=sys.stderr)
                continue
            self._autos[auto.id] = auto

    def _persist(self) -> None:
        path = self.data_dir / "automations.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "automations": [a.to_dict() for a in self._autos.values()],
        }
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise AutomationError(
                f"cannot persist automations to {path}: {exc}"
            ) from exc

    def _require_id(self, auto_id: Any) -> Automation:
        """Fetch an automation or raise an actionable error."""
        if not isinstance(auto_id, str) or not auto_id.strip():
            raise AutomationError(
                f"invalid automation id {auto_id!r}: must be a non-empty string"
            )
        try:
            return self._autos[auto_id]
        except KeyError:
            raise AutomationError(
                f"unknown automation {auto_id!r} — nothing was changed."
            ) from None

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
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> Automation:
        if not isinstance(name, str) or not name.strip():
            raise AutomationError(
                f"invalid automation name {name!r}: must be a non-empty string"
            )
        if not isinstance(description, str):
            raise AutomationError("invalid automation description: must be a string")
        if not isinstance(actions, list):
            raise AutomationError(
                "invalid automation actions: must be a list of AutomationAction"
            )
        actions = [_validate_action(a, what=f"#{i}") for i, a in enumerate(actions)]
        if not isinstance(trigger, TriggerKind):
            raise AutomationError(
                f"invalid automation trigger {trigger!r}: must be a TriggerKind"
            )
        if (
            not isinstance(risk_ceiling, int)
            or isinstance(risk_ceiling, bool)
            or risk_ceiling < 0
        ):
            raise AutomationError(
                f"invalid risk_ceiling {risk_ceiling!r}: must be a non-negative integer"
            )
        # Risk ceiling at least max of action risks
        action_risk = max((a.risk_level for a in actions), default=0)
        ceiling = max(risk_ceiling, action_risk)
        auto = Automation(
            id=f"auto.{uuid.uuid4().hex[:10]}",
            name=name,
            description=description,
            trigger=trigger,
            trigger_config=trigger_config or {},
            actions=actions,
            risk_ceiling=ceiling,
            linked_personas=linked_personas or [],
            linked_genres=linked_genres or [],
            tags=tags or [],
        )
        self._autos[auto.id] = auto
        self._persist()
        return auto

    def remove(self, auto_id: str) -> bool:
        """Delete an automation. Returns False when the id is unknown."""
        if not isinstance(auto_id, str) or not auto_id.strip():
            raise AutomationError(
                f"invalid automation id {auto_id!r}: must be a non-empty string"
            )
        if auto_id not in self._autos:
            return False
        del self._autos[auto_id]
        self._persist()
        return True

    def activate(self, auto_id: str) -> Automation:
        a = self._require_id(auto_id)
        a.status = AutomationStatus.ACTIVE
        self._persist()
        return a

    def run_manual(self, auto_id: str, skill_registry=None) -> str:
        """Execute automation actions under simple sequential flow. Policy should gate callers."""
        a = self._require_id(auto_id)
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

    def register(self, automation: Automation) -> Automation:
        """Insert a pre-built Automation (e.g. a built-in daemon job).

        Replaces any automation already stored under the same id.
        """
        if not isinstance(automation, Automation):
            raise AutomationError(
                f"invalid automation {automation!r}: expected Automation, "
                f"got {type(automation).__name__}"
            )
        if not isinstance(automation.id, str) or not automation.id.strip():
            raise AutomationError("automation is missing a valid 'id'")
        self._autos[automation.id] = automation
        self._persist()
        return automation

    def list(self) -> List[Automation]:
        return sorted(self._autos.values(), key=lambda x: x.name)

    def get(self, auto_id: str) -> Optional[Automation]:
        # Benign lookup: non-string ids simply miss.
        if not isinstance(auto_id, str):
            return None
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


# ---------------------------------------------------------------------------
# Nightly dream cycle (levi.dream wiring)
#
# Registered-but-inert by default: the job installs as PAUSED, and the
# runner is a no-op unless LEVI_DREAM_ENABLED=1. The operator activates the
# job when the nightly dream run is wanted. Dreams are records — the runner
# never executes actions and never leaves the machine.
# ---------------------------------------------------------------------------

DREAM_JOB_ID = "auto.nightly-dream"
DREAM_JOB_RUNNER = "levi.dream.cycle:run_nightly"
DREAM_ENV_ENABLED = "LEVI_DREAM_ENABLED"


def build_nightly_dream_automation(seed_limit: int = 5) -> "Automation":
    """Build the nightly dream-cycle job (not registered — use
    :func:`ensure_nightly_dream_job` to install it idempotently)."""
    return Automation(
        id=DREAM_JOB_ID,
        name="nightly dream cycle",
        description=(
            "Run the dream engine over recent seeds: synthesize dreams, "
            "compost failed branches via REIM, and surface RIEM genome "
            "proposals (data only, never applied)."
        ),
        trigger=TriggerKind.SCHEDULE,
        trigger_config={
            "cadence": "nightly",
            "window": "02:00-04:00 local",
            "runner": DREAM_JOB_RUNNER,
            "seed_limit": seed_limit,
        },
        actions=[],
        status=AutomationStatus.PAUSED,  # inert until the operator activates
        risk_ceiling=0,
        tags=["dream", "nightly", "reim", "riem"],
    )


def ensure_nightly_dream_job(registry: "AutomationRegistry") -> "Automation":
    """Idempotently install the nightly dream job in an automation registry.

    Safe to call on every daemon boot: an existing job is left untouched.
    """
    existing = registry.get(DREAM_JOB_ID)
    if existing is not None:
        return existing
    return registry.register(build_nightly_dream_automation())


def run_dream_job(limit: int = 5, seeds: "Optional[list]" = None) -> str:
    """Runner for the nightly dream job.

    Returns a one-line summary. Inert (does nothing) unless
    ``LEVI_DREAM_ENABLED=1`` — a registered-but-unsanctioned job must not
    run on its own.
    """
    if os.environ.get(DREAM_ENV_ENABLED) != "1":
        return "dream job inert (set %s=1 to run)" % DREAM_ENV_ENABLED
    from levi.dream.cycle import run_cycle

    summary = run_cycle(limit=limit, seeds=seeds)
    return (
        "dream cycle: %d dreams, %d variants, %d composted, %d risky, "
        "%d proposals (unapplied)"
        % (
            summary["dreams"],
            summary["variants"],
            summary["compost_branches"],
            summary["risky_branches"],
            len(summary["proposals"]),
        )
    )
