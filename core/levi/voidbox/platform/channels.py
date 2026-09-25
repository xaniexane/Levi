"""Void Box platform — channels: Telegram-style broadcast channels.

FORMED on the rooms primitive: a channel is a public room on
``levi.voidbox.rooms`` plus a registry entry carrying the broadcast
roles — admin-post, subscriber-read. Subscribers join the underlying
room (primitive membership, re-key, replay all hold); posting is gated
to the channel owner at THIS surface.

Honest boundary: post-only roles are enforced by the platform surface,
not inside the primitive — the primitive itself is member-sealed. A
caller with direct RoomStore access can seal on the underlying room;
through the channel API, only the owner posts.

SI side: every public entry point calls ``require_adult()`` FIRST —
adult-only, default OFF.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — Adult gate: every public entry point calls require_adult()
  first — default OFF, minors hard-locked out; every refusal names its
  remedy. (WIRED)
- L2 — Crypto stays in rooms.py: channels never seal, open, or handle
  key material directly; all of it is the primitive's. (WIRED)
- L3 — Admin-post: only the channel owner may post through the channel
  API; anyone else is refused with the remedy. (WIRED — at the
  platform surface, not inside the primitive; the boundary is stated,
  not hidden.)
- L4 — Subscriber-read: subscribers are members of the underlying
  public room, so the primitive's membership/epoch/replay laws govern
  reading. (WIRED)
- L5 — Nothing thrown away: unsubscribes mark state; channel records
  persist. (WIRED)

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from levi.voidbox.platform import (
    JsonStore,
    PlatformError,
    ProfileNotFoundError,
    utcnow,
    valid_id,
    valid_text,
)
from levi.voidbox.rooms import NotAdminError, RoomStore

#: The declared laws, machine-readable.
LAWS = (
    ("L1", "Adult gate: every public entry point calls require_adult() first — default OFF, minors hard-locked out; every refusal names its remedy. (WIRED)"),
    ("L2", "Crypto stays in rooms.py: channels never seal, open, or handle key material directly. (WIRED)"),
    ("L3", "Admin-post: only the channel owner may post through the channel API; anyone else refused. Enforced at the platform surface — the boundary is stated, not hidden. (WIRED)"),
    ("L4", "Subscriber-read: subscribers are members of the underlying public room; the primitive's membership/epoch/replay laws govern reading. (WIRED)"),
    ("L5", "Nothing thrown away: unsubscribes mark state; channel records persist. (WIRED)"),
)


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("create_channel", True, "public room on the primitive + registry."),
        ("list_channels", True, "metadata summaries from the registry."),
        ("subscribe", True, "join_room on the underlying room."),
        ("unsubscribe", True, "leave_room on the underlying room."),
        (
            "post",
            True,
            "owner-only seal via the primitive; role enforced at the "
            "platform surface.",
        ),
        ("read", True, "open_message on the primitive."),
    ]


class ChannelStore(JsonStore):
    """Channel registry. Crypto ops take the keeper's RoomStore.

    ``home`` MUST be the same home the RoomStore was built with —
    channels are a surface over that store's rooms.
    """

    _FILENAME = "channels.json"

    def __init__(self, home: Optional[Path] = None):
        super().__init__(home)

    def create_channel(
        self, rooms: RoomStore, owner_id: str, name: str, description: str = ""
    ) -> dict:
        """Create a broadcast channel: a public room + registry entry.
        The owner is the room admin and the only poster."""
        self._require_adult()
        owner_id = valid_id(owner_id, "owner_id")
        name = valid_text(name, "channel name", max_len=128)
        description = valid_text(
            description, "channel description", max_len=500, allow_empty=True
        )
        meta = rooms.create_room(name, owner_id, public=True)
        channel_id = "chan_" + secrets.token_hex(8)
        data = self._load()
        channels = data.setdefault("channels", {})
        channels[channel_id] = {
            "channel_id": channel_id,
            "room_id": meta["room_id"],
            "owner_id": owner_id,
            "name": name,
            "description": description,
            "created_at": utcnow(),
            "archived": False,
        }
        self._save(data)
        return dict(channels[channel_id])

    def get_channel(self, channel_id: str) -> dict:
        """Fetch a channel record by id."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        return dict(self._get(self._load(), channel_id))

    def list_channels(self) -> list[dict]:
        """List channels: metadata summaries, no key material."""
        self._require_adult()
        data = self._load()
        return [
            {
                "channel_id": c["channel_id"],
                "room_id": c["room_id"],
                "owner_id": c["owner_id"],
                "name": c["name"],
                "description": c["description"],
                "created_at": c["created_at"],
                "archived": c["archived"],
            }
            for c in data.get("channels", {}).values()
            if not c.get("archived")
        ]

    @staticmethod
    def _get(data: dict, channel_id: str) -> dict:
        channel = data.get("channels", {}).get(channel_id)
        if channel is None:
            raise ProfileNotFoundError("no channel %r." % channel_id)
        return channel

    def subscribe(
        self, rooms: RoomStore, channel_id: str, subscriber_id: str
    ) -> dict:
        """Subscribe: join the underlying public room (re-keys; the
        primitive's membership laws hold)."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        channel = self._get(self._load(), channel_id)
        if channel.get("archived"):
            raise PlatformError("channel %r is archived." % channel_id)
        return rooms.join_room(channel["room_id"], subscriber_id)

    def unsubscribe(
        self, rooms: RoomStore, channel_id: str, subscriber_id: str
    ) -> dict:
        """Unsubscribe: leave the underlying room. Marked, never deleted
        from the registry (L5)."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        channel = self._get(self._load(), channel_id)
        return rooms.leave_room(channel["room_id"], subscriber_id)

    def post(
        self, rooms: RoomStore, channel_id: str, author_id: str, body: str
    ) -> dict:
        """Post to the channel — OWNER ONLY (L3). Anyone else is refused
        with the remedy. The envelope is sealed by the primitive."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        author_id = valid_id(author_id, "author_id")
        body = valid_text(body, "post body", max_len=4000)
        channel = self._get(self._load(), channel_id)
        if author_id != channel["owner_id"]:
            raise NotAdminError(
                "only the channel owner (%r) may post to channel %r — "
                "subscribers read." % (channel["owner_id"], channel_id)
            )
        return rooms.seal_message(channel["room_id"], author_id, body)

    def read(
        self,
        rooms: RoomStore,
        channel_id: str,
        subscriber_id: str,
        envelope: dict,
    ) -> dict:
        """Open a channel envelope as a subscriber (the primitive
        enforces membership, epoch, and replay)."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        channel = self._get(self._load(), channel_id)
        return rooms.open_message(channel["room_id"], subscriber_id, envelope)

    def archive_channel(
        self, channel_id: str, by_owner: str
    ) -> dict:
        """Archive a channel (owner only). Marked archived, never
        deleted (L5); the underlying room persists untouched."""
        self._require_adult()
        channel_id = valid_id(channel_id, "channel_id")
        by_owner = valid_id(by_owner, "by_owner")
        data = self._load()
        channel = self._get(data, channel_id)
        if by_owner != channel["owner_id"]:
            raise NotAdminError(
                "only the channel owner (%r) may archive channel %r."
                % (channel["owner_id"], channel_id)
            )
        channel["archived"] = True
        channel["archived_at"] = utcnow()
        self._save(data)
        return dict(channel)
