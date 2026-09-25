"""omnipulse: the lifecycle heartbeat — an 18-phase cycle clock (LEVI-native).

Canon role (ORGANISM_FORMS): "lifecycle engine; birth->expansion->echo->
collapse->rebirth->stabilization".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "OmniPulse (Heartbeat) — 18-phase cycle clock (omnipulse_heartbeat.py)."
  - SER-18 (Lifecycle Engine) maps to OmniPulse, Eden, UniForge, Vector.
  - "OmniPulse controls cycle timing."

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. The phase canon comes from ``levi.ser18`` (quoted from
the founder's spec); OmniPulse is the CLOCK that advances it: a monotonic
beat counter, one phase per beat, with dry-run purity (``tick(dry_run=True)``
reports the next beat without advancing), fail-closed beats (refuses
non-integer or negative beat counts as data), and a receipt per tick.

OmniPulse is a clock, not a scheduler: it does not execute phases. The
daemon or caller decides what each beat means.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from levi.ser18 import Lifecycle, SER18_PHASES

FORM_NAME = "omnipulse"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class OmniPulse:
    """18-phase heartbeat. ``beats`` is the monotonic clock."""

    def __init__(self, phase: str = "Birth", beats: int = 0) -> None:
        if not isinstance(beats, int) or isinstance(beats, bool) or beats < 0:
            raise ValueError(f"beats must be a non-negative int, got {beats!r}")
        self.cycle = Lifecycle(phase=phase)
        self.beats = beats

    def tick(self, n: Any = 1, *, dry_run: bool = False) -> Dict[str, Any]:
        """Advance the clock by ``n`` beats (default 1)."""
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            return self._receipt(
                "rejected",
                f"beat count must be a non-negative int, got {n!r}: "
                "treated as data, clock untouched",
            )
        if n == 0:
            return self._receipt(
                "heartbeat", "zero beats: clock holds", dry_run=dry_run
            )
        if dry_run:
            idx = (SER18_PHASES.index(self.cycle.phase) + n) % len(SER18_PHASES)
            return self._receipt(
                "dry-run",
                f"would advance {n} beat(s) {self.cycle.phase} -> "
                f"{SER18_PHASES[idx]}; clock untouched",
                dry_run=True,
            )
        for _ in range(n):
            self.cycle.advance()
            self.beats += 1
        return self._receipt(
            "heartbeat",
            f"advanced {n} beat(s) to {self.cycle.phase} (beat {self.beats})",
        )

    def phase(self) -> str:
        return self.cycle.phase

    def status(self) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "phase": self.cycle.phase,
            "beats": self.beats,
            "phases": len(SER18_PHASES),
            "at": _utcnow(),
        }

    def _receipt(
        self, status: str, reason: str, *, dry_run: bool = False
    ) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "status": status,
            "reason": reason,
            "phase": self.cycle.phase,
            "beats": self.beats,
            "dry_run": dry_run,
            "at": _utcnow(),
        }
