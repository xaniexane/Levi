"""Engine substrate: types, registry, and the determinism gate.

The registry is the only legal way to run an engine. Registration is
additive and idempotent; ``run`` validates inputs against the engine's
declared schema before anything executes (deny-closed: malformed input
is refused with a named error, never coerced). Engines are pure —
``run`` may not touch the network, the filesystem, or wall-clock state
beyond what is passed in as input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


class EngineInputError(ValueError):
    """Raised when inputs fail the engine's schema check."""


@dataclass(frozen=True)
class EngineResult:
    """A verdict plus its audit trail."""

    engine_id: str
    verdict: Any
    confidence: float  # 0.0–1.0, calibrated by the engine itself
    trace: List[str] = field(default_factory=list)
    ran_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "trace": list(self.trace),
            "ran_at": self.ran_at,
        }


@dataclass
class Engine:
    """A registered deterministic decision machine."""

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    # Names of required input keys; optional keys may also be listed in
    # ``schema`` with their expected type names for documentation.
    required: Tuple[str, ...] = ()
    schema: Dict[str, str] = field(default_factory=dict)
    risk: str = "info"  # info | low — engines compute, never act
    handler: Optional[Callable[[Dict[str, Any]], EngineResult]] = None

    def run(self, inputs: Dict[str, Any]) -> EngineResult:
        if self.handler is None:
            raise EngineInputError(f"engine '{self.id}' has no handler")
        self._validate(inputs)
        return self.handler(dict(inputs))

    def _validate(self, inputs: Dict[str, Any]) -> None:
        if not isinstance(inputs, dict):
            raise EngineInputError(
                f"engine '{self.id}': inputs must be a dict, got "
                f"{type(inputs).__name__}"
            )
        missing = [k for k in self.required if k not in inputs]
        if missing:
            raise EngineInputError(
                f"engine '{self.id}': missing required inputs: "
                + ", ".join(missing)
            )


class EngineRegistry:
    """Owns every registered engine. Unknown ids name what's available."""

    def __init__(self) -> None:
        self._engines: Dict[str, Engine] = {}

    def register(self, engine: Engine) -> Engine:
        if engine.id in self._engines:
            raise ValueError(f"engine '{engine.id}' already registered")
        if not engine.id or not engine.id.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"engine id '{engine.id}' is not slug-safe")
        self._engines[engine.id] = engine
        return engine

    def get(self, engine_id: str) -> Engine:
        try:
            return self._engines[engine_id]
        except KeyError:
            available = ", ".join(sorted(self._engines)) or "(none)"
            raise KeyError(
                f"unknown engine '{engine_id}'. Available: {available}"
            ) from None

    def list(self) -> List[Engine]:
        return [self._engines[k] for k in sorted(self._engines)]

    def run(self, engine_id: str, inputs: Dict[str, Any]) -> EngineResult:
        return self.get(engine_id).run(inputs)


# The shared registry. Engine modules register themselves on import via
# the ``_register_builtin`` hook below.
registry = EngineRegistry()
