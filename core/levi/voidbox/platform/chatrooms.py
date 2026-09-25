"""Void Box platform — chatrooms: public room discovery, listing, join.

FORMED (thin by design): the crypto stays in ``levi.voidbox.rooms`` —
this module is the discovery/listing/joining surface over public rooms.
Every call gates on the adult gate first, then delegates to the
RoomStore, so rooms.py's LAWS (re-key on join, membership boundaries,
replay protection) hold unchanged.

SI side: every public entry point calls ``require_adult()`` FIRST —
adult-only, default OFF.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — Adult gate: every public entry point calls require_adult()
  first — default OFF, minors hard-locked out; every refusal names its
  remedy. (WIRED)
- L2 — Crypto stays in rooms.py: this module never seals, opens, or
  handles key material; all membership crypto is the primitive's.
  (WIRED)
- L3 — Public-only discovery: listing surfaces only rooms whose
  ``public`` flag is set; private rooms are never listed and self-join
  of a private room is refused by the primitive with its remedy.
  (WIRED)
- L4 — Metadata only: listings return room metadata (id, name, admin,
  member count, epoch) — never key material, never message content.
  (WIRED)

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from levi.plaiground.gate import require_adult
from levi.voidbox.platform import valid_id, valid_text
from levi.voidbox.rooms import RoomStore, voidbox_rooms_dir

#: The declared laws, machine-readable.
LAWS = (
    ("L1", "Adult gate: every public entry point calls require_adult() first — default OFF, minors hard-locked out; every refusal names its remedy. (WIRED)"),
    ("L2", "Crypto stays in rooms.py: this module never seals, opens, or handles key material; membership crypto is the primitive's. (WIRED)"),
    ("L3", "Public-only discovery: listing surfaces only rooms with the public flag; private rooms are never listed; self-join of a private room is refused by the primitive. (WIRED)"),
    ("L4", "Metadata only: listings return room metadata — never key material, never message content. (WIRED)"),
)


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("create_chatroom", True, "create_room(public=True) on the primitive."),
        ("list_public_rooms", True, "metadata scan of the rooms dir."),
        ("join_chatroom", True, "join_room on the primitive (re-keys, L2)."),
        ("leave_chatroom", True, "leave_room on the primitive (re-keys, L2)."),
        ("post_message", True, "seal_message on the primitive."),
        ("read_message", True, "open_message on the primitive."),
    ]


def create_chatroom(
    store: RoomStore, name: str, creator_id: str, home: Optional[Path] = None
) -> dict:
    """Create a public chatroom. The creator becomes admin (rooms.py)."""
    require_adult(home)
    name = valid_text(name, "room name", max_len=128)
    creator_id = valid_id(creator_id, "creator_id")
    return store.create_room(name, creator_id, public=True)


def _room_summary(room: dict) -> dict:
    return {
        "room_id": room["room_id"],
        "name": room["name"],
        "public": bool(room.get("public")),
        "admin_id": room["admin_id"],
        "created_at": room["created_at"],
        "epoch": room["epoch"],
        "member_count": sum(
            1 for m in room.get("members", {}).values()
            if m.get("removed_epoch") is None
        ),
    }


def list_public_rooms(home: Optional[Path] = None) -> list[dict]:
    """List public chatrooms: metadata only, never key material.

    Reads the rooms dir directly and surfaces only rooms with the
    ``public`` flag — private rooms are invisible here. Message content
    and key material are never touched.
    """
    require_adult(home)
    rooms_dir = voidbox_rooms_dir(home)
    out = []
    for path in sorted(rooms_dir.glob("room_*.json")):
        try:
            room = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # corrupt file: skip rather than break discovery
        if room.get("public"):
            out.append(_room_summary(room))
    return out


def join_chatroom(
    store: RoomStore, room_id: str, member_id: str, home: Optional[Path] = None
) -> dict:
    """Self-join a PUBLIC chatroom. Private rooms are refused by the
    primitive with the remedy (ask the admin)."""
    require_adult(home)
    room_id = valid_id(room_id, "room_id")
    member_id = valid_id(member_id, "member_id")
    return store.join_room(room_id, member_id)


def leave_chatroom(
    store: RoomStore, room_id: str, member_id: str, home: Optional[Path] = None
) -> dict:
    """Leave a chatroom (re-keys the room; the primitive's L2/L3 hold)."""
    require_adult(home)
    room_id = valid_id(room_id, "room_id")
    member_id = valid_id(member_id, "member_id")
    return store.leave_room(room_id, member_id)


def post_message(
    store: RoomStore,
    room_id: str,
    sender_id: str,
    text: str,
    home: Optional[Path] = None,
) -> dict:
    """Post to a chatroom (sealed by the rooms primitive)."""
    require_adult(home)
    room_id = valid_id(room_id, "room_id")
    sender_id = valid_id(sender_id, "sender_id")
    text = valid_text(text, "message", max_len=4000)
    return store.seal_message(room_id, sender_id, text)


def read_message(
    store: RoomStore,
    room_id: str,
    member_id: str,
    envelope: dict,
    home: Optional[Path] = None,
) -> dict:
    """Open a chatroom envelope as a member (primitive enforces
    membership, epoch, and replay)."""
    require_adult(home)
    room_id = valid_id(room_id, "room_id")
    member_id = valid_id(member_id, "member_id")
    return store.open_message(room_id, member_id, envelope)
