"""Device as cache, server as truth: instant-restore sync.

Studied from: dead-networks-20260916 (Danger Hiptop / Sidekick section of report.md).
The Sidekick model treated the handset as a cache and the server as the
canonical truth: contacts, photos, and apps lived server-side, so a
replacement device could be restored instantly. The device's local copy
is authoritative for nothing — it is a replica that pushes deltas up and
can always be rebuilt from the server.

This module implements that discipline without any network I/O. A
TruthStore holds versioned records keyed by name; a DeviceCache tracks
its own dirty records; sync pushes deltas up, and a fresh device is
restored by full pull. Conflicts resolve last-writer-wins on (version,
device id). Deletions are tombstones so they replicate too. A logical
clock stands in for wall time; it is monotonic per caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "SyncError",
    "Record",
    "TruthStore",
    "DeviceCache",
]

ORIGIN = "levi-revival/danger-hiptop"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SyncError(Exception):
    """Base class for sync failures."""


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class Record:
    """One versioned record on either side of the sync."""

    key: str
    value: Any
    version: int  # logical clock of the writer
    device_id: str  # last writer
    deleted: bool = False  # tombstone when True


def _wins(challenger: Record, incumbent: Record) -> bool:
    """Last-writer-wins: higher version wins; ties break by device id order."""
    return (challenger.version, challenger.device_id) > (
        incumbent.version,
        incumbent.device_id,
    )


# ---------------------------------------------------------------------------
# Server side: the truth
# ---------------------------------------------------------------------------


class TruthStore:
    """Canonical store. Accepts pushed records, keeps the winner per key."""

    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self._clock = 0

    @property
    def clock(self) -> int:
        return self._clock

    def push(self, records: list[Record]) -> list[str]:
        """Accept records from a device; return the keys that changed the truth."""
        changed: list[str] = []
        for record in records:
            if not record.key:
                raise SyncError("record key must be non-empty")
            incumbent = self._records.get(record.key)
            if incumbent is None or _wins(record, incumbent):
                self._records[record.key] = record
                changed.append(record.key)
            self._clock = max(self._clock, record.version)
        return changed

    def pull(self, keys: Optional[list[str]] = None) -> list[Record]:
        """Return the canonical records (live ones only, no tombstones)."""
        items = (
            self._records.values()
            if keys is None
            else (self._records[k] for k in keys if k in self._records)
        )
        return [r for r in items if not r.deleted]

    def raw(self, key: str) -> Optional[Record]:
        """Inspect the canonical record for a key, tombstone included."""
        return self._records.get(key)

    def key_count(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Device side: the cache
# ---------------------------------------------------------------------------


class DeviceCache:
    """A handset: local replica that pushes deltas and rebuilds from truth."""

    def __init__(self, device_id: str, server: TruthStore) -> None:
        if not device_id:
            raise ValueError("device_id must be non-empty")
        self.device_id = device_id
        self.server = server
        self._local: dict[str, Record] = {}
        self._clock = 0

    def _tick(self) -> int:
        self._clock = max(self._clock, self.server.clock) + 1
        return self._clock

    def put(self, key: str, value: Any) -> None:
        """Stage a local change (contacts, photos, apps...). Marks it dirty."""
        self._local[key] = Record(
            key=key, value=value, version=self._tick(), device_id=self.device_id
        )

    def delete(self, key: str) -> None:
        """Stage a deletion as a tombstone so it replicates."""
        self._local[key] = Record(
            key=key,
            value=None,
            version=self._tick(),
            device_id=self.device_id,
            deleted=True,
        )

    def sync(self) -> list[str]:
        """Push dirty records to the server, then reconcile with the truth.

        Returns the keys the server accepted. After a sync the cache
        reflects the canonical state for the pushed keys.
        """
        dirty = [r for r in self._local.values()]
        accepted = self.server.push(dirty)
        for record in dirty:
            truth = self.server.raw(record.key)
            if truth is not None:
                self._local[record.key] = truth
        return accepted

    def restore(self) -> int:
        """Full pull from the server: become an exact replica of the truth.

        This is the replacement-handset path — local state is discarded.
        Returns the number of live records restored.
        """
        pulled = self.server.pull()
        self._local = {r.key: r for r in pulled}
        return len(pulled)

    def get(self, key: str) -> Any:
        record = self._local.get(key)
        if record is None or record.deleted:
            raise KeyError(key)
        return record.value

    def keys(self) -> list[str]:
        return sorted(k for k, r in self._local.items() if not r.deleted)
