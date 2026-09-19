"""Run commands on machines you aren't connected to.

Studied from: protocols-hunt-20260916-0041/report.md (Find 2 - UUCP)

The load-bearing mechanism: with no persistent connection, remote
execution becomes *mail*. A job carries the command line plus input
files; it waits in the outbox until the link is up, crosses with the
next transfer, and the far side executes it through a strict
allow-list and mails the result back as a new job. Nothing executes
that isn't explicitly permitted; nothing blocks while waiting.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is queued remote execution with
allow-listed commands and asynchronous result mail. Not revived: a
real distributed filesystem — input/output "files" are named string
blobs carried with the job, not remote reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable


ORIGIN = "levi-revival/remote-queued-exec"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class QueuedExecError(Exception):
    """Base class for queued-execution failures."""


class ExecState(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    RUNNING = "running"
    DONE = "done"
    DENIED = "denied"
    FAILED = "failed"


@dataclass
class ExecJob:
    """A remote command packaged as mail."""

    job_id: str
    command: str  # the program name, e.g. "wordcount"
    args: list[str] = field(default_factory=list)
    stdin_data: str = ""  # carried input
    input_files: dict[str, str] = field(default_factory=dict)  # name -> content
    requester: str = ""  # who asked for this
    state: ExecState = ExecState.QUEUED
    result: str = ""
    output_files: dict[str, str] = field(default_factory=dict)
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None


@dataclass
class Allowlist:
    """The explicit command policy of a receiving host.

    Only commands registered here may execute. Handlers are pure
    Python callables: ``handler(job) -> str`` returning stdout text.
    """

    commands: dict[str, Callable[[ExecJob], str]] = field(default_factory=dict)

    def register(self, name: str, handler: Callable[[ExecJob], str]) -> None:
        self.commands[name] = handler

    def permitted(self, name: str) -> bool:
        return name in self.commands

    def run(self, job: ExecJob) -> str:
        handler = self.commands.get(job.command)
        if handler is None:
            raise QueuedExecError(f"command not permitted: {job.command!r}")
        return handler(job)


# ---------------------------------------------------------------------------
# Host
# ---------------------------------------------------------------------------


class QueuedExecHost:
    """One machine: an outbox of requests and an allow-list of commands."""

    def __init__(self, name: str, allowlist: Allowlist | None = None) -> None:
        self.name = name
        self.allowlist = allowlist or Allowlist()
        self.outbox: list[ExecJob] = []  # requests awaiting the link
        self.inbox: list[ExecJob] = []  # finished results awaiting pickup
        self.running: list[ExecJob] = []  # requests received, not yet run

    # -- requesting ----------------------------------------------------------

    def request(self, job: ExecJob) -> ExecJob:
        """Queue a remote-execution request for the next connection."""
        job.requester = self.name
        job.state = ExecState.QUEUED
        self.outbox.append(job)
        return job

    # -- transport -----------------------------------------------------------

    def link(self, other: "QueuedExecHost") -> int:
        """One connection: push our outbox to the peer's running list.

        Returns the number of jobs handed over. Jobs leave our outbox;
        results come back the same way in reverse — the caller is
        expected to link both directions or alternate.
        """
        sent = 0
        remaining: list[ExecJob] = []
        for job in self.outbox:
            job.state = ExecState.SENT
            other.running.append(job)
            sent += 1
        self.outbox = remaining
        # Pull results addressed back to us.
        for job in list(other.inbox):
            if job.requester == self.name and job.state in (
                ExecState.DONE,
                ExecState.DENIED,
                ExecState.FAILED,
            ):
                other.inbox.remove(job)
                self.inbox.append(job)
        return sent

    # -- execution -------------------------------------------------------------

    def execute_pending(self) -> list[ExecJob]:
        """Run every received request through the allow-list."""
        finished: list[ExecJob] = []
        for job in self.running:
            job.state = ExecState.RUNNING
            try:
                if not self.allowlist.permitted(job.command):
                    job.state = ExecState.DENIED
                    job.error = f"denied: {job.command!r} not allow-listed"
                else:
                    job.result = self.allowlist.run(job)
                    job.state = ExecState.DONE
            except Exception as exc:  # a handler bug must not kill the host
                job.state = ExecState.FAILED
                job.error = f"handler error: {exc}"
            job.finished_at = datetime.now().isoformat()
            self.inbox.append(job)
            finished.append(job)
        self.running = []
        return finished

    # -- queries ---------------------------------------------------------------

    def results_for(self, requester: str | None = None) -> list[ExecJob]:
        return [j for j in self.inbox if requester is None or j.requester == requester]
