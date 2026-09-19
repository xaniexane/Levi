"""owned_media — real downloads and local libraries, playable forever.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S8].

Load-bearing idea: you own what you can hold. Ingesting media means storing
the actual bytes locally with a checksum — a real download, not a license to
stream. Playback is just reading bytes back: there is deliberately no license
check, no expiry, no phone-home. ``verify()`` re-hashes every item so bit rot
is caught, and ``export()`` writes real files back out.

LEVI's take: ``Library`` ingests ``(name, bytes)`` pairs as ``MediaItem``
records with SHA-256 digests, plays them by returning the bytes, verifies
integrity on demand, and exports to real files. ``ownership_receipt()``
proves possession with hash and ingest date — and lists no expiry, because
there is none.

Honest limits: bytes live in memory until you ``save()``/``load()`` the
library to disk; very large libraries should use the JSON sidecar plus the
exported files rather than holding everything in RAM. The module cannot
defeat DRM on files you never truly received — it only guarantees that what
you ingested stays yours.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

ORIGIN = "levi-revival/owned-media"


@dataclass
class MediaItem:
    """One owned media file: the actual bytes, plus proof they are intact."""

    name: str
    data: bytes = field(repr=False)
    sha256: str = ""
    ingested: str = ""
    media_type: str = "application/octet-stream"
    size: int = 0

    def __post_init__(self) -> None:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.data).hexdigest()
        if not self.ingested:
            self.ingested = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not self.size:
            self.size = len(self.data)


class Library:
    """A local media library. What is ingested here is owned, forever."""

    def __init__(self) -> None:
        self._items: Dict[str, MediaItem] = {}

    def ingest(
        self, name: str, data: bytes, media_type: str = "application/octet-stream"
    ) -> MediaItem:
        """Store a real download: the bytes themselves, checksummed at rest."""
        if not data:
            raise ValueError("cannot ingest empty data: a download must be real bytes")
        item = MediaItem(name=name, data=data, media_type=media_type)
        self._items[name] = item
        return item

    def play(self, name: str) -> bytes:
        """Play a file: return its bytes. No license check exists to fail.

        The absence of a license check is the feature — ownership needs no
        permission.
        """
        return self._items[name].data

    def verify(self) -> List[Dict[str, object]]:
        """Re-hash every item. Returns one entry per corrupted item; empty is good."""
        corrupted = []
        for item in self._items.values():
            actual = hashlib.sha256(item.data).hexdigest()
            if actual != item.sha256:
                corrupted.append(
                    {"name": item.name, "expected": item.sha256, "actual": actual}
                )
        return corrupted

    def export(self, name: str, path: str) -> str:
        """Write the real file back out to disk. Yours to keep, anywhere."""
        item = self._items[name]
        with open(path, "wb") as fh:
            fh.write(item.data)
        return path

    def remove(self, name: str) -> None:
        """Delete a file from the library. Your choice, your bytes."""
        del self._items[name]

    def catalog(self) -> List[Dict[str, object]]:
        """Everything you own: names, types, sizes, hashes, ingest dates."""
        return [
            {
                "name": i.name,
                "media_type": i.media_type,
                "size": i.size,
                "sha256": i.sha256,
                "ingested": i.ingested,
            }
            for i in self._items.values()
        ]

    def ownership_receipt(self, name: str) -> Dict[str, object]:
        """Proof of ownership. Note what is absent: expiry, license, lessor."""
        item = self._items[name]
        return {
            "name": item.name,
            "sha256": item.sha256,
            "size": item.size,
            "ingested": item.ingested,
            "expires": None,
            "license_required": False,
            "owner": "you",
        }

    def save(self, path: str) -> None:
        """Persist the library to local JSON (bytes as base64). Still offline."""
        payload = {
            name: {
                "data": base64.b64encode(item.data).decode("ascii"),
                "sha256": item.sha256,
                "ingested": item.ingested,
                "media_type": item.media_type,
                "size": item.size,
            }
            for name, item in self._items.items()
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, path: str) -> "Library":
        """Restore a library saved with :meth:`save`."""
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        lib = cls()
        for name, record in payload.items():
            lib._items[name] = MediaItem(
                name=name,
                data=base64.b64decode(record["data"]),
                sha256=record["sha256"],
                ingested=record["ingested"],
                media_type=record["media_type"],
                size=record["size"],
            )
        return lib
