"""The LEVI event bus — one organism, one event stream.

This is a stdlib-only, in-process publish/subscribe bus that lets the
bloodstream subsystems hear each other without coupling: growth publishes
learnings, the archive publishes ingestions, the hunt publishes findings,
and the turn pipeline publishes a summary of every completed turn.

Topic naming convention (enforced)::

    levi.<subsystem>.<event>

Payloads must be JSON-serializable — the bus validates and rejects
otherwise, because every publish appends to the decision trace.

Trace binding: ``publish()`` writes an event record via
:class:`levi.bloodstream.trace.TraceWriter` *only while a trace is active*
(see :func:`trace_scope`). Outside a turn there is no disk write — the
bus is pure fan-out. Handler exceptions are isolated: one failing
subscriber never breaks the bus or the turn; failures are recorded in
the trace event.
"""

from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from levi.bloodstream.trace import TraceWriter


_TOPIC_RE = re.compile(r"^levi\.[a-z0-9_]+(?:\.[a-z0-9_]+)*$")

Handler = Callable[[str, Dict[str, Any]], None]

# topic -> token -> handler
_subscribers: Dict[str, Dict[str, Handler]] = {}
# every topic ever published in this process (for topics())
_seen_topics: set = set()
# active trace binding: (trace_id, base_dir) — None outside a trace scope
_active: ContextVar[Optional[Tuple[str, Optional[Path]]]] = ContextVar(
    "levi_bus_active_trace", default=None
)


def _validate_topic(topic: str) -> str:
    if not isinstance(topic, str) or not _TOPIC_RE.match(topic):
        raise ValueError(
            f"invalid topic {topic!r}: topics must look like "
            "'levi.<subsystem>.<event>' (lowercase, dot-separated)"
        )
    return topic


def _validate_payload(payload: Dict[str, Any], topic: str) -> None:
    if not isinstance(payload, dict):
        raise TypeError(
            f"bus payload for {topic!r} must be a dict, got {type(payload).__name__}"
        )
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"bus payload for {topic!r} is not JSON-serializable: {exc}"
        ) from exc


def subscribe(topic: str, handler: Handler) -> str:
    """Subscribe *handler* to *topic*. Returns an opaque token for
    :func:`unsubscribe`. Handler signature: ``(topic, payload)``."""
    _validate_topic(topic)
    if not callable(handler):
        raise TypeError("bus handler must be callable")
    token = uuid.uuid4().hex
    _subscribers.setdefault(topic, {})[token] = handler
    return token


def unsubscribe(token: str) -> bool:
    """Remove a subscription by token. Returns True when it existed."""
    for topic, handlers in _subscribers.items():
        if token in handlers:
            del handlers[token]
            if not handlers:
                del _subscribers[topic]
            return True
    return False


def topics() -> List[str]:
    """Every topic this process has published or been subscribed to."""
    return sorted(_seen_topics | set(_subscribers))


def publish(topic: str, payload: Dict[str, Any]) -> None:
    """Publish *payload* to *topic*.

    Validates the topic name and JSON-serializability, fans out to every
    subscriber (each isolated from the others), then — when a trace is
    active — appends an event record to the trace via TraceWriter.
    """
    _validate_topic(topic)
    _validate_payload(payload, topic)
    _seen_topics.add(topic)

    errors: List[str] = []
    for handler in list(_subscribers.get(topic, {}).values()):
        try:
            handler(topic, payload)
        except Exception as exc:  # noqa: BLE001 — isolation, recorded below
            errors.append(f"{type(exc).__name__}: {exc}"[:200])

    binding = _active.get()
    if binding is not None:
        trace_id, base_dir = binding
        try:
            writer = TraceWriter(base_dir=base_dir)
            writer.write(
                {
                    "trace_id": trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "bus.publish",
                    "topic": topic,
                    "payload": payload,
                    "handler_errors": errors,
                }
            )
        except Exception:  # noqa: BLE001 — the bus never breaks a turn
            pass


@contextmanager
def trace_scope(trace_id: str, base_dir: Optional[Path] = None) -> Iterator[None]:
    """Bind ``publish()`` to a trace: while inside the scope, every
    publish appends an event record to *trace_id* (TraceWriter under
    *base_dir*, defaulting to ``~/.levi/traces``)."""
    token = _active.set((trace_id, base_dir))
    try:
        yield
    finally:
        _active.reset(token)


def reset_bus() -> None:
    """Clear subscriptions, seen topics, and the active trace binding
    (tests, fresh starts)."""
    _subscribers.clear()
    _seen_topics.clear()
    _active.set(None)
