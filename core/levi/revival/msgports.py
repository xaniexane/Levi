"""LEVI's message-port tasks — tiny actors, near-zero-cost mail.

Studied from: systems-internals survey (AmigaOS Exec, message-port
section).

The mechanism, functionally: lightweight tasks are coroutines. Each
task owns named message ports; sending a message is passing an object
reference — no serialization, no copying. A dispatch loop watches all
ports and delivers the highest-priority ready message first, waking the
task that was blocked receiving on that port.

Honesty: in-process simulation. Tasks are Python generators driven by
one dispatcher; "near-zero-cost" means references are passed, never
marshalled. Priority ordering is real within the model.
"""

from __future__ import annotations

import heapq
import itertools
from typing import Any, Dict, Generator, List, Optional, Tuple

ORIGIN = "levi-revival/msgports"


class PortError(Exception):
    """Base failure for message-port operations."""


class Message:
    """A message in flight: payload, priority, sender."""

    __slots__ = ("payload", "priority", "sender")

    def __init__(self, payload: Any, priority: int = 0, sender: str = ""):
        self.payload = payload
        self.priority = priority
        self.sender = sender

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Message(priority={self.priority}, sender={self.sender!r})"


class Send:
    """Yield this from a task to send a message (non-blocking)."""

    def __init__(self, port: str, payload: Any, priority: int = 0):
        self.port = port
        self.payload = payload
        self.priority = priority


class Recv:
    """Yield this from a task to block until a message arrives on a port."""

    def __init__(self, port: str):
        self.port = port


class MessagePort:
    """A named port: a priority queue of undelivered messages."""

    def __init__(self, name: str):
        self.name = name
        self._queue: List[Tuple[int, int, Message]] = []
        self._seq = itertools.count()

    def post(self, message: Message) -> None:
        # heap on (-priority, seq): highest priority first, FIFO on ties
        heapq.heappush(self._queue, (-message.priority, next(self._seq), message))

    def pop(self) -> Optional[Message]:
        if not self._queue:
            return None
        return heapq.heappop(self._queue)[2]

    def pending(self) -> int:
        return len(self._queue)


class Task:
    """A lightweight task: a named coroutine with a priority."""

    def __init__(
        self,
        name: str,
        body: Generator,
        priority: int = 0,
    ):
        self.name = name
        self.body = body
        self.priority = priority
        self.waiting_on: Optional[str] = None
        self.inbox: Optional[Message] = None
        self.done = False
        self.result: Any = None


class Dispatcher:
    """Drives tasks and delivers messages, highest priority first."""

    def __init__(self) -> None:
        self._ports: Dict[str, MessagePort] = {}
        self._tasks: Dict[str, Task] = {}

    # -- wiring --------------------------------------------------------
    def port(self, name: str) -> MessagePort:
        if name not in self._ports:
            self._ports[name] = MessagePort(name)
        return self._ports[name]

    def add_task(self, task: Task) -> None:
        if task.name in self._tasks:
            raise PortError(f"task {task.name!r} already registered")
        self._tasks[task.name] = task

    # -- the loop ------------------------------------------------------
    def _deliver_ready(self) -> bool:
        """Deliver ready messages, highest priority first.

        Returns True if at least one message was delivered.
        """
        # Collect (priority-key, port, message) for ports with waiting tasks.
        candidates: List[Tuple[Tuple[int, int], str, Message, Task]] = []
        seq = itertools.count()
        for task in self._tasks.values():
            if task.done or task.waiting_on is None or task.inbox is not None:
                continue
            port = self._ports.get(task.waiting_on)
            if port is None or port.pending() == 0:
                continue
            msg = port.pop()
            assert msg is not None
            candidates.append(((-msg.priority, next(seq)), port.name, msg, task))
        if not candidates:
            return False
        candidates.sort(key=lambda c: c[0])
        for _, _, msg, task in candidates:
            task.inbox = msg
            task.waiting_on = None
        return True

    def run(self, max_rounds: int = 10_000) -> Dict[str, Any]:
        """Run until every task is done or nothing can progress."""
        results: Dict[str, Any] = {}
        for _ in range(max_rounds):
            progressed = False
            for task in list(self._tasks.values()):
                if task.done:
                    continue
                if task.waiting_on is not None and task.inbox is None:
                    continue  # blocked on a message
                try:
                    if task.inbox is not None:
                        msg, task.inbox = task.inbox, None
                        request = task.body.send(msg)
                    else:
                        request = next(task.body)
                except StopIteration as stop:
                    task.done = True
                    task.result = stop.value
                    results[task.name] = stop.value
                    progressed = True
                    continue
                progressed = True
                if isinstance(request, Send):
                    self.port(request.port).post(
                        Message(request.payload, request.priority, task.name)
                    )
                elif isinstance(request, Recv):
                    task.waiting_on = request.port
                else:
                    raise PortError(
                        f"task {task.name!r} yielded unknown request {request!r}"
                    )
            if not self._deliver_ready():
                if all(t.done for t in self._tasks.values()):
                    break
                if not progressed:
                    break  # deadlock: everyone waiting, nothing pending
        return results

    def pending_counts(self) -> Dict[str, int]:
        return {name: port.pending() for name, port in self._ports.items()}
