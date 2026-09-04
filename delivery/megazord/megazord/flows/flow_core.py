"""
Flow engine core: a Flow is a sequence of steps; FlowEngine orchestrates them.
"""
from __future__ import annotations
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import time

class FlowState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"
    PAUSED  = "paused"

@dataclass
class FlowStep:
    name:     str
    handler:  Callable[..., Any]
    args:     tuple = field(default_factory=tuple)
    kwargs:   Dict[str, Any] = field(default_factory=dict)
    result:   Any = None
    error:    Optional[str] = None
    ts_start: float = 0.0
    ts_end:   float = 0.0

    def run(self) -> Any:
        self.ts_start = time.time()
        try:
            self.result = self.handler(*self.args, **self.kwargs)
            self.ts_end = time.time()
            return self.result
        except Exception as exc:
            self.ts_end = time.time()
            self.error = str(exc)
            raise

    @property
    def duration_ms(self) -> float:
        if self.ts_end and self.ts_start:
            return (self.ts_end - self.ts_start) * 1000
        return 0.0


@dataclass
class Flow:
    id:         str
    name:       str
    description: str = ""
    steps:      List[FlowStep] = field(default_factory=list)
    state:      FlowState = FlowState.PENDING
    context:    Dict[str, Any] = field(default_factory=dict)
    ts_start:   float = 0.0
    ts_end:     float = 0.0

    def add_step(self, name: str, handler: Callable, *args, **kwargs) -> "Flow":
        self.steps.append(FlowStep(name=name, handler=handler, args=args, kwargs=kwargs))
        return self

    def execute(self) -> Dict[str, Any]:
        self.state = FlowState.RUNNING
        self.ts_start = time.time()
        results = []
        for step in self.steps:
            try:
                r = step.run()
                results.append({"step": step.name, "ok": True, "result": r,
                                 "duration_ms": step.duration_ms})
            except Exception as exc:
                results.append({"step": step.name, "ok": False, "error": str(exc),
                                 "duration_ms": step.duration_ms})
                self.state = FlowState.FAILED
                self.ts_end = time.time()
                return {"flow": self.name, "state": self.state.value,
                        "results": results}
        self.state = FlowState.DONE
        self.ts_end = time.time()
        return {"flow": self.name, "state": self.state.value,
                "total_ms": (self.ts_end - self.ts_start)*1000, "results": results}


class FlowRegistry:
    def __init__(self):
        self._flows: Dict[str, Flow] = {}

    def register(self, flow: Flow) -> None:
        self._flows[flow.id] = flow

    def get(self, fid: str) -> Optional[Flow]:
        return self._flows.get(fid)

    def all(self) -> List[Flow]:
        return list(self._flows.values())


class FlowEngine:
    def __init__(self):
        self.registry = FlowRegistry()

    def run(self, flow_id: str) -> Dict[str, Any]:
        flow = self.registry.get(flow_id)
        if not flow:
            return {"error": f"Flow {flow_id!r} not found"}
        return flow.execute()

    def run_named(self, name: str, **context) -> Dict[str, Any]:
        """Find and run the first flow whose name matches."""
        for flow in self.registry.all():
            if flow.name == name:
                flow.context.update(context)
                return flow.execute()
        return {"error": f"Flow named {name!r} not found"}
