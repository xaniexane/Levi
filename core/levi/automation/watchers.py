"""Polling trigger sources for the automation engine.

The engine consumes :class:`~levi.automation.engine.TriggerEvent`; this
module is the *producer* side — small stdlib-only watchers that notice
things changing and turn them into events. Nothing here sleeps and
nothing talks to the network:

* :class:`FileWatcher` — watches files/dirs for created/modified/deleted
  via ``(mtime_ns, size)`` snapshots (complements
  :mod:`levi.daemon.watchman`, which journals instead of emitting events);
* :class:`JournalWatcher` — tails a JSONL journal (e.g. the watchman
  journal) and converts each new line into an event, bridging daemon
  journals into the automation engine;
* :class:`CommandWatcher` — runs a local command on a poll schedule and
  emits an event when its stdout hash changes;
* :class:`TickWatcher` — emits ``"time"`` tick events every interval.

Clocks, runners, and the filesystem are injected so tests stay fast and
deterministic. :class:`WatcherHub` holds a named set of watchers and
polls them all in one call.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from .engine import TriggerEvent

__all__ = [
    "Watcher",
    "WatcherState",
    "FileWatcher",
    "JournalWatcher",
    "CommandWatcher",
    "TickWatcher",
    "WatcherHub",
]

# Clocks return epoch seconds as float; the default is wall time.
Clock = Callable[[], float]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WatcherState:
    """Persistent snapshot a watcher keeps between polls."""

    name: str
    snapshot: Dict[str, Any] = field(default_factory=dict)
    last_poll: float = 0.0


class Watcher:
    """Base class: ``poll(now)`` returns new :class:`TriggerEvent`s."""

    kind = "watcher"

    def __init__(self, name: str, *, clock: Clock | None = None) -> None:
        self.name = name
        self.clock: Clock = clock or _wall_clock
        self.state = WatcherState(name=name)

    def poll(self, now: float | None = None) -> List[TriggerEvent]:
        raise NotImplementedError

    def _event(self, kind: str, summary: str, payload: Dict[str, Any]) -> TriggerEvent:
        payload = dict(payload)
        payload.setdefault("watcher", self.name)
        return TriggerEvent(kind=kind, summary=summary, payload=payload)


def _wall_clock() -> float:
    return datetime.now(timezone.utc).timestamp()


class FileWatcher(Watcher):
    """Emit events when watched files change.

    ``paths`` may be files or directories (directories are scanned
    non-recursively unless ``recursive=True``). Each poll compares
    ``(mtime_ns, size)``; new paths → ``created``, changed → ``modified``,
    vanished → ``deleted``.
    """

    kind = "file"

    def __init__(
        self,
        name: str,
        paths: List[str],
        *,
        recursive: bool = False,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(name, clock=clock)
        self.paths = [Path(p) for p in paths]
        self.recursive = recursive

    def _scan(self) -> Dict[str, tuple[int, int]]:
        found: Dict[str, tuple[int, int]] = {}
        for root in self.paths:
            if root.is_file():
                found[str(root)] = self._sig(root)
            elif root.is_dir():
                pattern = "**/*" if self.recursive else "*"
                for child in root.glob(pattern):
                    if child.is_file():
                        found[str(child)] = self._sig(child)
            elif root.exists():
                continue
        return found

    @staticmethod
    def _sig(path: Path) -> tuple[int, int]:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)

    def poll(self, now: float | None = None) -> List[TriggerEvent]:
        current = self._scan()
        previous = self.state.snapshot
        events: List[TriggerEvent] = []
        for path, sig in current.items():
            prev = previous.get(path)
            prev_sig = tuple(prev) if isinstance(prev, list) else prev
            if prev is None:
                events.append(
                    self._event(
                        "file",
                        f"file created: {os.path.basename(path)}",
                        {"path": path, "change": "created"},
                    )
                )
            elif prev_sig != sig:
                events.append(
                    self._event(
                        "file",
                        f"file modified: {os.path.basename(path)}",
                        {"path": path, "change": "modified"},
                    )
                )
        for path in previous:
            if path not in current:
                events.append(
                    self._event(
                        "file",
                        f"file deleted: {os.path.basename(path)}",
                        {"path": path, "change": "deleted"},
                    )
                )
        self.state.snapshot = {k: list(v) for k, v in current.items()}
        self.state.last_poll = self.clock() if now is None else now
        return events


class JournalWatcher(Watcher):
    """Tail a JSONL journal and emit one event per new line.

    Bridges daemon journals (e.g. ``~/.levi/watchman/events.jsonl``) into
    the automation engine. The read offset is kept in memory; pass
    ``state_path`` to persist it across restarts. Unparseable lines are
    skipped honestly (counted in ``payload["skipped_lines"]`` on the next
    good event, and in the watcher state).
    """

    kind = "journal"

    def __init__(
        self,
        name: str,
        journal_path: str,
        *,
        event_kind: str = "journal",
        clock: Clock | None = None,
    ) -> None:
        super().__init__(name, clock=clock)
        self.journal_path = Path(journal_path)
        self.event_kind = event_kind

    def poll(self, now: float | None = None) -> List[TriggerEvent]:
        offset = int(self.state.snapshot.get("offset", 0))
        skipped = int(self.state.snapshot.get("skipped", 0))
        events: List[TriggerEvent] = []
        if not self.journal_path.exists():
            self.state.last_poll = self.clock() if now is None else now
            return events
        with self.journal_path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size < offset:  # journal rotated/truncated — start over
                offset = 0
            fh.seek(offset)
            chunk = fh.read()
            new_offset = fh.tell()
        for raw in chunk.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                skipped += 1
                continue
            if not isinstance(entry, dict):
                skipped += 1
                continue
            summary = str(entry.get("summary") or entry.get("kind") or "journal entry")
            events.append(
                self._event(
                    self.event_kind,
                    summary,
                    {"entry": entry, "journal": str(self.journal_path)},
                )
            )
        if events and skipped:
            events[0].payload["skipped_lines"] = skipped
            skipped = 0
        self.state.snapshot = {"offset": new_offset, "skipped": skipped}
        self.state.last_poll = self.clock() if now is None else now
        return events


# A runner executes a command and returns (returncode, stdout_bytes).
Runner = Callable[[List[str]], tuple[int, bytes]]


def _default_runner(argv: List[str]) -> tuple[int, bytes]:
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WatcherError(f"command watcher could not run {argv[0]!r}: {exc}") from exc
    return proc.returncode, proc.stdout


class WatcherError(Exception):
    """A watcher could not do its job (bad path, command failed to run)."""


class CommandWatcher(Watcher):
    """Run a local command each poll; emit when stdout changes.

    The command's stdout is hashed (sha256); an event fires only when the
    hash differs from the previous poll, so quiet commands stay quiet.
    ``runner`` is injectable for tests. A command that cannot even be
    started raises :class:`WatcherError`; a nonzero exit is *not* an
    error — the output is still hashed and compared.
    """

    kind = "command"

    def __init__(
        self,
        name: str,
        argv: List[str],
        *,
        runner: Runner | None = None,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(name, clock=clock)
        if not argv:
            raise WatcherError("CommandWatcher needs a non-empty argv")
        self.argv = list(argv)
        self.runner: Runner = runner or _default_runner

    def poll(self, now: float | None = None) -> List[TriggerEvent]:
        returncode, stdout = self.runner(self.argv)
        digest = hashlib.sha256(stdout).hexdigest()
        previous = self.state.snapshot.get("digest")
        events: List[TriggerEvent] = []
        if previous is not None and previous != digest:
            events.append(
                self._event(
                    "command",
                    f"command output changed: {' '.join(self.argv)}",
                    {
                        "argv": self.argv,
                        "returncode": returncode,
                        "output_bytes": len(stdout),
                    },
                )
            )
        self.state.snapshot = {"digest": digest, "returncode": returncode}
        self.state.last_poll = self.clock() if now is None else now
        return events


class TickWatcher(Watcher):
    """Emit a ``"time"`` tick event every ``interval_sec``."""

    kind = "time"

    def __init__(
        self, name: str, interval_sec: float = 300.0, *, clock: Clock | None = None
    ) -> None:
        super().__init__(name, clock=clock)
        if interval_sec <= 0:
            raise WatcherError("TickWatcher interval_sec must be positive")
        self.interval_sec = interval_sec

    def poll(self, now: float | None = None) -> List[TriggerEvent]:
        now = self.clock() if now is None else now
        last = self.state.snapshot.get("last_tick")
        if last is None:
            # First poll arms the timer but emits nothing — no thundering
            # burst of ticks on startup.
            self.state.snapshot = {"last_tick": now}
            self.state.last_poll = now
            return []
        if now - float(last) >= self.interval_sec:
            self.state.snapshot = {"last_tick": now}
            self.state.last_poll = now
            return [
                self._event(
                    "time",
                    f"tick: {self.name}",
                    {"interval_sec": self.interval_sec},
                )
            ]
        self.state.last_poll = now
        return []


class WatcherHub:
    """A named set of watchers polled together."""

    def __init__(self, watchers: List[Watcher] | None = None) -> None:
        self.watchers: List[Watcher] = list(watchers or [])

    def add(self, watcher: Watcher) -> None:
        if any(w.name == watcher.name for w in self.watchers):
            raise WatcherError(f"watcher {watcher.name!r} already registered")
        self.watchers.append(watcher)

    def remove(self, name: str) -> bool:
        before = len(self.watchers)
        self.watchers = [w for w in self.watchers if w.name != name]
        return len(self.watchers) < before

    def poll_all(self, now: float | None = None) -> List[TriggerEvent]:
        events: List[TriggerEvent] = []
        for watcher in self.watchers:
            events.extend(watcher.poll(now))
        return events

    def describe(self) -> List[Dict[str, Any]]:
        return [
            {"name": w.name, "kind": w.kind, "last_poll": w.state.last_poll}
            for w in self.watchers
        ]
