"""Per-project memory vaults — scoped local memory with explicit retention rules.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 14].

The mechanism under study: memory kept in separate per-project vaults,
each with explicit retention rules (time-to-live, max entries, pinned
tags that are never purged), stored locally. This is an original,
from-scratch implementation for LEVI: a small policy engine over a local
JSON-backed store. Retention is enforced by an explicit ``purge()``
call — nothing expires silently or in the background. Pinning is
absolute: pinned entries survive every purge.

Public surface:
- ``RetentionPolicy``: ttl_seconds, max_entries, pin_tags, on_overflow.
- ``MemoryVault``: put/get/delete entries inside one vault.
- ``VaultStore``: create/get/delete/list vaults; save(path)/load(path);
  ``purge_all(now)`` enforcing every vault's policy.

stdlib-only. No network. All timestamps are caller-supplied floats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/memory-vaults"


class VaultError(ValueError):
    """Raised when a vault operation is invalid."""


@dataclass
class Entry:
    entry_id: str
    key: str
    value: str
    created_at: float
    tags: List[str] = field(default_factory=list)


@dataclass
class RetentionPolicy:
    """Explicit retention rules for a vault.

    ttl_seconds: entries older than this are purged (None = keep forever).
    max_entries: newest N entries kept (None = unlimited).
    pin_tags: entries carrying any of these tags are never purged.
    on_overflow: "drop-oldest" (purge oldest non-pinned) or "refuse"
        (reject new puts when full).
    """

    ttl_seconds: Optional[float] = None
    max_entries: Optional[int] = None
    pin_tags: List[str] = field(default_factory=list)
    on_overflow: str = "drop-oldest"

    def __post_init__(self) -> None:
        if self.on_overflow not in ("drop-oldest", "refuse"):
            raise VaultError(f"unknown on_overflow mode: {self.on_overflow!r}")
        if self.max_entries is not None and self.max_entries < 1:
            raise VaultError("max_entries must be >= 1")


def _pinned(entry: Entry, policy: RetentionPolicy) -> bool:
    return any(t in policy.pin_tags for t in entry.tags)


class MemoryVault:
    """One scoped vault: a key-addressable store with a retention policy."""

    def __init__(self, name: str, policy: RetentionPolicy) -> None:
        self.name = name
        self.policy = policy
        self._entries: Dict[str, Entry] = {}
        self._seq = 0

    def put(
        self, key: str, value: str, created_at: float, tags: Optional[List[str]] = None
    ) -> Entry:
        if not key:
            raise VaultError("key must not be empty")
        self._seq += 1
        entry = Entry(
            f"{self.name}:{self._seq}", key, value, created_at, list(tags or [])
        )
        if self.policy.max_entries is not None:
            self._make_room()
        self._entries[key] = entry
        return entry

    def _make_room(self) -> None:
        """Free capacity before a put. Honest about refuse vs drop-oldest."""
        limit = self.policy.max_entries
        while len(self._entries) >= limit:
            if self.policy.on_overflow == "refuse":
                raise VaultError(f"vault {self.name!r} is full (refusing new entry)")
            evictable = [
                e
                for e in sorted(self._entries.values(), key=lambda e: e.created_at)
                if not _pinned(e, self.policy)
            ]
            if not evictable:
                raise VaultError(
                    f"vault {self.name!r} is full and all entries are pinned"
                )
            del self._entries[evictable[0].key]

    def get(self, key: str) -> Optional[Entry]:
        return self._entries.get(key)

    def delete(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    def list_keys(self) -> List[str]:
        return sorted(self._entries)

    def purge(self, now: float) -> int:
        """Enforce the retention policy. Returns number of entries removed."""
        removed = 0
        if self.policy.ttl_seconds is not None:
            cutoff = now - self.policy.ttl_seconds
            stale = [
                k
                for k, e in self._entries.items()
                if e.created_at < cutoff and not _pinned(e, self.policy)
            ]
            for k in stale:
                del self._entries[k]
                removed += 1
        if self.policy.max_entries is not None:
            while len(self._entries) > self.policy.max_entries:
                evictable = [
                    e
                    for e in sorted(self._entries.values(), key=lambda e: e.created_at)
                    if not _pinned(e, self.policy)
                ]
                if not evictable:
                    break
                del self._entries[evictable[0].key]
                removed += 1
        return removed

    def stats(self) -> Dict[str, int]:
        pinned = sum(1 for e in self._entries.values() if _pinned(e, self.policy))
        return {"entries": len(self._entries), "pinned": pinned}

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "policy": {
                "ttl_seconds": self.policy.ttl_seconds,
                "max_entries": self.policy.max_entries,
                "pin_tags": self.policy.pin_tags,
                "on_overflow": self.policy.on_overflow,
            },
            "entries": [vars(e) for e in self._entries.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryVault":
        p = data["policy"]
        vault = cls(
            data["name"],
            RetentionPolicy(
                ttl_seconds=p["ttl_seconds"],
                max_entries=p["max_entries"],
                pin_tags=p["pin_tags"],
                on_overflow=p["on_overflow"],
            ),
        )
        for e in data["entries"]:
            vault._entries[e["key"]] = Entry(**e)
            seq = int(e["entry_id"].split(":")[-1])
            vault._seq = max(vault._seq, seq)
        return vault


class VaultStore:
    """Owns many named vaults; persists the whole store to one JSON file."""

    def __init__(self) -> None:
        self._vaults: Dict[str, MemoryVault] = {}

    def create_vault(
        self, name: str, policy: Optional[RetentionPolicy] = None
    ) -> MemoryVault:
        if not name:
            raise VaultError("vault name must not be empty")
        if name in self._vaults:
            raise VaultError(f"vault {name!r} already exists")
        vault = MemoryVault(name, policy or RetentionPolicy())
        self._vaults[name] = vault
        return vault

    def get_vault(self, name: str) -> MemoryVault:
        try:
            return self._vaults[name]
        except KeyError:
            raise VaultError(f"no vault named {name!r}") from None

    def delete_vault(self, name: str) -> bool:
        return self._vaults.pop(name, None) is not None

    def list_vaults(self) -> List[str]:
        return sorted(self._vaults)

    def purge_all(self, now: float) -> Dict[str, int]:
        return {name: v.purge(now) for name, v in self._vaults.items()}

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({n: v.to_dict() for n, v in self._vaults.items()}, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "VaultStore":
        store = cls()
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for name, vdata in data.items():
            store._vaults[name] = MemoryVault.from_dict(vdata)
        return store
