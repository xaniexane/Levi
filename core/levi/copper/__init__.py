"""LEVI copper lists — declarative timed choreography, stdlib-only.

Inspired by the Commodore Amiga's Copper co-processor (1985): a display
co-processor that ran tiny scored lists of three instructions — WAIT
(until the electron beam reached a position), MOVE (write a hardware
register), SKIP (skip the next MOVE if a condition held) — restarting at
each vertical blank. Zero CPU, zero interrupts, zero callbacks: the list
IS the program.

This is a clean-room, native LEVI recreation of the *pattern*, not the
hardware: a small builder for instruction scores of WAIT / EXEC / SKIP,
executed by a tiny runner against a real or simulated clock, producing an
honest Receipt of everything that ran, when, and where it stopped.

Use it for supervision recovery sequences and automation routines:
"wait 5s; exec restart; wait until healthy (30s timeout); skip rest if
already healthy" — deterministic replay under a FakeClock for tests and
bounded simulation.
"""

from .lists import (FakeClock, Instruction, RealClock, Receipt, Score,
                    ScoreError, run)

__all__ = ["Score", "Instruction", "Receipt", "ScoreError", "run",
           "RealClock", "FakeClock"]
