"""Cross-device sync for browser data: dials, notes, bookmarks.

Studied from: desktop-casualties-20260916 (Opera section of report.md).
Opera Link synced speed dials, notes, and bookmarks across browsers
before browser sync was ordinary. The shape is a two-way merge between
a local store and a remote store, both holding the same collections,
with tombstones so deletions replicate and last-writer-wins so
conflicts resolve deterministically.

This module implements that merge without any network I/O: a SyncStore
holds versioned items per collection, and ``sync_pair`` merges a local
and a remote store in both directions. Items carry logical timestamps
(set by the caller); the higher timestamp wins a conflict, ties break
by device id. The merge is idempotent — syncing an already-synced pair
changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

__all__ = [
    "SyncItem",
    "SyncStore",
    "SyncReport",
    "sync_pair",
]

ORIGIN = "levi-revival/opera-link"


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


@dataclass
class SyncItem:
    """One synced datum: a dial, note, or bookmark."""

    id: str
    collection: str  # e.g. "bookmarks", "notes", "dials"
    payload: dict[str, Any]
    updated: int  # logical timestamp of the last edit
    device_id: str  # last editor
    deleted: bool = False  # tombstone: the item was removed


def _wins(challenger: SyncItem, incumbent: SyncItem) -> bool:
    """Last-writer-wins; ties break by device id order for determinism."""
    return (challenger.updated, challenger.device_id) > (
        incumbent.updated,
        incumbent.device_id,
    )


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class SyncStore:
    """One side of the sync: local browser or remote server."""

    def __init__(self, device_id: str) -> None:
        if not device_id:
            raise ValueError("device_id must be non-empty")
        self.device_id = device_id
        self._items: dict[tuple[str, str], SyncItem] = {}  # (collection, id) -> item

    def upsert(
        self, collection: str, item_id: str, payload: dict[str, Any], updated: int
    ) -> SyncItem:
        item = SyncItem(
            id=item_id,
            collection=collection,
            payload=dict(payload),
            updated=updated,
            device_id=self.device_id,
        )
        self._items[(collection, item_id)] = item
        return item

    def remove(self, collection: str, item_id: str, updated: int) -> None:
        """Delete as a tombstone so the deletion replicates."""
        self._items[(collection, item_id)] = SyncItem(
            id=item_id,
            collection=collection,
            payload={},
            updated=updated,
            device_id=self.device_id,
            deleted=True,
        )

    def get(self, collection: str, item_id: str) -> Optional[SyncItem]:
        return self._items.get((collection, item_id))

    def live(self, collection: Optional[str] = None) -> list[SyncItem]:
        """Non-deleted items, optionally filtered to one collection."""
        return [
            item
            for (coll, _), item in self._items.items()
            if not item.deleted and (collection is None or coll == collection)
        ]

    def all_items(self) -> Iterable[SyncItem]:
        return list(self._items.values())

    def _apply(self, item: SyncItem) -> bool:
        """Merge one incoming item; True if it changed this store."""
        key = (item.collection, item.id)
        incumbent = self._items.get(key)
        if incumbent is None or _wins(item, incumbent):
            self._items[key] = item
            return True
        return False


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


@dataclass
class SyncReport:
    """What one two-way sync did."""

    to_remote: int  # items local pushed to remote
    to_local: int  # items remote pulled into local
    conflicts_resolved: int  # keys where both sides had a different version
    unchanged: int


def sync_pair(local: SyncStore, remote: SyncStore) -> SyncReport:
    """Two-way merge between a local and a remote store.

    Every item flows to the side that lacks it or holds an older version;
    deletions replicate via tombstones. Conflicts (both sides holding a
    different version of the same key) resolve last-writer-wins. After the
    merge both stores hold identical per-key winners, so repeating the
    sync is a no-op.
    """
    to_remote = 0
    to_local = 0
    conflicts = 0
    unchanged = 0

    for item in local.all_items():
        incumbent = remote.get(item.collection, item.id)
        if incumbent is None:
            remote._apply(item)
            to_remote += 1
        elif incumbent.updated != item.updated or incumbent.deleted != item.deleted:
            conflicts += 1
            if remote._apply(item):
                to_remote += 1
            else:
                unchanged += 1
        else:
            unchanged += 1

    for item in remote.all_items():
        local_item = local.get(item.collection, item.id)
        # Items that just flowed remote-ward, or conflicts already counted,
        # need only the local-ward pass for genuinely new/older content.
        if local_item is None:
            local._apply(item)
            to_local += 1
        elif (local_item.updated, local_item.deleted) != (item.updated, item.deleted):
            if local._apply(item):
                to_local += 1
            else:
                unchanged += 1
        else:
            unchanged += 1

    return SyncReport(
        to_remote=to_remote,
        to_local=to_local,
        conflicts_resolved=conflicts,
        unchanged=unchanged,
    )
