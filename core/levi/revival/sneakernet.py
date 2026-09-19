"""Drivethread — physical media rotation for offsite copies without a cloud tier.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md [§6]
(the sneakernet: a rotating set of removable drives where one copy always
lives offsite, carried by hand instead of pushed over the network).

This is an original, from-scratch implementation for LEVI. A
``RotationPool`` manages a set of labeled drives moving through a rotation:
``onsite`` (plugged in, taking fresh copies) → ``transit`` (being carried) →
``offsite`` (stored away from the machine). Exactly one drive is onsite at a
time; ``rotate()`` advances the hand: the onsite drive goes to transit, the
transit drive lands offsite, the oldest offsite drive comes home. Every copy
is written with a content manifest (relative path → sha256), so ``verify()``
can prove a drive still matches what was written to it.

The mechanism tracks the *age* of the offsite copy and the risk window it
implies: the older the offsite drive, the more data loss a disaster would
cost. ``status()`` reports the rotation state; ``overdue(threshold_days)``
flags drives whose offsite copy is stale. Drives that fail verification are
quarantined, never rotated back into service.

Public surface:
- ``Drive`` / ``DriveState``: one physical drive and its slot in the rotation.
- ``RotationPool``: ``add_drive``, ``write_copy``, ``verify``, ``rotate``,
  ``overdue``, ``quarantine``, ``status``.
- ``RotationError`` for embedding.

stdlib-only. No network. Deterministic (callers supply the clock).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

ORIGIN = "levi-revival/sneakernet"


class RotationError(ValueError):
    """Raised when a rotation operation cannot be honored."""


class DriveState(str, Enum):
    ONSITE = "onsite"
    TRANSIT = "transit"
    OFFSITE = "offsite"
    QUARANTINED = "quarantined"


def _manifest_hash(files: Dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8") + b"\x00")
        digest.update(hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


@dataclass
class Drive:
    """One physical drive in the rotation."""

    drive_id: str
    capacity_bytes: int
    state: DriveState = DriveState.OFFSITE
    manifest: Dict[str, str] = field(default_factory=dict)
    written_at: Optional[datetime] = None
    rotation_count: int = 0
    verify_failures: int = 0

    @property
    def manifest_size(self) -> int:
        return len(self.manifest)

    def offsite_age_days(self, now: datetime) -> Optional[float]:
        """Days since this drive was written while it sits offsite."""
        if self.state is not DriveState.OFFSITE or self.written_at is None:
            return None
        return (now - self.written_at).total_seconds() / 86400.0


@dataclass
class RotationPool:
    """The set of drives and the hand-off discipline between them."""

    drives: Dict[str, Drive] = field(default_factory=dict)

    # -- inventory -----------------------------------------------------
    def add_drive(self, drive_id: str, capacity_bytes: int) -> Drive:
        if not drive_id:
            raise RotationError("drive_id must be non-empty")
        if capacity_bytes <= 0:
            raise RotationError("capacity_bytes must be positive")
        if drive_id in self.drives:
            raise RotationError(f"drive {drive_id!r} already in pool")
        drive = Drive(drive_id=drive_id, capacity_bytes=capacity_bytes)
        self.drives[drive_id] = drive
        return drive

    def _onsite_drive(self) -> Drive:
        onsite = [d for d in self.drives.values() if d.state is DriveState.ONSITE]
        if len(onsite) > 1:
            raise RotationError("rotation corrupted: more than one onsite drive")
        if not onsite:
            raise RotationError("no drive is onsite; dock one first")
        return onsite[0]

    def dock(self, drive_id: str) -> None:
        """Bring an offsite drive home and plug it in as the onsite drive."""
        drive = self._get(drive_id)
        if drive.state is DriveState.QUARANTINED:
            raise RotationError(f"drive {drive_id!r} is quarantined")
        if any(d.state is DriveState.ONSITE for d in self.drives.values()):
            raise RotationError("an onsite drive is already docked")
        drive.state = DriveState.ONSITE

    def _get(self, drive_id: str) -> Drive:
        try:
            return self.drives[drive_id]
        except KeyError:
            raise RotationError(f"unknown drive {drive_id!r}") from None

    # -- copies --------------------------------------------------------
    def write_copy(
        self, drive_id: str, files: Dict[str, bytes], now: datetime
    ) -> Dict[str, str]:
        """Write a full copy to the onsite drive and record its manifest."""
        drive = self._get(drive_id)
        if drive.state is not DriveState.ONSITE:
            raise RotationError(f"drive {drive_id!r} is not onsite")
        total = sum(len(b) for b in files.values())
        if total > drive.capacity_bytes:
            raise RotationError(
                f"copy ({total} bytes) exceeds drive capacity ({drive.capacity_bytes})"
            )
        manifest = {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()
        }
        drive.manifest = manifest
        drive.written_at = now
        drive.verify_failures = 0
        return dict(manifest)

    def verify(self, drive_id: str, files: Dict[str, bytes]) -> bool:
        """Check a drive's live contents against its recorded manifest."""
        drive = self._get(drive_id)
        if not drive.manifest:
            raise RotationError(f"drive {drive_id!r} has no recorded copy to verify")
        expected = {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()
        }
        ok = expected == drive.manifest
        if not ok:
            drive.verify_failures += 1
        return ok

    def quarantine(self, drive_id: str) -> None:
        """Pull a suspect drive out of the rotation permanently."""
        drive = self._get(drive_id)
        drive.state = DriveState.QUARANTINED

    # -- rotation ------------------------------------------------------
    def rotate(self, now: datetime) -> Dict[str, str]:
        """Advance the hand: onsite→transit, transit→offsite, oldest offsite→docked.

        The onsite drive can only rotate after a copy was written to it; the
        drive that comes home becomes the new onsite drive. Returns a mapping
        of drive_id → new state describing what moved.
        """
        onsite = self._onsite_drive()
        if not onsite.manifest:
            raise RotationError(
                f"drive {onsite.drive_id!r} has no fresh copy; write_copy first"
            )
        transit = [d for d in self.drives.values() if d.state is DriveState.TRANSIT]
        if len(transit) > 1:
            raise RotationError("rotation corrupted: more than one drive in transit")
        moved: Dict[str, str] = {}

        # The drive arriving offsite is the one previously in transit.
        # Onsite drive leaves for transit.
        onsite.state = DriveState.TRANSIT
        onsite.rotation_count += 1
        moved[onsite.drive_id] = DriveState.TRANSIT.value

        for d in transit:
            d.state = DriveState.OFFSITE
            d.written_at = d.written_at or now
            moved[d.drive_id] = DriveState.OFFSITE.value

        # Oldest verified offsite drive comes home and docks.
        candidates = [
            d
            for d in self.drives.values()
            if d.state is DriveState.OFFSITE
            and d.verify_failures == 0
            and d.drive_id not in moved
        ]
        if candidates:
            home = min(
                candidates,
                key=lambda d: d.written_at or datetime.min.replace(tzinfo=timezone.utc),
            )
            home.state = DriveState.ONSITE
            moved[home.drive_id] = DriveState.ONSITE.value
        return moved

    # -- reporting -----------------------------------------------------
    def overdue(self, now: datetime, threshold_days: float) -> List[str]:
        """Drive ids whose offsite copy is older than the threshold."""
        late = []
        for d in self.drives.values():
            age = d.offsite_age_days(now)
            if age is not None and age > threshold_days:
                late.append(d.drive_id)
        return sorted(late)

    def offsite_freshness(self, now: datetime) -> Optional[float]:
        """Age in days of the freshest offsite copy (None if there is none)."""
        ages = [
            d.offsite_age_days(now)
            for d in self.drives.values()
            if d.offsite_age_days(now) is not None
        ]
        return min(ages) if ages else None

    def status(self, now: datetime) -> Dict[str, object]:
        by_state: Dict[str, List[str]] = {s.value: [] for s in DriveState}
        for d in self.drives.values():
            by_state[d.state.value].append(d.drive_id)
        return {
            "drives": len(self.drives),
            "by_state": by_state,
            "offsite_freshest_days": self.offsite_freshness(now),
            "quarantined": by_state[DriveState.QUARANTINED.value],
        }
