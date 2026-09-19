"""CircuitBreaker — fault isolation without killing the rail.

A faulted consumer is isolated: after `failure_threshold` consecutive
failures the breaker opens and calls are refused fast (BreakerOpen) instead
of hammering the fault. After `cooldown` seconds one probe call is allowed
through (half-open); success closes the breaker, failure re-opens it.

The breaker never fixes the fault. It only stops one bad consumer from
taking the whole rail down with it.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Optional


class BreakerState(Enum):
    CLOSED = "closed"  # traffic flows
    OPEN = "open"  # faulted: calls refused
    HALF_OPEN = "half_open"  # cooldown elapsed: one probe allowed


class BreakerOpen(Exception):
    """Raised when a call is refused because the breaker is open."""

    def __init__(self, name: str) -> None:
        super().__init__(f"circuit breaker {name!r} is OPEN — consumer isolated")
        self.breaker_name = name


class CircuitBreaker:
    def __init__(
        self,
        name: str = "breaker",
        failure_threshold: int = 3,
        cooldown: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(
                f"CircuitBreaker: failure_threshold must be >= 1, "
                f"got {failure_threshold!r}"
            )
        if cooldown < 0:
            raise ValueError(f"CircuitBreaker: cooldown must be >= 0, got {cooldown!r}")
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.cooldown = float(cooldown)
        self._clock = clock
        self.failures = 0
        self.trips = 0
        self.last_error: Optional[BaseException] = None
        self._opened_at: Optional[float] = None
        self._forced_open = False

    @property
    def state(self) -> BreakerState:
        if self._forced_open:
            return BreakerState.OPEN
        if self._opened_at is not None:
            if self._clock() - self._opened_at >= self.cooldown:
                return BreakerState.HALF_OPEN
            return BreakerState.OPEN
        return BreakerState.CLOSED

    @property
    def isolated(self) -> bool:
        return self.state is BreakerState.OPEN

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run fn under the breaker. Refuses fast while open."""
        if self.state is BreakerState.OPEN:
            raise BreakerOpen(self.name)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            self._record_failure(exc)
            raise
        self._record_success()
        return result

    def guard(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap fn so every invocation runs under this breaker."""

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return self.call(fn, *args, **kwargs)

        wrapped.__name__ = getattr(fn, "__name__", "guarded")
        return wrapped

    def isolate(self) -> None:
        """Manually open the breaker (operator override)."""
        self._forced_open = True
        self._opened_at = self._clock()

    def reset(self) -> None:
        """Manually close the breaker, clearing failure history."""
        self._forced_open = False
        self._opened_at = None
        self.failures = 0
        self.last_error = None

    def _record_failure(self, exc: BaseException) -> None:
        self.failures += 1
        self.last_error = exc
        if self._opened_at is None:
            if self.failures >= self.failure_threshold:
                self._trip()
        else:
            # Failed probe while half-open: re-open on a fresh cooldown.
            self._trip()

    def _trip(self) -> None:
        self._opened_at = self._clock()
        self.trips += 1

    def _record_success(self) -> None:
        self.failures = 0
        self.last_error = None
        self._forced_open = False
        self._opened_at = None

    def stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "trips": self.trips,
            "failure_threshold": self.failure_threshold,
            "cooldown": self.cooldown,
            "last_error": repr(self.last_error) if self.last_error else None,
        }
