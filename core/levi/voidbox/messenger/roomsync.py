"""Void Box Messenger — room-state sync between keepers.

A room lives in each keeper's own ``RoomStore``. When the admin adds or
removes a member, ``rooms`` re-keys — and the other keepers need the new
epoch keys. This module exports a member's slice of room state from the
admin's store and applies it into the recipient's store, re-wrapping
every epoch key under the RECIPIENT's own master-derived keys. The
payload itself is sealed inside the 1:1 E2E channel by the caller
(``app.py`` sends it as a ``room-sync`` DM frame) — epoch keys never
cross the wire in the clear (M5).

This module uses the keeper-only seams of ``RoomStore`` (``_read_room``,
``_epoch_key_bytes``, ``_wrap_key``, ``_member_wrap_key``,
``_write_room``) — the keeper's own store, the keeper's own keys (M6).
``rooms.py`` itself is NOT modified.

Preserved across sync (never clobbered):
- the recipient's replay state (``seen``) — wiping it would re-open the
  replay window;
- the recipient's own send sequence (``sent_seq``);
- ``created_at`` for rooms already known locally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from levi.cybrus.veil import _b64d, _b64e, _seal_backend, _utcnow
from levi.plaiground.gate import require_adult

__all__ = ["RoomSyncError", "export_room_state", "apply_room_state"]


class RoomSyncError(ValueError):
    """Room state could not be exported or applied."""


# ---------------------------------------------------------------------------
# export — admin side
# ---------------------------------------------------------------------------


def export_room_state(store, room_id: str, member_id: str,
                      home: Optional[Path] = None) -> dict:
    """Export ``member_id``'s slice of ``room_id``: metadata, the member
    records (so the recipient can check sender membership per epoch),
    and the epoch keys the member's membership covers — raw bytes here,
    sealed into the DM channel by the caller (M5)."""
    require_adult(home)  # M7: FIRST
    try:
        room = store._read_room(room_id)
    except Exception as exc:
        raise RoomSyncError("cannot export unknown room %r" % (room_id,)) from exc
    member = room["members"].get(member_id)
    if member is None:
        raise RoomSyncError("identity %r is not a member of %r" % (member_id, room_id))
    current_epoch = int(room["epoch"])
    joined = int(member.get("joined_epoch", 0))
    removed = member.get("removed_epoch")
    last = current_epoch if removed is None else int(removed) - 1
    keys: dict[str, str] = {}
    for epoch in range(joined, last + 1):
        try:
            keys[str(epoch)] = _b64e(store._epoch_key_bytes(room_id, epoch))
        except Exception as exc:
            raise RoomSyncError(
                "cannot unwrap epoch %d for export: %s" % (epoch, exc)
            ) from exc
    return {
        "sync_version": 1,
        "room_id": room_id,
        "name": room["name"],
        "public": bool(room.get("public")),
        "admin_id": room["admin_id"],
        "created_at": room["created_at"],
        "epoch": current_epoch,
        "members": {
            mid: {
                "joined_epoch": m["joined_epoch"],
                "joined_at": m["joined_at"],
                "removed_epoch": m.get("removed_epoch"),
                "removed_at": m.get("removed_at"),
                "devices": {
                    did: {
                        "fingerprint": d["fingerprint"],
                        "registered_at": d.get("registered_at"),
                        "revoked": bool(d.get("revoked")),
                        "revoked_at": d.get("revoked_at"),
                        "revoked_epoch": d.get("revoked_epoch"),
                    }
                    for did, d in m.get("devices", {}).items()
                },
            }
            for mid, m in room["members"].items()
        },
        "keys": keys,  # epoch -> b64 raw key, for THIS member's span
        "rekey_log": list(room.get("rekey_log", [])),
        "exported_at": _utcnow(),
    }


# ---------------------------------------------------------------------------
# apply — recipient side
# ---------------------------------------------------------------------------


def apply_room_state(store, payload: dict, member_id: str,
                     home: Optional[Path] = None) -> dict:
    """Apply an exported room state into the recipient's own store,
    re-wrapping every epoch key under the recipient's own keys:

    - ``wrapped_epochs``: sealed under the master-derived wrap key;
    - ``key_copies[member_id]``: sealed under the per-member wrap key.

    Only the recipient's own copies are written (M6) — the payload
    carries no other member's key material, and the store will not
    resolve epochs outside the member's span anyway. Returns
    ``{"room_id", "epoch", "new_room"}``.
    """
    require_adult(home)  # M7: FIRST
    if not isinstance(payload, dict) or payload.get("sync_version") != 1:
        raise RoomSyncError("bad room-sync payload")
    room_id = payload["room_id"]
    if member_id not in payload.get("members", {}):
        raise RoomSyncError(
            "sync payload for %r carries no membership for %r — refusing "
            "to install a room you don't belong to" % (room_id, member_id)
        )
    # Preserve the recipient's local replay state and send sequence —
    # wiping `seen` would re-open the replay window (rooms L5).
    try:
        existing = store._read_room(room_id)
        keep_seen = existing.get("seen", {})
        keep_sent = existing.get("sent_seq", {})
        created_at = existing.get("created_at")
    except Exception:
        keep_seen, keep_sent, created_at = {}, {}, None

    wrap_key = store._wrap_key()
    member_key = store._member_wrap_key(member_id)
    wrapped_epochs: dict[str, str] = {}
    for epoch_s, key_b64 in payload["keys"].items():
        epoch = int(epoch_s)
        key = _b64d(key_b64)
        if len(key) != 32:
            raise RoomSyncError("bad epoch key bytes at epoch %d" % epoch)
        wrapped_epochs[epoch_s] = _b64e(
            _seal_backend(wrap_key, key, store._wrap_aad(room_id, epoch))
        )
    copies: dict[str, str] = {}
    for epoch_s, key_b64 in payload["keys"].items():
        epoch = int(epoch_s)
        copies[epoch_s] = _b64e(
            _seal_backend(
                member_key, _b64d(key_b64),
                store._copy_aad(room_id, member_id, epoch),
            )
        )
    room = {
        "room_id": room_id,
        "name": payload["name"],
        "public": bool(payload["public"]),
        "admin_id": payload["admin_id"],
        "created_at": created_at or payload["created_at"],
        "epoch": int(payload["epoch"]),
        "members": {
            mid: {
                "joined_epoch": m["joined_epoch"],
                "joined_at": m["joined_at"],
                "removed_epoch": m.get("removed_epoch"),
                "removed_at": m.get("removed_at"),
                "devices": dict(m.get("devices", {})),
            }
            for mid, m in payload["members"].items()
        },
        "wrapped_epochs": wrapped_epochs,
        "key_copies": {member_id: copies},
        "rekey_log": list(payload.get("rekey_log", [])),
        "sent_seq": dict(keep_sent),
        "seen": dict(keep_seen),
        "synced_at": _utcnow(),
    }
    store._write_room(room)
    return {
        "room_id": room_id,
        "epoch": int(payload["epoch"]),
        "new_room": created_at is None,
    }
