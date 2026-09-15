"""
Daemon Kernel (brainstem) — keeps the unified agent from becoming chaos.

Not a chatbot. Operating substrate under LEVI Daemon Core:

  Event Bus · Scheduler · State · Permission · Tool Registry · Model Router
  Memory Router · Workflow Engine · Cost Controller · Safety · Audit · E-Stop
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import json
import math
import uuid


DEFAULT_KERNEL_PATH = Path.home() / ".levi" / "daemon_kernel.json"


class KernelError(Exception):
    """Domain error for daemon kernel failures (bad input, bad state)."""


class SafetyLevel(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    STOPPED = "stopped"  # emergency stop


@dataclass
class KernelEvent:
    id: str
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KernelState:
    safety: str = SafetyLevel.NORMAL.value
    cycle: int = 0
    last_event_id: str = ""
    cost_units_session: float = 0.0
    cost_budget: float = 100.0  # abstract units; free-first = prefer 0-cost paths
    estop: bool = False
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KernelState":
        """Rebuild state, validating each field with a safe default.

        A corrupt field degrades to its default; only a wholly
        non-object record falls back to a fresh state.
        """
        if not isinstance(d, dict):
            return cls()
        safety = d.get("safety") or SafetyLevel.NORMAL.value
        if safety not in {s.value for s in SafetyLevel}:
            safety = SafetyLevel.NORMAL.value
        try:
            cycle = int(d.get("cycle", 0))
        except (TypeError, ValueError):
            cycle = 0
        cycle = max(0, cycle)
        try:
            spent = float(d.get("cost_units_session", 0.0))
        except (TypeError, ValueError):
            spent = 0.0
        if not math.isfinite(spent) or spent < 0:
            spent = 0.0
        try:
            budget = float(d.get("cost_budget", 100.0))
        except (TypeError, ValueError):
            budget = 100.0
        if not math.isfinite(budget) or budget <= 0:
            budget = 100.0
        last_event_id = d.get("last_event_id") or ""
        if not isinstance(last_event_id, str):
            last_event_id = ""
        updated_at = d.get("updated_at") or datetime.now(timezone.utc).isoformat()
        if not isinstance(updated_at, str):
            updated_at = datetime.now(timezone.utc).isoformat()
        return cls(
            safety=safety,
            cycle=cycle,
            last_event_id=last_event_id,
            cost_units_session=spent,
            cost_budget=budget,
            estop=bool(d.get("estop", False)),
            updated_at=updated_at,
        )


class DaemonKernel:
    """
    Minimal brainstem. Deterministic. No model required to run.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_KERNEL_PATH
        self.state = KernelState()
        self._bus: List[KernelEvent] = []
        self._handlers: Dict[str, List[Callable[[KernelEvent], None]]] = {}
        self._tools: Dict[str, str] = {}  # name -> description
        self._audit: List[Dict[str, Any]] = []
        self._load()
        self._register_builtin_tools()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = KernelState.from_dict(raw.get("state") or {})
            audit = raw.get("audit") or []
            self._audit = list(audit)[-200:] if isinstance(audit, list) else []
            tools = raw.get("tools") or {}
            self._tools = (
                {str(k): str(v) for k, v in tools.items()}
                if isinstance(tools, dict)
                else {}
            )
        except (json.JSONDecodeError, TypeError, ValueError, OSError, KeyError):
            self.state = KernelState()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "state": self.state.to_dict(),
            "audit": self._audit[-200:],
            "tools": self._tools,
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            raise KernelError(
                f"cannot persist daemon kernel state to {self.path}: {exc}"
            ) from exc

    def _register_builtin_tools(self) -> None:
        defaults = {
            "memory.recall": "Search local memory/corpus/brain",
            "memory.record": "Write to corpus or brain table",
            "project.phase": "Service phase runner",
            "hitl.propose": "Human approval gate",
            "organ.echo": "Parallel path organ",
            "organ.mandella": "Stake organ",
            "demand.scan": "DemandPulse opportunity scan",
            "income.compose": "Income factory composition (no auto-spend)",
            "model.generate": "Model relay (local-first)",
            "pulse.check": "Local self-check",
            "ops.status": "Operational layer snapshot",
            "lwp.mirror": "Mirror Cascade reverse cross-check",
            "lwp.rail": "Opportunity Rail HITL automation",
            "builder.plan": "Emergency Builder E3-E6",
            "story.expand": "L.W.P. cascade story expand",
        }
        for k, v in defaults.items():
            self._tools.setdefault(k, v)

    # --- Event bus ---
    def emit(self, kind: str, payload: Optional[Dict[str, Any]] = None) -> KernelEvent:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(
                f"emit: 'kind' must be a non-empty string, got {kind!r}"
            )
        if payload is not None and not isinstance(payload, dict):
            raise ValueError(
                f"emit: 'payload' must be a dict or None, got {type(payload).__name__}"
            )
        if self.state.estop or self.state.safety == SafetyLevel.STOPPED.value:
            ev = KernelEvent(
                id=str(uuid.uuid4())[:8],
                kind="blocked_estop",
                payload={"attempted": kind},
            )
            self._audit_log("emit_blocked", {"kind": kind})
            return ev
        ev = KernelEvent(id=str(uuid.uuid4())[:8], kind=kind, payload=payload or {})
        self._bus.append(ev)
        self._bus = self._bus[-100:]
        self.state.last_event_id = ev.id
        self.state.cycle += 1
        for h in self._handlers.get(kind, []) + self._handlers.get("*", []):
            try:
                h(ev)
            except Exception:
                pass
        self._audit_log("emit", {"id": ev.id, "kind": kind})
        self._persist()
        return ev

    def on(self, kind: str, handler: Callable[[KernelEvent], None]) -> None:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(
                f"on: 'kind' must be a non-empty string, got {kind!r}"
            )
        if not callable(handler):
            raise ValueError(
                f"on: 'handler' must be callable, got {type(handler).__name__}"
            )
        self._handlers.setdefault(kind, []).append(handler)

    # --- Permission / safety ---
    def require_permission(self, action: str, risk: str = "LOW") -> bool:
        """True if action may proceed without HITL. High risk always False."""
        if self.state.estop:
            return False
        r = (risk or "LOW").upper()
        if r in ("HIGH", "CRITICAL"):
            return False
        if r == "MEDIUM":
            return False  # HITL required
        return True

    def emergency_stop(self, reason: str = "") -> None:
        if not isinstance(reason, str):
            raise ValueError(
                f"emergency_stop: 'reason' must be a string, got {type(reason).__name__}"
            )
        self.state.estop = True
        self.state.safety = SafetyLevel.STOPPED.value
        self._audit_log("estop", {"reason": reason})
        self._persist()

    def clear_estop(self) -> None:
        self.state.estop = False
        self.state.safety = SafetyLevel.NORMAL.value
        self._audit_log("estop_cleared", {})
        self._persist()

    # --- Cost ---
    def charge(self, units: float, label: str = "") -> bool:
        """Return False if over budget (prefer free/local)."""
        try:
            units = float(units)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(
                f"charge: 'units' must be a number, got {units!r}"
            ) from None
        if not math.isfinite(units):
            raise ValueError(
                f"charge: 'units' must be finite, got {units!r}"
            )
        if not isinstance(label, str):
            raise ValueError(
                f"charge: 'label' must be a string, got {type(label).__name__}"
            )
        if units <= 0:
            return True
        if self.state.cost_units_session + units > self.state.cost_budget:
            self._audit_log("cost_blocked", {"units": units, "label": label})
            return False
        self.state.cost_units_session += units
        self._audit_log("cost", {"units": units, "label": label})
        self._persist()
        return True

    def tool_registry(self) -> Dict[str, str]:
        return dict(self._tools)

    def register_tool(self, name: str, description: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"register_tool: 'name' must be a non-empty string, got {name!r}"
            )
        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                "register_tool: 'description' must be a non-empty string"
            )
        self._tools[name] = description
        self._persist()

    def _audit_log(self, action: str, detail: Dict[str, Any]) -> None:
        self._audit.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "detail": detail,
            }
        )
        self._audit = self._audit[-200:]

    def status(self) -> str:
        lines = [
            "=== LEVI Daemon Kernel (brainstem) ===",
            f"safety={self.state.safety}  estop={self.state.estop}  cycle={self.state.cycle}",
            f"cost_session={self.state.cost_units_session:.1f} / budget={self.state.cost_budget:.1f}",
            f"tools_registered={len(self._tools)}  bus_depth={len(self._bus)}",
            f"last_event={self.state.last_event_id or '—'}",
        ]
        return "\n".join(lines)
