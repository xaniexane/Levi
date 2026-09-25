"""Local-first CI with no minute metering: pipelines as plain local scripts.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 4]

The mechanism: a pipeline is ordinary data — a list of steps, each a local
command with dependencies, timeouts, and retries. A local ``Runner``
executes them with ``subprocess`` (never a remote executor), records a
``RunRecord`` per step (exit code, duration, captured output), and a
``LocalCI`` daemon-queue drains queued pipelines in order. Because there is
no cloud, there is no meter: ``minutes_used`` reports 0 and
``minutes_remaining`` is infinity — the billing model is the absence of
one.

Design notes, kept honest:

- Steps run as the local user with the user's full local privileges.
  There is no sandbox, no container, no isolation. A malicious pipeline
  definition can do anything the user can do — this is a runner, not a
  jail. Run only pipelines you can read.
- Retries are bounded; a step that keeps failing fails the pipeline and
  the record says so. The queue never silently drops work.
- "Infinite minutes" is not a pricing trick, it is the literal truth
  about a local runner: nobody is counting but you.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/local-ci"


@dataclass
class Step:
    """One pipeline step: a local command, its deps, timeout, and retries."""

    name: str
    command: List[str]
    needs: List[str] = field(default_factory=list)
    timeout: float = 300.0
    retries: int = 0
    cwd: str = ""


@dataclass
class RunRecord:
    """What one step execution did: exit code, wall time, captured output."""

    step: str
    attempt: int
    exit_code: int
    duration: float
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class PipelineResult:
    """The whole pipeline's verdict: per-step records and the failed step, if any."""

    pipeline: str
    records: List[RunRecord]
    failed_step: str | None
    duration: float

    @property
    def ok(self) -> bool:
        return self.failed_step is None


class Pipeline:
    """A pipeline as plain data: named steps, explicit dependency order."""

    def __init__(self, name: str):
        self.name = name
        self._steps: Dict[str, Step] = {}

    def add_step(self, step: Step) -> "Pipeline":
        if step.name in self._steps:
            raise ValueError(f"duplicate step name: {step.name!r}")
        self._steps[step.name] = step
        return self

    def steps(self) -> List[Step]:
        return list(self._steps.values())

    def order(self) -> List[Step]:
        """Topological order over ``needs``; raises on cycles or missing deps."""
        ordered: List[Step] = []
        visiting: List[str] = []
        done: set = set()

        def visit(name: str) -> None:
            if name in done:
                return
            if name in visiting:
                raise ValueError(f"dependency cycle involving {name!r}")
            step = self._steps.get(name)
            if step is None:
                raise ValueError(f"unknown dependency {name!r}")
            visiting.append(name)
            for dep in step.needs:
                visit(dep)
            visiting.pop()
            done.add(name)
            ordered.append(step)

        for name in self._steps:
            visit(name)
        return ordered


class Runner:
    """Execute pipeline steps locally via subprocess. No remote anything."""

    def run_step(self, step: Step) -> RunRecord:
        """Run one step, retrying up to ``step.retries`` times on failure."""
        last: RunRecord | None = None
        for attempt in range(step.retries + 1):
            start = time.time()
            try:
                proc = subprocess.run(
                    step.command,
                    cwd=step.cwd or None,
                    capture_output=True,
                    text=True,
                    timeout=step.timeout,
                )
                record = RunRecord(
                    step=step.name,
                    attempt=attempt,
                    exit_code=proc.returncode,
                    duration=time.time() - start,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                )
            except subprocess.TimeoutExpired as exc:
                record = RunRecord(
                    step=step.name,
                    attempt=attempt,
                    exit_code=124,
                    duration=time.time() - start,
                    stdout=exc.stdout.decode() if exc.stdout else "",
                    stderr=f"timeout after {step.timeout}s",
                )
            except FileNotFoundError as exc:
                record = RunRecord(
                    step=step.name,
                    attempt=attempt,
                    exit_code=127,
                    duration=time.time() - start,
                    stdout="",
                    stderr=str(exc),
                )
            if record.ok:
                return record
            last = record
        return last  # type: ignore[return-value]

    def run_pipeline(self, pipeline: Pipeline) -> PipelineResult:
        """Run steps in dependency order; stop at the first failure."""
        start = time.time()
        records: List[RunRecord] = []
        failed: str | None = None
        for step in pipeline.order():
            record = self.run_step(step)
            records.append(record)
            if not record.ok:
                failed = step.name
                break
        return PipelineResult(
            pipeline=pipeline.name,
            records=records,
            failed_step=failed,
            duration=time.time() - start,
        )


class LocalCI:
    """The local runner daemon's queue: pipelines in, results out, no meter."""

    def __init__(self):
        self._queue: List[Pipeline] = []
        self._results: List[PipelineResult] = []
        self._runner = Runner()

    def enqueue(self, pipeline: Pipeline) -> None:
        self._queue.append(pipeline)

    def queued(self) -> List[str]:
        return [p.name for p in self._queue]

    def drain(self) -> List[PipelineResult]:
        """Run every queued pipeline in FIFO order, recording each result."""
        results: List[PipelineResult] = []
        while self._queue:
            pipeline = self._queue.pop(0)
            result = self._runner.run_pipeline(pipeline)
            self._results.append(result)
            results.append(result)
        return results

    def history(self) -> List[PipelineResult]:
        return list(self._results)

    # -- the no-meter promise ----------------------------------------------
    @staticmethod
    def minutes_used() -> int:
        return 0

    @staticmethod
    def minutes_remaining() -> float:
        return float("inf")

    @staticmethod
    def billing_model() -> str:
        return "no meter: the runner is your machine; minutes are infinite"
