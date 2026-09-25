"""The night-shift tollbooth: batch all outbound traffic into cheap windows.

Studied from: protocols-hunt-20260916-0041/report.md (Find 1 - FidoNet)

The load-bearing mechanism: when bandwidth costs real money (or energy,
or radio spectrum), you don't send immediately — you queue outbound
traffic all day and flush it during a scheduled *poll window* when rates
are cheapest. The window decides *when* things move; everything else
decides *what* moves.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is rate-aware deferred delivery with
per-route windows and catch-up on missed windows. Not revived: actual
telephone dialing or modem negotiation — the window is a schedule,
not a wire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from pathlib import Path


ORIGIN = "levi-revival/poll-window"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PollWindowError(Exception):
    """Base class for poll-window failures."""


# ---------------------------------------------------------------------------
# Rate schedule
# ---------------------------------------------------------------------------


class WindowKind(str, Enum):
    """Traffic priority for window planning: cheaper windows get bulk."""

    URGENT = "urgent"  # may leave in any window, even an expensive one
    NORMAL = "normal"  # waits for a standard window
    BULK = "bulk"  # waits for the cheapest window only


@dataclass
class PollWindow:
    """One daily window of time during which queued traffic may move.

    Windows are clock-times on a 24h clock; a window that crosses
    midnight (start > end) is supported.
    """

    name: str
    start: time
    end: time
    rate_class: str = "standard"  # free-form label, e.g. "cheap" / "peak"

    def contains(self, moment: datetime) -> bool:
        t = moment.time()
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end  # crosses midnight

    def next_open(self, moment: datetime) -> datetime:
        """Next datetime >= moment at which this window opens."""
        if self.contains(moment):
            return moment  # already open
        candidate = moment.replace(
            hour=self.start.hour,
            minute=self.start.minute,
            second=0,
            microsecond=0,
        )
        if candidate < moment:
            candidate += timedelta(days=1)
        return candidate


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


@dataclass
class QueuedItem:
    """One outbound payload waiting for a window."""

    item_id: str
    payload: str
    kind: WindowKind = WindowKind.NORMAL
    destination: str = ""
    queued_at: str = field(default_factory=lambda: datetime.now().isoformat())
    attempts: int = 0
    delivered: bool = False


@dataclass
class DeliveryRecord:
    """A receipt for an item released during a window."""

    item_id: str
    window: str
    released_at: str


class PollWindowQueue:
    """Queue outbound traffic and release it only inside scheduled windows.

    BULK waits for cheap windows, NORMAL goes in standard windows,
    URGENT leaves in any open window. Closed windows release nothing;
    missed windows are simply re-evaluated at the next tick — items never
    leave outside a window (honest deferred delivery).
    """

    def __init__(self, windows: list[PollWindow]) -> None:
        if not windows:
            raise PollWindowError("at least one poll window is required")
        self.windows = list(windows)
        self.items: dict[str, QueuedItem] = {}
        self.delivered_log: list[DeliveryRecord] = []

    # -- enqueue --------------------------------------------------------

    def queue(self, item: QueuedItem) -> None:
        if item.item_id in self.items:
            raise PollWindowError(f"duplicate item id: {item.item_id}")
        self.items[item.item_id] = item

    # -- scheduling -------------------------------------------------------

    def open_windows(self, moment: datetime) -> list[PollWindow]:
        return [w for w in self.windows if w.contains(moment)]

    def next_window(self, moment: datetime) -> PollWindow:
        return min(self.windows, key=lambda w: w.next_open(moment))

    def _release_kind(self, kind: WindowKind, windows: list[PollWindow]) -> bool:
        if kind == WindowKind.URGENT:
            return bool(windows)
        if kind == WindowKind.NORMAL:
            return bool(windows)  # any window will do
        return any(w.rate_class == "cheap" for w in windows)

    # -- tick --------------------------------------------------------------

    def tick(self, moment: datetime) -> list[DeliveryRecord]:
        """Release everything eligible now; return new delivery records."""
        open_now = self.open_windows(moment)
        if not open_now:
            return []
        window = min(open_now, key=lambda w: (w.rate_class != "cheap", w.name))
        released: list[DeliveryRecord] = []
        for item in sorted(self.items.values(), key=lambda i: i.queued_at):
            if item.delivered:
                continue
            if self._release_kind(item.kind, open_now):
                item.delivered = True
                item.attempts += 1
                record = DeliveryRecord(
                    item_id=item.item_id,
                    window=window.name,
                    released_at=moment.isoformat(),
                )
                self.delivered_log.append(record)
                released.append(record)
        return released

    def pending(self) -> list[QueuedItem]:
        return [i for i in self.items.values() if not i.delivered]

    # -- persistence ---------------------------------------------------------

    def save(self, path: str | Path) -> None:
        data = {
            "windows": [
                {
                    "name": w.name,
                    "start": w.start.isoformat(),
                    "end": w.end.isoformat(),
                    "rate_class": w.rate_class,
                }
                for w in self.windows
            ],
            "items": [
                {
                    "item_id": i.item_id,
                    "payload": i.payload,
                    "kind": i.kind.value,
                    "destination": i.destination,
                    "queued_at": i.queued_at,
                    "attempts": i.attempts,
                    "delivered": i.delivered,
                }
                for i in self.items.values()
            ],
            "delivered_log": [
                {"item_id": r.item_id, "window": r.window, "released_at": r.released_at}
                for r in self.delivered_log
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "PollWindowQueue":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        windows = [
            PollWindow(
                name=w["name"],
                start=time.fromisoformat(w["start"]),
                end=time.fromisoformat(w["end"]),
                rate_class=w.get("rate_class", "standard"),
            )
            for w in data["windows"]
        ]
        queue = cls(windows)
        for raw in data["items"]:
            item = QueuedItem(
                item_id=raw["item_id"],
                payload=raw["payload"],
                kind=WindowKind(raw["kind"]),
                destination=raw["destination"],
                queued_at=raw["queued_at"],
                attempts=raw["attempts"],
                delivered=raw["delivered"],
            )
            queue.items[item.item_id] = item
        for raw in data.get("delivered_log", []):
            queue.delivered_log.append(DeliveryRecord(**raw))
        return queue
