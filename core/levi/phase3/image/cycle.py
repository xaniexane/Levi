"""Local cycle stub: the journal's sequence clock.

The scan-mind's cycle counter will be the journal's sequence clock once
the middle team pins the cycle protocol; until then this deterministic
counter stands in. No wall-clock anywhere in here.
"""

from __future__ import annotations


class CycleClock:
    """Monotonic integer clock. ``tick()`` advances and returns."""

    def __init__(self, start: int = 0) -> None:
        self._n = int(start)

    def tick(self) -> int:
        self._n += 1
        return self._n

    def peek(self) -> int:
        return self._n
