"""Dedupvault — deduplicating, content-addressed backup with snapshot history.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§7 — named alternative] (restic: deduplicating, encrypted,
backend-agnostic backup with the same cheap-bytes economics as a crypt
remote).

This is an original, from-scratch implementation for LEVI of the *shape*
studied: content-defined chunking, a content-addressed chunk store,
parent-linked snapshots, and a retention policy. It is a faithful working
model, not a port:

- Chunking uses a Rabin rolling fingerprint (implemented here in pure
  Python) with min/avg/max size bounds — variable-size, content-defined
  cut points, so a one-byte insertion shifts only local chunks.
- The chunk store is content-addressed: identical chunks collapse to one
  entry (real dedup), keyed by sha256.
- Snapshots are immutable records pointing at ordered chunk lists, linked
  to a parent; ``restore()`` reassembles bytes exactly.
- Retention (``prune``) applies keep-last / keep-daily / keep-weekly /
  keep-monthly rules, then garbage-collects chunks no snapshot references.
- ``stats()`` reports the honest dedup ratio: logical bytes vs stored bytes.

Encryption is NOT implemented here (the studied tool encrypts at rest;
this module stores plaintext chunks in memory and says so). The default
store is in-memory; nothing touches the disk unless the caller passes a
directory explicitly.

Public surface:
- ``DedupVault``: ``snapshot``, ``restore``, ``list_snapshots``,
  ``verify``, ``prune``, ``stats``, ``forget``.
- ``Snapshot``, ``RetentionPolicy``, ``VaultError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/restic"


class VaultError(ValueError):
    """Raised when a vault operation cannot be honored."""


# -- Rabin rolling fingerprint (pure-python, content-defined chunking) -----

_RABIN_POLY = 0x3DA3358B4DC173  # irreducible-ish 53-bit polynomial
_RABIN_WINDOW = 48


def _rabin_table() -> List[int]:
    table = []
    for i in range(256):
        h = i
        for _ in range(8):
            h = (h >> 1) ^ (_RABIN_POLY if h & 1 else 0)
        table.append(h)
    return table


_RABIN_TBL = _rabin_table()


def chunk_data(
    data: bytes,
    avg_size: int = 4096,
    min_size: int = 2048,
    max_size: int = 16384,
) -> List[bytes]:
    """Split bytes at content-defined boundaries via a Rabin fingerprint.

    A cut is taken when the low ``log2(avg_size)`` bits of the rolling hash
    are zero (and ``min_size`` has passed); ``max_size`` forces a cut. This
    is a heuristic chunker — good enough for dedup modeling, not tuned for
    any production workload.
    """
    if avg_size < min_size or max_size < avg_size:
        raise VaultError("need min_size <= avg_size <= max_size")
    if not data:
        return []
    mask = avg_size - 1  # avg_size should be a power of two
    chunks: List[bytes] = []
    start = 0
    fp = 0
    for i, byte in enumerate(data):
        fp = ((fp << 8) ^ _RABIN_TBL[byte & 0xFF]) & 0xFFFFFFFFFFFFFFFF
        size = i - start + 1
        if size >= min_size and (fp & mask == 0 or size >= max_size):
            chunks.append(data[start : i + 1])
            start = i + 1
            fp = 0
    if start < len(data):
        chunks.append(data[start:])
    return chunks


@dataclass(frozen=True)
class Snapshot:
    """One immutable backup: name, time, parent, and chunk references."""

    snap_id: str
    name: str
    taken_at: datetime
    parent_id: Optional[str]
    chunks: Tuple[str, ...]  # content hashes in order
    logical_bytes: int


@dataclass(frozen=True)
class RetentionPolicy:
    """Which snapshots ``prune`` keeps."""

    keep_last: int = 0
    keep_daily: int = 0
    keep_weekly: int = 0
    keep_monthly: int = 0

    def __post_init__(self) -> None:
        for f in ("keep_last", "keep_daily", "keep_weekly", "keep_monthly"):
            if getattr(self, f) < 0:
                raise VaultError(f"{f} cannot be negative")


class DedupVault:
    """In-memory deduplicating backup vault."""

    def __init__(self) -> None:
        self._chunks: Dict[str, bytes] = {}
        self._snapshots: Dict[str, Snapshot] = {}
        self._order: List[str] = []  # snapshot ids, oldest first

    # -- core ----------------------------------------------------------
    def snapshot(
        self,
        name: str,
        files: Dict[str, bytes],
        taken_at: Optional[datetime] = None,
        parent_id: Optional[str] = None,
    ) -> Snapshot:
        """Store a snapshot: chunk each file, dedup into the store."""
        if not name:
            raise VaultError("snapshot name must be non-empty")
        if parent_id is not None and parent_id not in self._snapshots:
            raise VaultError(f"unknown parent snapshot {parent_id!r}")
        taken_at = taken_at or datetime.now(timezone.utc)
        chunk_refs: List[str] = []
        logical = 0
        # A per-file header chunk keeps file boundaries restorable.
        for fname in sorted(files):
            header = f"FILE:{fname}:{len(files[fname])}\n".encode("utf-8")
            chunk_refs.extend(self._store_chunks([header]))
            chunk_refs.extend(self._store_chunks(chunk_data(files[fname])))
            logical += len(files[fname])
        snap_id = hashlib.sha256(
            (name + taken_at.isoformat() + str(chunk_refs)).encode("utf-8")
        ).hexdigest()[:16]
        snap = Snapshot(
            snap_id=snap_id,
            name=name,
            taken_at=taken_at,
            parent_id=parent_id,
            chunks=tuple(chunk_refs),
            logical_bytes=logical,
        )
        self._snapshots[snap_id] = snap
        self._order.append(snap_id)
        return snap

    def _store_chunks(self, chunks: List[bytes]) -> List[str]:
        refs = []
        for c in chunks:
            digest = hashlib.sha256(c).hexdigest()
            if digest not in self._chunks:
                self._chunks[digest] = c
            refs.append(digest)
        return refs

    def restore(self, snap_id: str) -> Dict[str, bytes]:
        """Reassemble a snapshot's files exactly."""
        snap = self._get(snap_id)
        files: Dict[str, bytes] = {}
        current_name: Optional[str] = None
        current_expect: Optional[int] = None
        current_data = bytearray()
        for ref in snap.chunks:
            raw = self._chunks[ref]
            if raw.startswith(b"FILE:"):
                if current_name is not None:
                    if len(current_data) != current_expect:
                        raise VaultError(f"snapshot {snap_id!r} is corrupt")
                    files[current_name] = bytes(current_data)
                parts = raw.decode("utf-8").rstrip("\n").split(":")
                current_name = ":".join(parts[1:-1])
                current_expect = int(parts[-1])
                current_data = bytearray()
            else:
                current_data.extend(raw)
        if current_name is not None:
            if len(current_data) != current_expect:
                raise VaultError(f"snapshot {snap_id!r} is corrupt")
            files[current_name] = bytes(current_data)
        return files

    def verify(self, snap_id: str) -> bool:
        """True when every chunk a snapshot references is present."""
        snap = self._get(snap_id)
        return all(ref in self._chunks for ref in snap.chunks)

    def list_snapshots(self) -> List[Snapshot]:
        return [self._snapshots[sid] for sid in self._order]

    # -- retention -----------------------------------------------------
    def prune(self, policy: RetentionPolicy) -> List[str]:
        """Apply retention, drop unreferenced chunks, return removed snap ids."""
        keep: set = set()
        snaps = self.list_snapshots()
        if policy.keep_last:
            keep.update(s.snap_id for s in snaps[-policy.keep_last :])
        buckets: Dict[Tuple[str, str], Snapshot] = {}
        for snap in snaps:
            if policy.keep_daily:
                key = ("d", snap.taken_at.strftime("%Y-%m-%d"))
                if key not in buckets or snap.taken_at > buckets[key].taken_at:
                    buckets[key] = snap
            if policy.keep_weekly:
                key = ("w", snap.taken_at.strftime("%Y-%W"))
                if key not in buckets or snap.taken_at > buckets[key].taken_at:
                    buckets[key] = snap
            if policy.keep_monthly:
                key = ("m", snap.taken_at.strftime("%Y-%m"))
                if key not in buckets or snap.taken_at > buckets[key].taken_at:
                    buckets[key] = snap
        # Trim each bucket class to its keep count (newest first).
        for kind, limit in (
            ("d", policy.keep_daily),
            ("w", policy.keep_weekly),
            ("m", policy.keep_monthly),
        ):
            if not limit:
                continue
            members = sorted(
                (s for k, s in buckets.items() if k[0] == kind),
                key=lambda s: s.taken_at,
                reverse=True,
            )
            keep.update(s.snap_id for s in members[:limit])
        removed = [s.snap_id for s in snaps if s.snap_id not in keep]
        for sid in removed:
            del self._snapshots[sid]
            self._order.remove(sid)
        self._gc_chunks()
        return removed

    def _gc_chunks(self) -> int:
        referenced = set()
        for snap in self._snapshots.values():
            referenced.update(snap.chunks)
        orphaned = [h for h in self._chunks if h not in referenced]
        for h in orphaned:
            del self._chunks[h]
        return len(orphaned)

    def forget(self, snap_id: str) -> None:
        """Delete one snapshot and garbage-collect its orphaned chunks."""
        self._get(snap_id)
        del self._snapshots[snap_id]
        self._order.remove(snap_id)
        self._gc_chunks()

    # -- insight -------------------------------------------------------
    def stats(self) -> Dict[str, float]:
        logical = sum(s.logical_bytes for s in self._snapshots.values())
        stored = sum(len(c) for c in self._chunks.values())
        return {
            "snapshots": float(len(self._snapshots)),
            "chunks": float(len(self._chunks)),
            "logical_bytes": float(logical),
            "stored_bytes": float(stored),
            "dedup_ratio": (logical / stored) if stored else 0.0,
        }

    def _get(self, snap_id: str) -> Snapshot:
        try:
            return self._snapshots[snap_id]
        except KeyError:
            raise VaultError(f"unknown snapshot {snap_id!r}") from None
