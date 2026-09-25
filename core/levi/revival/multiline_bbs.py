"""A multi-line bulletin board exchange on a single machine.

Studied from: dead-networks-20260916/report.md (The Major BBS / Worldgroup).

The old mechanism: one PC polled a bank of serial ports, so 32 to 256
dialup callers could be online at once. A round-robin poll swept every
port each tick; ringing lines got answered, connected lines got serviced,
and busy lines logged a missed call. LEVI's reimplementation keeps that
shape — a deterministic line bank with an explicit event feed, a poll
sweep, and per-line session state — without touching real serial
hardware. Every event is injected by the caller, so runs are
reproducible: nothing here dials, answers, or rings anything real.

Line states: IDLE -> RINGING -> CONNECTED -> IDLE. A ring that arrives
on a non-IDLE line is a missed call, counted, never queued (the old
exchanges had no voicemail; honesty about that is the point).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/multiline_bbs"

MIN_LINES = 1
MAX_LINES = 256

# Line states.
IDLE = "idle"
RINGING = "ringing"
CONNECTED = "connected"


@dataclass
class Line:
    """One polled port: its state, its caller, and its session ledger."""

    port: int
    state: str = IDLE
    caller: Optional[str] = None
    answered: bool = False
    keystrokes: int = 0
    sessions_served: int = 0
    log: List[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        self.log.append(text)


@dataclass
class PollStats:
    """What the most recent poll sweep did."""

    sweep: int
    rings_seen: int
    answered: int
    busy_signals: int
    active: int


class LineBank:
    """A bank of polled lines behaving like the old multi-line exchanges.

    Events (ring/answer/hangup) are fed in explicitly; ``poll()`` performs
    one round-robin sweep that answers ringing lines and services
    connected ones. Set ``auto_answer=False`` to make poll only *notice*
    rings, leaving answering to the operator via ``answer()``.
    """

    def __init__(self, lines: int = 32, *, auto_answer: bool = True) -> None:
        if not MIN_LINES <= lines <= MAX_LINES:
            raise ValueError(f"lines must be {MIN_LINES}..{MAX_LINES}")
        self.lines: List[Line] = [Line(port=i) for i in range(lines)]
        self.auto_answer = auto_answer
        self.sweeps = 0
        self.missed_calls = 0
        self.total_rings = 0

    def _line(self, port: int) -> Line:
        if not 0 <= port < len(self.lines):
            raise ValueError(f"no port {port}")
        return self.lines[port]

    # -- injected events -------------------------------------------------
    def ring(self, port: int, caller: str) -> bool:
        """A caller dials in on ``port``. Returns False if the line was
        busy (counted as a missed call, never queued)."""
        line = self._line(port)
        self.total_rings += 1
        if line.state != IDLE:
            self.missed_calls += 1
            line.note(f"busy signal to {caller}")
            return False
        line.state = RINGING
        line.caller = caller
        line.note(f"ring from {caller}")
        return True

    def answer(self, port: int) -> None:
        line = self._line(port)
        if line.state != RINGING:
            raise ValueError(f"port {port} is {line.state}, nothing to answer")
        line.state = CONNECTED
        line.answered = True
        line.sessions_served += 1
        line.note(f"connected {line.caller}")

    def activity(self, port: int, keystrokes: int = 1) -> None:
        """Record caller activity on a connected line (the poll sweep's
        per-line service work, in miniature)."""
        line = self._line(port)
        if line.state != CONNECTED:
            raise ValueError(f"port {port} is {line.state}, not connected")
        if keystrokes < 0:
            raise ValueError("keystrokes must be >= 0")
        line.keystrokes += keystrokes

    def hangup(self, port: int) -> str:
        line = self._line(port)
        if line.state == IDLE:
            raise ValueError(f"port {port} already idle")
        caller = line.caller or "unknown"
        line.note(f"hangup {caller} ({line.keystrokes} keys)")
        line.state = IDLE
        line.caller = None
        line.answered = False
        line.keystrokes = 0
        return caller

    # -- the poll sweep --------------------------------------------------
    def poll(self) -> PollStats:
        """One round-robin sweep: answer ringing lines (if auto_answer),
        count actives. Deterministic; the sweep itself never injects
        rings — callers arrive only through ``ring()``."""
        self.sweeps += 1
        rings = 0
        answered = 0
        for line in self.lines:
            if line.state == RINGING:
                rings += 1
                if self.auto_answer:
                    self.answer(line.port)
                    answered += 1
        active = sum(1 for line in self.lines if line.state == CONNECTED)
        return PollStats(
            sweep=self.sweeps,
            rings_seen=rings,
            answered=answered,
            busy_signals=self.missed_calls,
            active=active,
        )

    # -- operator views --------------------------------------------------
    def active_calls(self) -> List[Tuple[int, str]]:
        return [
            (line.port, line.caller) for line in self.lines if line.state == CONNECTED
        ]

    def utilization(self) -> float:
        active = sum(1 for line in self.lines if line.state != IDLE)
        return active / len(self.lines)

    def line_report(self, port: int) -> Dict[str, object]:
        line = self._line(port)
        return {
            "port": line.port,
            "state": line.state,
            "caller": line.caller,
            "sessions_served": line.sessions_served,
            "log": list(line.log),
        }

    def board_status(self) -> Dict[str, object]:
        return {
            "lines": len(self.lines),
            "sweeps": self.sweeps,
            "rings": self.total_rings,
            "missed_calls": self.missed_calls,
            "active": len(self.active_calls()),
            "utilization": round(self.utilization(), 3),
        }
