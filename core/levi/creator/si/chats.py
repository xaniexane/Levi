"""SI private chats — 1:1 conversations and owner-moderated group chats.

A chat is a sealed container with a member list. Groups are owned by the
creator: only the owner adds or removes members, closes, or reopens the
chat. Membership is enforced on every send and read — a non-member gets
nothing, not even the member list.

All entries are gate-locked (Plaiground law: adult-only, default OFF,
minors hard-locked out); message bodies pass the bounds check; records
are sealed at rest with the Veil-lineage envelope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_SI
from levi.creator.store import si_delete, si_read_all, si_update, si_write
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

_MAX_GROUP_MEMBERS = 50


class ChatError(ValueError):
    """A chat operation was invalid."""


class ChatDeniedError(PermissionError):
    """The caller is not a member / not the owner."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_chat(chat_id: str, home: Optional[Path]) -> Dict[str, Any]:
    chat = next((c for c in si_read_all(home, "chats") if c["id"] == chat_id), None)
    if chat is None:
        raise ChatError("unknown chat %r" % chat_id)
    return chat


def _require_member(chat: Dict[str, Any], user_id: str) -> None:
    if user_id not in chat["members"]:
        raise ChatDeniedError("not a member of this chat")


def _require_owner(chat: Dict[str, Any], user_id: str) -> None:
    if chat["owner"] != user_id:
        raise ChatDeniedError("only the chat owner may do that")


def create_chat(
    creator_handle: str, other_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Open a private 1:1 chat between the creator and one other user."""
    require_adult(home)
    if not other_id or not other_id.strip():
        raise ChatError("the other party is required")
    other_id = other_id.strip()
    return si_write(
        home,
        "chats",
        {
            "track": TRACK_SI,
            "kind": "dm",
            "owner": creator_handle,
            "name": None,
            "members": [creator_handle, other_id],
            "open": True,
            "created_at": _utcnow(),
        },
    )


def create_group(
    creator_handle: str,
    name: str,
    member_ids: List[str],
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create an owner-moderated group chat. The creator owns it."""
    require_adult(home)
    check_bounds(name or "", home)
    clean = [m.strip() for m in (member_ids or []) if m and m.strip()]
    members = [creator_handle] + [m for m in clean if m != creator_handle]
    if len(members) > _MAX_GROUP_MEMBERS:
        raise ChatError("group is capped at %d members" % _MAX_GROUP_MEMBERS)
    return si_write(
        home,
        "chats",
        {
            "track": TRACK_SI,
            "kind": "group",
            "owner": creator_handle,
            "name": (name or "").strip(),
            "members": members,
            "open": True,
            "created_at": _utcnow(),
        },
    )


def send_chat_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Send a message into a chat. Members only, chat must be open."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_member(chat, sender_id)
    if not chat["open"]:
        raise ChatError("this chat is closed")
    if not body or not body.strip():
        raise ChatError("message body is required")
    check_bounds(body, home)
    return si_write(
        home,
        "chat_messages",
        {
            "track": TRACK_SI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "body": body.strip(),
            "sent_at": _utcnow(),
        },
    )


def chat_thread(chat_id: str, user_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read a chat's messages. Members only."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_member(chat, user_id)
    return [m for m in si_read_all(home, "chat_messages") if m["chat_id"] == chat_id]


def list_chats(user_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Chats the user belongs to — metadata, no message bodies."""
    require_adult(home)
    return [
        {k: v for k, v in c.items()}
        for c in si_read_all(home, "chats")
        if user_id in c["members"]
    ]


def add_member(
    chat_id: str, owner_id: str, member_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Add a member to a group chat. Owner only."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    if chat["kind"] != "group":
        raise ChatError("only group chats take new members")
    member_id = (member_id or "").strip()
    if not member_id:
        raise ChatError("member_id is required")
    if member_id in chat["members"]:
        return chat
    if len(chat["members"]) >= _MAX_GROUP_MEMBERS:
        raise ChatError("group is capped at %d members" % _MAX_GROUP_MEMBERS)
    members = chat["members"] + [member_id]
    return si_update(home, "chats", chat_id, {"members": members})


def remove_member(
    chat_id: str, owner_id: str, member_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Remove a member from a group chat. Owner only; never the owner."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    if chat["kind"] != "group":
        raise ChatError("only group chats lose members")
    if member_id == chat["owner"]:
        raise ChatError("the owner cannot be removed")
    members = [m for m in chat["members"] if m != member_id]
    return si_update(home, "chats", chat_id, {"members": members})


def close_chat(chat_id: str, owner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Close a chat. Owner only; sending stops, history stays readable."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    return si_update(home, "chats", chat_id, {"open": False, "closed_at": _utcnow()})


def reopen_chat(chat_id: str, owner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Reopen a closed chat. Owner only."""
    require_adult(home)
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    return si_update(home, "chats", chat_id, {"open": True})
