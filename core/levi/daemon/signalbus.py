"""Daemon signal bus — topics, subscribers, and an honest journal.

LEVI's daemons (heartbeat, watchman, supervisor, automations) talk past
each other today: each polls, none signal. The signal bus is the local,
stdlib-only pub/sub between them. Topics are dotted names
(``"heartbeat.pulse"``, ``"watchman.file.modified"``); subscriptions may
match exactly or with a trailing wildcard (``"watchman.file.*"``).

Every publish is appended to an owner-only JSONL journal (``~/.levi/
daemon_signalbus.jsonl``), so a restarted subscriber can *replay* what
it missed instead of pretending it never happened. History is bounded:
the journal is trimmed to the newest ``journal_cap`` events on publish.

No network, no threads, no daemonization here — the bus is a library
the daemons embed; dispatch is synchronous in the publisher's process.

Stdlib only, local-first.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_JOURNAL_PATH = Path.home() / ".levi" / "daemon_signalbus.jsonl"
JOURNAL_CAP = 10_000


class SignalBusError(Exception):
    """Bad topic, bad pattern, or bad journal for the signal bus."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SignalEvent:
    """One published signal."""

    id: str
    topic: str
    publisher: str
    at: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SignalEvent":
        return SignalEvent(
            id=str(data["id"]),
            topic=str(data["topic"]),
            publisher=str(data["publisher"]),
            at=str(data["at"]),
            payload=dict(data.get("payload") or {}),
        )


def validate_topic(topic: str) -> str:
    """A topic is lowercase dotted segments; a subscription may add ``.*``."""
    if not isinstance(topic, str) or not topic:
        raise SignalBusError("topic must be a non-empty string")
    body = topic[:-2] if topic.endswith(".*") else topic
    if not body or not all(
        seg and all(c.islower() or c.isdigit() or c == "_" for c in seg)
        for seg in body.split(".")
    ):
        raise SignalBusError(
            f"invalid topic {topic!r}: dotted lowercase segments, optional '.*'"
        )
    return topic


def pattern_matches(pattern: str, topic: str) -> bool:
    """Exact match, or prefix match when the pattern ends in ``.*``."""
    validate_topic(pattern)
    validate_topic(topic)
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return topic == prefix or topic.startswith(prefix + ".")
    return pattern == topic


class SignalBus:
    """In-process pub/sub with a persistent journal.

    Subscriptions are in-memory (the process owns them); the journal is
    on disk so missed events survive restarts.
    """

    def __init__(
        self,
        journal_path: Optional[Path] = None,
        journal_cap: int = JOURNAL_CAP,
    ) -> None:
        self.journal_path = Path(journal_path) if journal_path else DEFAULT_JOURNAL_PATH
        self.journal_cap = max(1, int(journal_cap))
        self._subs: Dict[str, str] = {}  # subscriber_id -> pattern

    # -- subscriptions ---------------------------------------------------

    def subscribe(self, subscriber_id: str, pattern: str) -> None:
        if not subscriber_id:
            raise SignalBusError("subscriber_id must be non-empty")
        self._subs[subscriber_id] = validate_topic(pattern)

    def unsubscribe(self, subscriber_id: str) -> bool:
        return self._subs.pop(subscriber_id, None) is not None

    def subscribers(self) -> Dict[str, str]:
        return dict(self._subs)

    # -- publish ----------------------------------------------------------

    def publish(
        self, topic: str, payload: Optional[Dict[str, Any]], publisher: str
    ) -> SignalEvent:
        """Publish a signal; returns the journaled event.

        Dispatch is synchronous: every subscriber whose pattern matches
        is recorded as a recipient in the event payload under
        ``"_recipients"`` — honest routing, never silent drops. The actual
        *delivery* is the caller's job (in-process subscribers read
        :meth:`history` / :meth:`replay`); the bus never pretends to push
        across processes.
        """
        validate_topic(topic)
        if not publisher:
            raise SignalBusError("publisher must be non-empty")
        recipients = sorted(
            sid for sid, pat in self._subs.items() if pattern_matches(pat, topic)
        )
        event = SignalEvent(
            id=uuid.uuid4().hex,
            topic=topic,
            publisher=publisher,
            at=_utcnow_iso(),
            payload=dict(payload or {}),
        )
        event.payload["_recipients"] = recipients
        self._append(event)
        return event

    # -- journal ----------------------------------------------------------

    def _append(self, event: SignalEvent) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), separators=(",", ":"))
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        try:
            os.chmod(self.journal_path, 0o600)
        except OSError:
            pass
        self._trim()

    def _trim(self) -> None:
        try:
            with open(self.journal_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            return
        if len(lines) > self.journal_cap:
            with open(self.journal_path, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-self.journal_cap :])

    def history(
        self, topic: Optional[str] = None, limit: int = 100
    ) -> List[SignalEvent]:
        """Newest-first journal read; optional exact-topic filter."""
        if topic is not None:
            validate_topic(topic)
        events: List[SignalEvent] = []
        try:
            with open(self.journal_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = SignalEvent.from_dict(json.loads(line))
                    except (ValueError, KeyError, TypeError):
                        continue  # a corrupt line is skipped, never fatal
                    if topic is None or ev.topic == topic:
                        events.append(ev)
        except FileNotFoundError:
            return []
        return events[-max(1, limit) :][::-1]

    def replay(
        self, subscriber_id: str, since_id: Optional[str] = None
    ) -> List[SignalEvent]:
        """Events the subscriber would have received, oldest-first.

        ``since_id`` is the last event the subscriber already processed;
        replay returns everything journaled after it. ``None`` replays all.
        """
        pattern = self._subs.get(subscriber_id)
        if pattern is None:
            raise SignalBusError(f"unknown subscriber {subscriber_id!r}")
        events = self.history(limit=self.journal_cap)[::-1]  # oldest-first
        if since_id is not None:
            idx = next((i for i, e in enumerate(events) if e.id == since_id), None)
            events = events[idx + 1 :] if idx is not None else []
        return [e for e in events if pattern_matches(pattern, e.topic)]


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.signalbus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish", help="publish one signal")
    p.add_argument("topic")
    p.add_argument("--publisher", default="cli")
    p.add_argument("--payload", default="{}")
    t = sub.add_parser("tail", help="show recent journaled signals")
    t.add_argument("--topic", default=None)
    t.add_argument("--limit", type=int, default=20)
    args = ap.parse_args(argv)

    bus = SignalBus()
    if args.cmd == "publish":
        try:
            payload = json.loads(args.payload)
        except ValueError as exc:
            print(f"bad --payload JSON: {exc}")
            return 2
        ev = bus.publish(args.topic, payload, args.publisher)
        print(json.dumps(ev.to_dict(), indent=2))
    else:
        for ev in bus.history(topic=args.topic, limit=args.limit):
            print(f"{ev.at}  {ev.topic}  <- {ev.publisher}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
