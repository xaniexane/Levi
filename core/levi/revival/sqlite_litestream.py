"""sqlite_litestream — continuous write-ahead-log replication, planned locally.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 2,
embedded database with continuous WAL-to-remote replication replacing
managed-database subscriptions).

Functional pattern studied: the database is just a file; every write lands
in an append-only write-ahead log, and a replicator continuously ships new
log frames to cheap object storage, tracking a persistent cursor. Recovery
is snapshot + replay of frames after the cursor.

What this module is: the *mechanism* without the network. An in-memory
append-only ``Wal`` of frames, a ``Replicator`` that advances a durable
cursor and returns exactly the unshipped frames (so any transport — rsync,
rclone, object upload — can carry them), checkpointing, gap detection, and
restore-by-replay. It models idempotency, resume, and corruption signaling;
it does not perform uploads.

Honest limits: frames are opaque payloads here, not real SQLite pages; the
transport is the operator's job. ``verify()`` detects gaps and checksum
mismatches in what was shipped and demands a full resync — that signaling
is the core of the design.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional

ORIGIN = "levi-revival/sqlite-litestream"


@dataclass
class Frame:
    """One write-ahead-log frame: an opaque payload with an id and checksum."""

    frame_id: int
    payload: bytes
    created_at: float = field(default_factory=time.time)
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._digest()

    def _digest(self) -> str:
        h = hashlib.sha256()
        h.update(self.frame_id.to_bytes(8, "big"))
        h.update(self.payload)
        return h.hexdigest()

    def valid(self) -> bool:
        return self.checksum == self._digest()


class Wal:
    """Append-only write-ahead log."""

    def __init__(self) -> None:
        self._frames: List[Frame] = []
        self._next_id = 1

    def append(self, payload: bytes) -> Frame:
        frame = Frame(frame_id=self._next_id, payload=payload)
        self._frames.append(frame)
        self._next_id += 1
        return frame

    def frames_after(self, frame_id: int) -> List[Frame]:
        return [f for f in self._frames if f.frame_id > frame_id]

    def latest_id(self) -> int:
        return self._frames[-1].frame_id if self._frames else 0

    def __len__(self) -> int:
        return len(self._frames)


@dataclass
class ReplicationPlan:
    """Operator policy for the continuous replication loop."""

    interval_s: float = 1.0  # how often the loop wakes
    retention_frames: int = 100_000  # local frames kept after shipping
    object_prefix: str = "db/wal/"  # remote key namespace (transport-side)
    snapshot_every_frames: int = 10_000  # full snapshot cadence


@dataclass
class Checkpoint:
    """Durable cursor: everything at or below shipped_upto is replicated."""

    shipped_upto: int = 0
    last_snapshot_at: int = 0
    updated_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(
            {
                "shipped_upto": self.shipped_upto,
                "last_snapshot_at": self.last_snapshot_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "Checkpoint":
        data = json.loads(raw)
        return cls(
            shipped_upto=int(data.get("shipped_upto", 0)),
            last_snapshot_at=int(data.get("last_snapshot_at", 0)),
            updated_at=float(data.get("updated_at", time.time())),
        )


class GapError(Exception):
    """Raised when shipped frames are not contiguous — full resync required."""


class Replicator:
    """Cursor-driven replication over a WAL.

    ``poll()`` returns the newly-shipped batch (the frames the transport
    must carry) and advances the cursor. ``restore()`` replays a snapshot
    plus shipped frames onto a fresh WAL.
    """

    def __init__(
        self,
        wal: Wal,
        plan: Optional[ReplicationPlan] = None,
        checkpoint: Optional[Checkpoint] = None,
    ) -> None:
        self.wal = wal
        self.plan = plan or ReplicationPlan()
        self.checkpoint = checkpoint or Checkpoint()
        self.shipped_log: List[int] = []  # frame ids shipped, in order (audit)

    def pending(self) -> List[Frame]:
        return self.wal.frames_after(self.checkpoint.shipped_upto)

    def poll(self) -> List[Frame]:
        """Ship everything new since the cursor; advance the cursor.

        Idempotent across crashes: on restart the checkpoint is reloaded and
        only unshipped frames are returned again.
        """
        batch = self.pending()
        for frame in batch:
            if not frame.valid():
                raise GapError(f"frame {frame.frame_id} failed checksum")
        if batch:
            self.checkpoint.shipped_upto = batch[-1].frame_id
            self.checkpoint.updated_at = time.time()
            self.shipped_log.extend(f.frame_id for f in batch)
        return batch

    def snapshot_due(self) -> bool:
        return (
            self.checkpoint.shipped_upto - self.checkpoint.last_snapshot_at
        ) >= self.plan.snapshot_every_frames

    def mark_snapshot(self) -> None:
        self.checkpoint.last_snapshot_at = self.checkpoint.shipped_upto

    def verify_shipped(self, shipped: List[Frame]) -> None:
        """Check a shipped batch for contiguity and integrity.

        Raises GapError on any hole or corruption — the signal that a full
        resync is required.
        """
        if not shipped:
            return
        ids = [f.frame_id for f in shipped]
        if any(b - a != 1 for a, b in zip(ids, ids[1:], strict=False)):
            raise GapError(f"non-contiguous shipped batch: {ids}")
        for frame in shipped:
            if not frame.valid():
                raise GapError(f"shipped frame {frame.frame_id} corrupt")

    def restore(self, snapshot: List[bytes], frames: List[Frame]) -> Wal:
        """Rebuild a WAL: snapshot base (ordered payloads) + replay frames.

        Frames must be contiguous from the snapshot end; otherwise GapError.
        """
        wal = Wal()
        for payload in snapshot:
            wal.append(payload)
        base = wal.latest_id()
        for frame in frames:
            if frame.frame_id != base + 1:
                raise GapError(
                    f"expected frame {base + 1} after snapshot, got {frame.frame_id}"
                )
            if not frame.valid():
                raise GapError(f"frame {frame.frame_id} corrupt")
            wal.append(frame.payload)
            base += 1
        return wal

    def prune(self) -> int:
        """Drop shipped frames older than the retention window. Returns
        the number of frames removed."""
        cutoff = self.checkpoint.shipped_upto - self.plan.retention_frames
        before = len(self.wal)
        self.wal._frames = [f for f in self.wal._frames if f.frame_id > cutoff]
        return before - len(self.wal)
