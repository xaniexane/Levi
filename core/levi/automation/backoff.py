"""Retry schedule and circuit breaker for automation adapters.

Automation adapters (webhook POST, device artifacts, work-product
writers) fail in the real world. Retrying instantly in a hot loop is how
a small outage becomes a self-inflicted flood; retrying forever is how a
dead endpoint becomes a permanent tax. This module gives automations two
honest tools:

- :class:`RetryPolicy` — deterministic exponential backoff with a cap and
  optional seeded jitter. ``delay_for(attempt)`` answers "how long before
  attempt N" with no clock and no sleeping; the caller sleeps.
- :class:`CircuitBreaker` — per-adapter failure accounting persisted to an
  owner-only JSON file: ``closed`` (traffic flows), ``open`` (failing fast
  until the cooldown expires), ``half_open`` (a bounded number of probe
  calls decide whether the circuit closes or re-opens).

State survives restarts because the breaker owns its file; a breaker
that forgot yesterday's failures would be a liar. All time is injected
(``now`` parameters) so the logic is fully testable without sleeping.

Stdlib only, local-first.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_BREAKER_PATH = Path.home() / ".levi" / "automation_breakers.json"


class BackoffError(Exception):
    """Bad policy configuration or bad breaker state transitions."""


@dataclass(frozen=True)
class RetryPolicy:
    """Deterministic exponential backoff.

    attempt is 1-based: ``delay_for(1)`` is the wait before the first
    *retry* (i.e. after the first failure). Jitter, when seeded, is
    reproducible — chaos you can replay.
    """

    max_attempts: int = 5
    base_delay_s: float = 1.0
    max_delay_s: float = 300.0
    jitter_seed: Optional[int] = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise BackoffError("max_attempts must be >= 1")
        if self.base_delay_s <= 0 or self.max_delay_s <= 0:
            raise BackoffError("delays must be positive")
        if self.base_delay_s > self.max_delay_s:
            raise BackoffError("base_delay_s must not exceed max_delay_s")

    def _jitter(self, attempt: int) -> float:
        if self.jitter_seed is None:
            return 1.0
        rng = random.Random(self.jitter_seed * 1_000_003 ^ attempt)
        return rng.uniform(0.5, 1.5)

    def delay_for(self, attempt: int) -> float:
        """Seconds to wait before the retry following failure ``attempt``."""
        if attempt < 1:
            raise BackoffError("attempt is 1-based")
        delay = self.base_delay_s * (2.0 ** (attempt - 1))
        delay = min(delay, self.max_delay_s)
        return round(delay * self._jitter(attempt), 3)

    def schedule(self) -> list[float]:
        """Full wait schedule for every retry the policy allows."""
        return [self.delay_for(a) for a in range(1, self.max_attempts)]


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-adapter breaker with persisted state.

    ``now`` is epoch seconds, injected so tests never sleep. Transitions:

    - closed --(failures reach threshold)--> open (opened_at = now)
    - open --(now - opened_at >= cooldown)--> half_open (on next allow())
    - half_open --(probe success)--> closed; --(probe failure)--> open
    - half_open allows at most ``half_open_probes`` concurrent probes;
      extra calls fail fast while probes are outstanding.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        open_cooldown_s: float = 60.0,
        half_open_probes: int = 1,
        store_path: Optional[Path] = None,
    ) -> None:
        if not name:
            raise BackoffError("breaker name must be non-empty")
        if failure_threshold < 1:
            raise BackoffError("failure_threshold must be >= 1")
        if open_cooldown_s <= 0:
            raise BackoffError("open_cooldown_s must be positive")
        if half_open_probes < 1:
            raise BackoffError("half_open_probes must be >= 1")
        self.name = name
        self.failure_threshold = failure_threshold
        self.open_cooldown_s = open_cooldown_s
        self.half_open_probes = half_open_probes
        self.store_path = Path(store_path) if store_path else DEFAULT_BREAKER_PATH
        self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> None:
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at: Optional[float] = None
        self.probes_outstanding = 0
        try:
            with open(self.store_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            mine = (data.get("breakers") or {}).get(self.name)
        except (FileNotFoundError, ValueError):
            return
        if not isinstance(mine, dict):
            return
        if mine.get("state") in (
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        ):
            self.state = mine["state"]
        self.failures = int(mine.get("failures", 0) or 0)
        self.opened_at = mine.get("opened_at")
        self.probes_outstanding = int(mine.get("probes_outstanding", 0) or 0)

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.store_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                data = {}
        except (FileNotFoundError, ValueError):
            data = {}
        breakers = data.setdefault("breakers", {})
        breakers[self.name] = {
            "state": self.state,
            "failures": self.failures,
            "opened_at": self.opened_at,
            "probes_outstanding": self.probes_outstanding,
        }
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        try:
            os.chmod(self.store_path, 0o600)
        except OSError:
            pass

    # -- transitions -------------------------------------------------------

    def allow(self, now: float) -> bool:
        """True if a call may proceed at ``now``; False = fail fast."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if (
                self.opened_at is not None
                and now - self.opened_at >= self.open_cooldown_s
            ):
                self.state = CircuitState.HALF_OPEN
                self.probes_outstanding = 0
                self._save()
                return self.allow(now)
            return False
        # half_open
        if self.probes_outstanding < self.half_open_probes:
            self.probes_outstanding += 1
            self._save()
            return True
        return False

    def record_success(self, now: float) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.probes_outstanding = max(0, self.probes_outstanding - 1)
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at = None
        self.probes_outstanding = 0
        self._save()

    def record_failure(self, now: float) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.probes_outstanding = max(0, self.probes_outstanding - 1)
            self.state = CircuitState.OPEN
            self.opened_at = now
            self.failures = 0
            self._save()
            return
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now
        self._save()

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self.failures,
            "opened_at": self.opened_at,
            "probes_outstanding": self.probes_outstanding,
        }
