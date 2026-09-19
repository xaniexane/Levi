"""Trunk-vs-last-mile routing — batch the bulk, courier the judgment.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #33).

The mechanism under study: separate the **trunk** from the **last
mile**. Bulk, scheduled work travels in batched high-throughput runs
between hubs — predictable, off-peak, cheap. Anything needing judgment
goes **courier**: individually routed, with its context, immediately.
The discipline is explicit labeling: every work item is classified as
trunk or courier by the dispatcher, instead of everything arriving as
equal-urgency noise.

This is an original, from-scratch implementation for LEVI. A
``WorkItem`` carries what it needs; the ``Dispatcher`` classifies it
trunk or courier (judgment-need beats everything; scheduled bulk goes
trunk; explicit override wins). ``TrunkLine`` batches items hub-to-hub
and flushes them as manifests; ``CourierPool`` routes items one by one
with their context attached. ``route()`` runs the whole dispatch and
returns a report with the split.

Public surface:
- ``WorkItem``: id, payload, hubs, flags (needs_judgment, scheduled,
  urgent, override).
- ``Dispatcher``: ``classify(item) -> str``; ``route(items)``.
- ``TrunkLine``: ``collect``, ``flush() -> manifest``.
- ``CourierPool``: ``dispatch(item) -> assignment``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/pneumatic"


class DispatchError(Exception):
    """The dispatcher refused: bad item, unknown hub, no route."""


TRUNK = "trunk"
COURIER = "courier"


@dataclass
class WorkItem:
    """One unit of work to be routed."""

    id: str
    payload: str
    from_hub: str = "central"
    to_hub: str = "central"
    needs_judgment: bool = False
    scheduled: bool = False
    urgent: bool = False
    override: str = ""  # explicit "trunk" or "courier" beats the rules
    context: str = ""  # the judgment context, carried by the courier


@dataclass
class TrunkBatch:
    from_hub: str
    to_hub: str
    item_ids: List[str] = field(default_factory=list)


@dataclass
class CourierAssignment:
    item_id: str
    from_hub: str
    to_hub: str
    context: str
    reason: str


@dataclass
class RoutingReport:
    trunk_items: int
    courier_items: int
    batches: List[TrunkBatch]
    assignments: List[CourierAssignment]
    decisions: List[Tuple[str, str, str]]  # (item_id, lane, reason)


class TrunkLine:
    """The tubes: batched high-throughput transport between hubs."""

    def __init__(self, hubs: List[str]) -> None:
        if not hubs:
            raise DispatchError("a trunk line needs at least one hub")
        self.hubs = list(hubs)
        self._queue: List[WorkItem] = []

    def collect(self, item: WorkItem) -> None:
        if item.from_hub not in self.hubs or item.to_hub not in self.hubs:
            raise DispatchError(f"unknown hub on item '{item.id}'")
        self._queue.append(item)

    def pending(self) -> int:
        return len(self._queue)

    def flush(self) -> List[TrunkBatch]:
        """Dispatch one scheduled run: group queued items hub-to-hub."""
        grouped: Dict[Tuple[str, str], TrunkBatch] = {}
        for item in self._queue:
            key = (item.from_hub, item.to_hub)
            grouped.setdefault(key, TrunkBatch(item.from_hub, item.to_hub))
            grouped[key].item_ids.append(item.id)
        self._queue = []
        return list(grouped.values())


class CourierPool:
    """The last mile: individual routing, context attached, immediately."""

    def __init__(self, hubs: List[str]) -> None:
        if not hubs:
            raise DispatchError("a courier pool needs at least one hub")
        self.hubs = list(hubs)
        self.delivered: List[CourierAssignment] = []

    def dispatch(self, item: WorkItem, reason: str) -> CourierAssignment:
        if item.from_hub not in self.hubs or item.to_hub not in self.hubs:
            raise DispatchError(f"unknown hub on item '{item.id}'")
        assignment = CourierAssignment(
            item_id=item.id,
            from_hub=item.from_hub,
            to_hub=item.to_hub,
            context=item.context or item.payload,
            reason=reason,
        )
        self.delivered.append(assignment)
        return assignment


class Dispatcher:
    """Makes the split: bulk/scheduled to the trunk, judgment to the courier."""

    def __init__(self, hubs: List[str]) -> None:
        self.trunk = TrunkLine(hubs)
        self.couriers = CourierPool(hubs)

    def classify(self, item: WorkItem) -> Tuple[str, str]:
        """Label one item (trunk|courier) with the reason, in priority order.

        1. explicit override wins; 2. needs_judgment -> courier;
        3. urgent -> courier; 4. scheduled bulk -> trunk; 5. default trunk.
        """
        if item.override in (TRUNK, COURIER):
            return item.override, "explicit override"
        if item.needs_judgment:
            return COURIER, "needs judgment — routed with context"
        if item.urgent:
            return COURIER, "urgent exception — couriered immediately"
        if item.scheduled:
            return TRUNK, "scheduled bulk — batched between hubs"
        return TRUNK, "default: bulk-compatible, travels the tubes"

    def route(self, items: List[WorkItem]) -> RoutingReport:
        """Classify every item, then dispatch: batches for the trunk,
        individual assignments for the couriers."""
        report = RoutingReport(0, 0, [], [], [])
        for item in items:
            lane, reason = self.classify(item)
            report.decisions.append((item.id, lane, reason))
            if lane == TRUNK:
                self.trunk.collect(item)
                report.trunk_items += 1
            else:
                report.assignments.append(self.couriers.dispatch(item, reason))
                report.courier_items += 1
        report.batches = self.trunk.flush()
        return report

    def summary(self, report: RoutingReport) -> str:
        lines = [
            f"Dispatch: {report.trunk_items} trunk (in {len(report.batches)} batch(es)), "
            f"{report.courier_items} courier",
        ]
        for batch in report.batches:
            lines.append(
                f"  tube {batch.from_hub} -> {batch.to_hub}: {len(batch.item_ids)} item(s) "
                f"({', '.join(batch.item_ids)})"
            )
        for assignment in report.assignments:
            lines.append(
                f"  courier {assignment.from_hub} -> {assignment.to_hub}: "
                f"{assignment.item_id} ({assignment.reason})"
            )
        return "\n".join(lines)
