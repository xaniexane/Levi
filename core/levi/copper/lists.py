"""Score lists: the Copper pattern, generalized.

A Score is an ordered list of instructions built with the fluent API:

    score = (Score("service-recovery")
             .skip_if("already-healthy", is_healthy)
             .wait_ms(5_000)
             .exec("restart", restart_service)
             .wait_until("healthy", is_healthy, timeout_ms=30_000))

Instructions:
  wait_ms(ms)                       — advance the clock by ms
  wait_until(name, pred, timeout_ms) — poll pred until true or timeout
  exec(name, fn)                    — call fn(); record its elapsed time
  skip_if(name, pred)               — if pred() is true, skip the NEXT exec

Execution is deny-closed and receipted: run() returns a Receipt listing
every event with timestamps from the (real or fake) clock, whether the
score completed, and exactly where/why it stopped. Timeouts and exec
errors STOP the score and are recorded — never silently swallowed.

A FakeClock makes scores fully deterministic for tests and for the
bounded-simulation law: no real time passes, but the receipt reads the
same.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class ScoreError(ValueError):
    """Raised when a score is built invalidly (deny-closed builder)."""


# --------------------------------------------------------------------------
# clocks
# --------------------------------------------------------------------------


class RealClock:
    """Wall clock: sleeps really sleep. Use for production runs."""

    def now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def sleep_ms(self, ms: int) -> None:
        if ms > 0:
            time.sleep(ms / 1000.0)


class FakeClock:
    """Simulated clock: sleep_ms advances instantly. Deterministic."""

    def __init__(self) -> None:
        self._t = 0
        self.advances: List[int] = []

    def now_ms(self) -> int:
        return self._t

    def sleep_ms(self, ms: int) -> None:
        if ms > 0:
            self._t += ms
            self.advances.append(ms)


# --------------------------------------------------------------------------
# instructions + score builder
# --------------------------------------------------------------------------

_OPS = ("wait_ms", "wait_until", "exec", "skip_if")


@dataclass
class Instruction:
    op: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.op not in _OPS:
            raise ScoreError(f"unknown op {self.op!r} (expected one of {_OPS})")
        if not self.name:
            raise ScoreError("instruction name must be non-empty")


class Score:
    """Fluent builder for a scored instruction list."""

    def __init__(self, name: str) -> None:
        if not name:
            raise ScoreError("score name must be non-empty")
        self.name = name
        self.instructions: List[Instruction] = []

    # -- builders ---------------------------------------------------------

    def wait_ms(self, ms: int, name: str = "") -> "Score":
        if not isinstance(ms, int) or ms < 0:
            raise ScoreError(f"wait_ms requires a non-negative int, got {ms!r}")
        self.instructions.append(
            Instruction("wait_ms", name or f"wait-{ms}ms", {"ms": ms})
        )
        return self

    def wait_until(
        self, name: str, pred: Callable[[], bool], timeout_ms: int, poll_ms: int = 200
    ) -> "Score":
        if timeout_ms <= 0:
            raise ScoreError("wait_until timeout_ms must be positive")
        if poll_ms <= 0:
            raise ScoreError("wait_until poll_ms must be positive")
        self.instructions.append(
            Instruction(
                "wait_until",
                name,
                {"pred": pred, "timeout_ms": timeout_ms, "poll_ms": poll_ms},
            )
        )
        return self

    def exec(self, name: str, fn: Callable[[], Any]) -> "Score":
        if not callable(fn):
            raise ScoreError(f"exec {name!r}: fn must be callable")
        self.instructions.append(Instruction("exec", name, {"fn": fn}))
        return self

    def skip_if(self, name: str, pred: Callable[[], bool]) -> "Score":
        """If pred() is true, the NEXT exec instruction is skipped.

        Like the Copper's SKIP: it can only skip the immediately following
        exec; any other instruction type simply proceeds.
        """
        if not callable(pred):
            raise ScoreError(f"skip_if {name!r}: pred must be callable")
        self.instructions.append(Instruction("skip_if", name, {"pred": pred}))
        return self

    def __len__(self) -> int:
        return len(self.instructions)


# --------------------------------------------------------------------------
# receipts + runner
# --------------------------------------------------------------------------


@dataclass
class Receipt:
    """Honest record of a run: what happened, in clock order."""

    score_name: str
    completed: bool
    stopped_at: Optional[int] = None  # instruction index or None
    stop_reason: str = ""  # "" when completed
    events: List[Dict[str, Any]] = field(default_factory=list)

    def executed(self) -> List[str]:
        """Names of exec instructions that ran."""
        return [
            e["name"]
            for e in self.events
            if e["op"] == "exec" and e.get("status") == "ran"
        ]


def run(score: Score, clock: Optional[Any] = None) -> Receipt:
    """Execute a score. Timeouts and exec errors STOP the score and are
    recorded in the receipt; nothing is silently skipped."""
    clock = clock or RealClock()
    receipt = Receipt(score_name=score.name, completed=False)
    instrs = score.instructions
    i = 0
    n = len(instrs)

    def event(op: str, name: str, **detail: Any) -> None:
        entry = {"op": op, "name": name, "at_ms": clock.now_ms()}
        entry.update(detail)
        receipt.events.append(entry)

    while i < n:
        ins = instrs[i]
        if ins.op == "wait_ms":
            ms = ins.args["ms"]
            event("wait_ms", ins.name, ms=ms)
            clock.sleep_ms(ms)
        elif ins.op == "wait_until":
            pred = ins.args["pred"]
            timeout = ins.args["timeout_ms"]
            poll = ins.args["poll_ms"]
            deadline = clock.now_ms() + timeout
            event("wait_until", ins.name, timeout_ms=timeout)
            while True:
                if pred():
                    event("wait_until", ins.name, status="satisfied")
                    break
                if clock.now_ms() >= deadline:
                    event("wait_until", ins.name, status="timeout")
                    receipt.stopped_at = i
                    receipt.stop_reason = (
                        f"wait_until {ins.name!r} timed out after {timeout}ms"
                    )
                    return receipt
                clock.sleep_ms(poll)
        elif ins.op == "exec":
            fn = ins.args["fn"]
            start = clock.now_ms()
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                event(
                    "exec",
                    ins.name,
                    status="error",
                    elapsed_ms=clock.now_ms() - start,
                    error=f"{type(exc).__name__}: {exc}",
                )
                receipt.stopped_at = i
                receipt.stop_reason = f"exec {ins.name!r} raised"
                return receipt
            elapsed = clock.now_ms() - start
            event(
                "exec",
                ins.name,
                status="ran",
                elapsed_ms=elapsed,
                returned=repr(result)[:200],
            )
        elif ins.op == "skip_if":
            if ins.args["pred"]():
                # Copper SKIP: skip the immediately following exec only.
                if i + 1 < n and instrs[i + 1].op == "exec":
                    skipped = instrs[i + 1]
                    event("skip_if", ins.name, status="skipped", skipped=skipped.name)
                    i += 2
                    continue
                event("skip_if", ins.name, status="no-exec-after")
            else:
                event("skip_if", ins.name, status="not-skipped")
        i += 1

    receipt.completed = True
    return receipt
