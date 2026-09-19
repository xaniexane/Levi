"""LEVI engines — small deterministic decision machines.

An *engine* is LEVI's smallest unit of judgment: a pure, local,
stdlib-only function that takes inputs in and emits a verdict out, with
a full trace of how it got there. Same inputs → same verdict, every
time (the determinism law). Engines compute; they never act, message,
or spend — the agent or operator decides what to do with the verdict.

Ships with three native engines:

- ``triage``  — weighted multi-option verdict (rank, winner, margin)
- ``cadence`` — rhythm math over event lists (next-due, streaks, drift)
- ``weigh``   — two-sided weighing with calibrated confidence
- ``quorum``  — weighted majority verdicts over named votes with a
  quorum participation gate and deterministic ties
- ``quietwatch`` — selective calling over a transcript: silent until a
  registered call sign is heard (SELCAL pattern, clean-room rebuild)
- ``handshake`` — two-party capability negotiation: tone, offer,
  acknowledgment, or a polite close (Bell 103 pattern, clean-room rebuild)

Use::

    from levi.engines import registry
    result = registry.run("triage", {...})
    print(result.verdict, result.trace)
"""

from __future__ import annotations

from levi.engines.base import (
    Engine,
    EngineInputError,
    EngineRegistry,
    EngineResult,
    registry,
)

__all__ = [
    "Engine",
    "EngineInputError",
    "EngineRegistry",
    "EngineResult",
    "registry",
]

# Builtin engines self-register on import.
from levi.engines import cadence as _cadence  # noqa: E402,F401
from levi.engines import handshake as _handshake  # noqa: E402,F401
from levi.engines import quietwatch as _quietwatch  # noqa: E402,F401
from levi.engines import quorum as _quorum  # noqa: E402,F401
from levi.engines import triage as _triage  # noqa: E402,F401
from levi.engines import weigh as _weigh  # noqa: E402,F401
