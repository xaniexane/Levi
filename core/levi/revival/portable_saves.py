"""portable_saves — game saves the player owns, exports, and keeps.

Studied from: games-hunt-20260916-0022/report.md (Find 2 — honest inversion).

The load-bearing idea: a save file that lives on someone else's
server is not yours — it is a loan they can recall. The honest
inversion makes the save a plain JSON document the player holds,
copies, and moves between machines, with checksums for integrity and
no remote kill switch anywhere in the design.

LEVI's take: ``SaveSlot`` serializes game state to JSON with a schema
version, a SHA-256 integrity checksum, and a manifest of what the
save contains. ``export_save`` writes it to a path the player chose;
``import_save`` re-reads it, verifies the checksum, and migrates
older schema versions forward through registered migrators.
``attempt_remote_revoke`` exists only to refuse: there is no
revocation path, so calling it raises ``NoRevocationPath``. Device
transfer is just copy-the-file; ``pack_for_move`` bundles saves into
one archive for convenience.

Honest limits: integrity is checksum-based, not cryptographic — a
player can hand-edit their own save (that's the point: it's theirs),
so this is not anti-cheat. Schema migration only moves forward
through migrators you registered.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/portable-saves"


class SaveCorrupt(Exception):
    """Checksum mismatch or unreadable save file."""


class NoRevocationPath(Exception):
    """There is deliberately no remote revoke — the call is refused."""


class UnknownSchema(Exception):
    """No migrator registered for this schema version."""


CURRENT_SCHEMA = 1


def _checksum(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class SaveSlot:
    """One player-owned save: state + manifest + integrity."""

    slot_name: str
    state: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def manifest(self) -> Dict[str, Any]:
        return {
            "slot": self.slot_name,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state_keys": sorted(self.state.keys()),
            "revocable": False,  # by design: no server-side revocation path
        }

    def to_document(self) -> Dict[str, Any]:
        payload = {
            "format": "levi-portable-save/1",
            "slot": self.slot_name,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": self.state,
        }
        payload["checksum"] = _checksum({k: v for k, v in payload.items()})
        return payload

    @classmethod
    def from_document(cls, doc: Dict[str, Any]) -> "SaveSlot":
        if doc.get("format") != "levi-portable-save/1":
            raise SaveCorrupt(f"unknown save format: {doc.get('format')!r}")
        body = {k: v for k, v in doc.items() if k != "checksum"}
        if _checksum(body) != doc.get("checksum"):
            raise SaveCorrupt("checksum mismatch — file damaged or tampered")
        return cls(
            slot_name=doc["slot"],
            state=doc.get("state", {}),
            schema_version=doc.get("schema_version", 1),
            created_at=doc.get("created_at", time.time()),
            updated_at=doc.get("updated_at", time.time()),
        )


class SaveLibrary:
    """A player's shelf of saves: export, import, migrate, move."""

    def __init__(self) -> None:
        self._migrators: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_migrator(
        self, from_version: int, migrator: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Teach the library to move a save from ``from_version`` forward."""
        self._migrators[from_version] = migrator

    def export_save(self, slot: SaveSlot, path: str) -> str:
        """Write the save to a player-chosen path. Returns the path."""
        slot.updated_at = time.time()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(slot.to_document(), fh, indent=2, sort_keys=True)
        return path

    def import_save(self, path: str) -> SaveSlot:
        """Read a save back, verify integrity, migrate old schemas forward."""
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        slot = SaveSlot.from_document(doc)
        while slot.schema_version < CURRENT_SCHEMA:
            migrator = self._migrators.get(slot.schema_version)
            if migrator is None:
                raise UnknownSchema(f"no migrator from schema v{slot.schema_version}")
            slot.state = migrator(slot.state)
            slot.schema_version += 1
        return slot

    def pack_for_move(self, slots: List[SaveSlot], path: str) -> str:
        """Bundle several saves into one archive file for device transfer."""
        archive = {
            "format": "levi-portable-save-pack/1",
            "packed_at": time.time(),
            "saves": [slot.to_document() for slot in slots],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(archive, fh, indent=2, sort_keys=True)
        return path

    def unpack_move(self, path: str) -> List[SaveSlot]:
        """Unpack a move archive; each save is integrity-checked."""
        with open(path, "r", encoding="utf-8") as fh:
            archive = json.load(fh)
        if archive.get("format") != "levi-portable-save-pack/1":
            raise SaveCorrupt(f"unknown pack format: {archive.get('format')!r}")
        slots = [SaveSlot.from_document(doc) for doc in archive.get("saves", [])]
        for slot in slots:
            while slot.schema_version < CURRENT_SCHEMA:
                migrator = self._migrators.get(slot.schema_version)
                if migrator is None:
                    raise UnknownSchema(
                        f"no migrator from schema v{slot.schema_version}"
                    )
                slot.state = migrator(slot.state)
                slot.schema_version += 1
        return slots

    def attempt_remote_revoke(self, slot_name: str) -> None:
        """Refused by design: saves have no server-side revocation path."""
        raise NoRevocationPath(
            f"save {slot_name!r} is player-owned — no remote party can revoke it"
        )


def list_saves(directory: str) -> List[str]:
    """Save files the player keeps in a directory. No server involved."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        f for f in os.listdir(directory) if f.endswith((".save.json", ".savepack.json"))
    )
