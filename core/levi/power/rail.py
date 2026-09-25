"""PowerRail — load balancing across consumers, with fault isolation.

A rail holds a budget of energy per round and shares it across registered
consumers by weight (weighted fair share), capped by each consumer's need.
Every consumer sits behind its own CircuitBreaker: a faulted consumer is
isolated — its share goes unserved — while the rail keeps serving the
healthy ones.

`surge()` is the endgame gear: a temporary budget multiplier for N rounds.
Breakers stay armed through a surge; the finale never excuses a fault.

`route()` delivers a signal along a Direction: forward (registration
order), reverse (back toward the source), inverse (same door, opposite
cost — the value negated), or free (first healthy consumer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .breaker import CircuitBreaker
from .signal import Signal


class Direction(Enum):
    FORWARD = "forward"  # along consumer order
    REVERSE = "reverse"  # back toward the source
    INVERSE = "inverse"  # same door, opposite cost
    FREE = "free"  # first healthy consumer


@dataclass
class Delivery:
    consumer: str
    allocation: float
    signal: Optional[Signal] = None


@dataclass
class Consumer:
    name: str
    handler: Callable[[Delivery], Any]
    weight: float = 1.0
    need: float = float("inf")
    breaker: CircuitBreaker = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"Consumer {self.name!r}: weight must be > 0")
        if self.need <= 0:
            raise ValueError(f"Consumer {self.name!r}: need must be > 0")
        if self.breaker is None:
            self.breaker = CircuitBreaker(name=f"breaker/{self.name}")


@dataclass
class DistributionReport:
    budget: float
    effective_budget: float
    allocations: Dict[str, float]
    served: float
    unserved: float
    faults: Dict[str, str]
    isolated: List[str]
    surged: bool


@dataclass
class RouteReport:
    direction: str
    deliveries: List[str]
    faults: Dict[str, str]
    isolated: List[str]


class PowerRail:
    """One rail, many consumers, no single point of failure."""

    def __init__(self, name: str = "rail") -> None:
        self.name = name
        self._consumers: List[Consumer] = []
        self._surge_factor = 1.0
        self._surge_rounds = 0

    def register(self, consumer: Consumer) -> Consumer:
        if any(c.name == consumer.name for c in self._consumers):
            raise ValueError(
                f"PowerRail {self.name!r}: duplicate consumer {consumer.name!r}"
            )
        self._consumers.append(consumer)
        return consumer

    def consumer(
        self,
        name: str,
        handler: Callable[[Delivery], Any],
        weight: float = 1.0,
        need: float = float("inf"),
        failure_threshold: int = 3,
        cooldown: float = 60.0,
    ) -> Consumer:
        """Register a consumer in one call, with its own breaker."""
        return self.register(
            Consumer(
                name=name,
                handler=handler,
                weight=weight,
                need=need,
                breaker=CircuitBreaker(
                    name=f"breaker/{name}",
                    failure_threshold=failure_threshold,
                    cooldown=cooldown,
                ),
            )
        )

    @property
    def isolated(self) -> List[str]:
        return [c.name for c in self._consumers if c.breaker.isolated]

    def _eligible(self) -> List[Consumer]:
        # Half-open consumers may take a probe share; open ones are skipped.
        return [c for c in self._consumers if not c.breaker.isolated]

    def surge(self, factor: float, rounds: int = 1) -> None:
        """Endgame surge: multiply the budget for `rounds` distributions.

        Breakers stay armed — a surge never excuses a fault.
        """
        if factor < 1.0:
            raise ValueError(f"PowerRail.surge: factor must be >= 1, got {factor!r}")
        if rounds < 1:
            raise ValueError(f"PowerRail.surge: rounds must be >= 1, got {rounds!r}")
        self._surge_factor = float(factor)
        self._surge_rounds = int(rounds)

    def distribute(
        self, budget: float, signal: Optional[Signal] = None
    ) -> DistributionReport:
        """Share `budget` across healthy consumers by weight, capped by need."""
        if budget < 0:
            raise ValueError(
                f"PowerRail.distribute: budget must be >= 0, got {budget!r}"
            )
        surged = self._surge_rounds > 0
        effective = budget * self._surge_factor if surged else budget
        if surged:
            self._surge_rounds -= 1
            if self._surge_rounds == 0:
                self._surge_factor = 1.0

        eligible = self._eligible()
        allocations: Dict[str, float] = {}
        faults: Dict[str, str] = {}
        if not eligible or effective <= 0:
            return DistributionReport(
                budget=budget,
                effective_budget=effective,
                allocations={},
                served=0.0,
                unserved=effective,
                faults={},
                isolated=self.isolated,
                surged=surged,
            )

        shares = self._fair_shares(eligible, effective)
        served = 0.0
        for consumer in eligible:
            share = shares.get(consumer.name, 0.0)
            if share <= 0:
                continue
            delivery = Delivery(consumer=consumer.name, allocation=share, signal=signal)
            try:
                consumer.breaker.call(consumer.handler, delivery)
            except Exception as exc:
                faults[consumer.name] = f"{type(exc).__name__}: {exc}"
                continue
            allocations[consumer.name] = share
            served += share
        return DistributionReport(
            budget=budget,
            effective_budget=effective,
            allocations=allocations,
            served=served,
            unserved=effective - served,
            faults=faults,
            isolated=self.isolated,
            surged=surged,
        )

    def _fair_shares(
        self, eligible: List[Consumer], effective: float
    ) -> Dict[str, float]:
        """Weighted fair share with need caps; leftover gets one more pass."""
        total_weight = sum(c.weight for c in eligible)
        shares = {
            c.name: min(effective * c.weight / total_weight, c.need) for c in eligible
        }
        leftover = effective - sum(shares.values())
        if leftover > 1e-9:
            hungry = [c for c in eligible if shares[c.name] < c.need]
            if hungry:
                total_hungry = sum(c.weight for c in hungry)
                for c in hungry:
                    extra = min(
                        leftover * c.weight / total_hungry, c.need - shares[c.name]
                    )
                    shares[c.name] += extra
        return shares

    def route(
        self, signal: Signal, direction: Direction = Direction.FORWARD
    ) -> RouteReport:
        """Deliver a signal along a direction. Faults isolate; the rest flow."""
        eligible = self._eligible()
        if direction is Direction.REVERSE:
            ordered = list(reversed(eligible))
        else:
            ordered = list(eligible)
        if direction is Direction.FREE:
            ordered = ordered[:1]

        deliveries: List[str] = []
        faults: Dict[str, str] = {}
        for consumer in ordered:
            wave = signal
            if direction is Direction.INVERSE:
                wave = signal.noted("inverted")
                wave.value = -signal.value
            delivery = Delivery(consumer=consumer.name, allocation=0.0, signal=wave)
            try:
                consumer.breaker.call(consumer.handler, delivery)
            except Exception as exc:
                faults[consumer.name] = f"{type(exc).__name__}: {exc}"
                continue
            deliveries.append(consumer.name)
        return RouteReport(
            direction=direction.value,
            deliveries=deliveries,
            faults=faults,
            isolated=self.isolated,
        )

    def status(self) -> str:
        lines = [f"=== PowerRail {self.name} ==="]
        for c in self._consumers:
            lines.append(
                f"{c.name}: weight={c.weight:g} need={c.need:g} "
                f"breaker={c.breaker.state.value} trips={c.breaker.trips}"
            )
        if self._surge_rounds:
            lines.append(
                f"surging x{self._surge_factor:g} for {self._surge_rounds} rounds"
            )
        return "\n".join(lines)
