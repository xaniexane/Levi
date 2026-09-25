"""Pneumatic dispatch routing: tube-vs-courier store-and-forward routing.

History: the 19th–20th-century *poste pneumatique* — networks of
pressurized tubes carrying sealed carriers between post/telegraph offices.
Paris ran 1866–1984, peaking at 427 km of tubes and 130 offices: a message
crossed the city in minutes — tube to the district office, courier for the
last mile. A physical packet-switched network with routing, addressing,
and store-and-forward. Telephone, telex, fax, then the internet killed it;
the routing *topology* is what survives.

In LEVI: the tube/courier discipline for the information diet. Every task
is explicitly labeled tube-or-courier and routed accordingly instead of
treating all notifications as equal:
- TUBE: bulk/scheduled work (digests, backups, batch processing) — held,
  batched, and dispatched off-peak as one manifest.
- COURIER: anything needing judgment — delivered immediately, never batched.
The routing table persists as JSON under ``~/.levi/methods/``; every
decision is logged with the rule that made it, so the routing is auditable.

Honesty: INSPIRATIONAL — the value is the routing discipline (separate the
trunk from the last mile), not the tubes. No real network is involved;
"tube" here means "batched and deferred by policy".
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import _persist


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

TUBE = "tube"
COURIER = "courier"


@dataclass
class Task:
    """Something to be dispatched."""

    task_id: str
    kind: str
    title: str
    urgency: int = 0  # 0..10; >= 8 is courier by the default rule
    payload: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        if not self.kind or not self.kind.strip():
            raise ValueError("kind must be non-empty")
        if not 0 <= self.urgency <= 10:
            raise ValueError("urgency must be 0..10")


@dataclass
class Rule:
    """A routing rule: regex over ``kind``/``title`` -> channel."""

    pattern: str
    channel: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.channel not in (TUBE, COURIER):
            raise ValueError(f"channel must be {TUBE!r} or {COURIER!r}")
        try:
            self._rx = re.compile(self.pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"invalid rule pattern {self.pattern!r}: {exc}") from exc

    def matches(self, task: Task) -> bool:
        return bool(self._rx.search(task.kind) or self._rx.search(task.title))

    def to_dict(self) -> dict:
        return {"pattern": self.pattern, "channel": self.channel, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        return cls(data["pattern"], data["channel"], data.get("reason", ""))


@dataclass
class Decision:
    task_id: str
    channel: str
    rule: str
    reason: str
    decided_at: float = field(default_factory=time.time)


class RoutingTable:
    """Ordered rules; first match wins. Ends with an explicit default rule."""

    DEFAULT_REASON = (
        "default: urgent (>=8) goes courier, everything else rides the tube"
    )

    def __init__(self, store: str | None = None):
        self.rules: list[Rule] = []
        self._store = _persist.store_path(store or "pneumatic-routes")
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        self.rules = [Rule.from_dict(r) for r in data.get("rules", [])]

    def save(self) -> None:
        _persist.save_json(self._store, {"rules": [r.to_dict() for r in self.rules]})

    def add_rule(self, pattern: str, channel: str, reason: str = "") -> Rule:
        rule = Rule(pattern, channel, reason)
        self.rules.append(rule)
        return rule

    def route(self, task: Task) -> Decision:
        for rule in self.rules:
            if rule.matches(task):
                return Decision(
                    task.task_id,
                    rule.channel,
                    rule.pattern,
                    rule.reason or "matched rule",
                )
        # The explicit default: the trunk/last-mile split.
        channel = COURIER if task.urgency >= 8 else TUBE
        return Decision(task.task_id, channel, "<default>", self.DEFAULT_REASON)


class Dispatcher:
    """Routes tasks; tubes accumulate until flushed, couriers go at once."""

    def __init__(self, table: RoutingTable | None = None):
        self.table = table or RoutingTable()
        self._held: list[Task] = []  # the tube manifest, awaiting dispatch
        self.decisions: list[Decision] = []
        self.courier_log: list[dict] = []

    def dispatch(self, task: Task) -> Decision:
        """Route one task. TUBE tasks are held; COURIER tasks go immediately."""
        decision = self.table.route(task)
        self.decisions.append(decision)
        if decision.channel == TUBE:
            self._held.append(task)
        else:
            self.courier_log.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "urgency": task.urgency,
                    "sent_at": decision.decided_at,
                }
            )
        return decision

    def held(self) -> list[Task]:
        return list(self._held)

    def flush_tubes(self) -> dict:
        """Dispatch the accumulated tube batch as one manifest (the scheduled run)."""
        batch = self._held
        self._held = []
        manifest = {
            "dispatched_at": time.time(),
            "count": len(batch),
            "tasks": [
                {"task_id": t.task_id, "kind": t.kind, "title": t.title} for t in batch
            ],
        }
        return manifest


__all__ = [
    "TUBE",
    "COURIER",
    "Task",
    "Rule",
    "Decision",
    "RoutingTable",
    "Dispatcher",
]
