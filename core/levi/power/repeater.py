"""Repeater — decay resistance over distance.

Every hop attenuates a signal. A repeater keeps an essence — the part that
must not rot — and re-injects it every `interval` hops, restoring strength
so length cannot kill the message. `Repeater.multi` is the rare
multi-sequence form: it cycles through several essences, a different one
per re-injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Sequence

from .signal import Signal, attenuate


@dataclass
class RepeaterLog:
    hops: int
    reinjections: int
    injections: List[int] = field(default_factory=list)  # hop numbers
    essences: List[Any] = field(default_factory=list)  # essence per injection


class Repeater:
    """Re-inject a kept essence every `interval` hops against `decay`."""

    def __init__(
        self,
        essence: Any = None,
        interval: int = 3,
        decay: float = 0.9,
        restore: float = 1.0,
    ) -> None:
        if interval < 1:
            raise ValueError(f"Repeater: interval must be >= 1, got {interval!r}")
        if not 0.0 < decay <= 1.0:
            raise ValueError(f"Repeater: decay must be in (0, 1], got {decay!r}")
        if not 0.0 < restore <= 1.0:
            raise ValueError(f"Repeater: restore must be in (0, 1], got {restore!r}")
        self.essence = essence
        self.interval = int(interval)
        self.decay = float(decay)
        self.restore = float(restore)
        self._sequence: List[Any] = []

    @classmethod
    def multi(
        cls,
        essences: Sequence[Any],
        interval: int = 3,
        decay: float = 0.9,
        restore: float = 1.0,
    ) -> "Repeater":
        """Rare multi-sequence repeater: a different essence per re-injection."""
        if not essences:
            raise ValueError("Repeater.multi needs at least one essence")
        rep = cls(essence=None, interval=interval, decay=decay, restore=restore)
        rep._sequence = list(essences)
        return rep

    @property
    def multi_sequence(self) -> bool:
        return bool(self._sequence)

    def should_reinject(self, hop: int) -> bool:
        return hop > 0 and hop % self.interval == 0

    def _essence_for(self, injection_index: int) -> Any:
        if self._sequence:
            return self._sequence[injection_index % len(self._sequence)]
        return self.essence

    def propagate(self, signal: Signal, hops: int) -> tuple[Signal, RepeaterLog]:
        """Walk a signal across `hops`, re-injecting essence on schedule."""
        if hops < 0:
            raise ValueError(f"Repeater.propagate: hops must be >= 0, got {hops!r}")
        log = RepeaterLog(hops=hops, reinjections=0)
        cur = signal
        for hop in range(1, hops + 1):
            cur = attenuate(cur, self.decay)
            if self.should_reinject(hop):
                essence = self._essence_for(log.reinjections)
                cur = cur.noted("repeated")
                cur.strength = self.restore
                log.reinjections += 1
                log.injections.append(hop)
                log.essences.append(essence)
        return cur, log
