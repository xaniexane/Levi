"""
L.W.P. Structural Primitives — clean modular re-implementation

Cascade Chain · Spiral Coil · Circuit Breaker · Governor · Bible · Banks

These constrain and enable interpenetration. They interpenetrate with
personas, skills, specialists, and composites.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid


class PrimitiveKind(str, Enum):
    CASCADE = "cascade"           # typed deterministic sequence
    SPIRAL = "spiral"             # iterative feedback
    CIRCUIT_BREAKER = "circuit_breaker"
    GOVERNOR = "governor"
    BIBLE = "bible"               # immutable verified canon
    BANKS = "banks"               # versioned approved stores


@dataclass
class CascadeStep:
    id: str
    name: str
    action: str
    expected: str = ""
    risk: int = 1


@dataclass
class CascadeChain:
    """Deterministic typed execution sequence."""
    id: str
    name: str
    steps: List[CascadeStep] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""

    def add(self, name: str, action: str, expected: str = "", risk: int = 1) -> "CascadeChain":
        self.steps.append(CascadeStep(str(uuid.uuid4())[:8], name, action, expected, risk))
        return self


@dataclass
class SpiralCoil:
    """Iterative feedback workflow — each turn feeds the next."""
    id: str
    name: str
    max_iterations: int = 5
    iteration: int = 0
    state: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def tick(self, observation: str, update: Optional[Dict[str, Any]] = None) -> bool:
        """Returns True if should continue, False if done or maxed."""
        self.iteration += 1
        self.history.append({
            "iteration": self.iteration,
            "observation": observation,
            "update": update or {},
            "at": datetime.now(timezone.utc).isoformat(),
        })
        if update:
            self.state.update(update)
        return self.iteration < self.max_iterations


@dataclass
class CircuitBreaker:
    """Resource / risk / depth limiter — trips closed on breach."""
    name: str
    max_depth: int = 8
    max_cost: float = 10.0
    max_calls: int = 50
    calls: int = 0
    cost: float = 0.0
    tripped: bool = False
    reason: str = ""

    def check(self, depth: int = 0, add_cost: float = 0.0) -> bool:
        """Return True if still open (allowed), False if tripped."""
        self.calls += 1
        self.cost += add_cost
        if depth > self.max_depth:
            self.tripped = True
            self.reason = f"depth {depth} > {self.max_depth}"
            return False
        if self.cost > self.max_cost:
            self.tripped = True
            self.reason = f"cost {self.cost} > {self.max_cost}"
            return False
        if self.calls > self.max_calls:
            self.tripped = True
            self.reason = f"calls {self.calls} > {self.max_calls}"
            return False
        return True

    def reset(self) -> None:
        self.calls = 0
        self.cost = 0.0
        self.tripped = False
        self.reason = ""


@dataclass
class Governor:
    """Dynamic budget / complexity controller."""
    name: str
    budget: float = 5.0
    spent: float = 0.0
    complexity_limit: int = 10
    current_complexity: int = 0

    def authorize(self, cost: float = 0.1, complexity: int = 1) -> bool:
        if self.spent + cost > self.budget:
            return False
        if self.current_complexity + complexity > self.complexity_limit:
            return False
        self.spent += cost
        self.current_complexity += complexity
        return True

    def remaining(self) -> float:
        return max(0.0, self.budget - self.spent)


@dataclass
class BibleEntry:
    """Immutable verified canon entry."""
    id: str
    title: str
    content: str
    hash: str  # integrity marker (simple for Phase 1)
    sealed_at: str


class Bible:
    """Immutable verified canon — write-once entries."""
    def __init__(self):
        self._entries: Dict[str, BibleEntry] = {}

    def seal(self, title: str, content: str) -> BibleEntry:
        import hashlib
        eid = str(uuid.uuid4())[:12]
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        entry = BibleEntry(
            id=eid,
            title=title,
            content=content,
            hash=h,
            sealed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._entries[eid] = entry
        return entry

    def get(self, entry_id: str) -> Optional[BibleEntry]:
        return self._entries.get(entry_id)

    def list(self) -> List[BibleEntry]:
        return list(self._entries.values())


class Banks:
    """Versioned approved knowledge/artifact stores."""
    def __init__(self):
        self._stores: Dict[str, List[Dict[str, Any]]] = {}

    def deposit(self, bank_name: str, artifact: Dict[str, Any]) -> int:
        if bank_name not in self._stores:
            self._stores[bank_name] = []
        version = len(self._stores[bank_name]) + 1
        record = {
            "version": version,
            "artifact": artifact,
            "deposited_at": datetime.now(timezone.utc).isoformat(),
        }
        self._stores[bank_name].append(record)
        return version

    def withdraw(self, bank_name: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if bank_name not in self._stores or not self._stores[bank_name]:
            return None
        if version is None:
            return self._stores[bank_name][-1]
        for r in self._stores[bank_name]:
            if r["version"] == version:
                return r
        return None

    def versions(self, bank_name: str) -> int:
        return len(self._stores.get(bank_name, []))
