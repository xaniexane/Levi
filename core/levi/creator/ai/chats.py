"""AI chats — SFW 1:1 conversations and owner-moderated group chats.

The reformed counterpart to the SI chats: same shape (chat containers,
member lists, owner moderation, open/closed), clean rules — message
bodies pass the SFW check, the store is plain local JSONL. No gate on
this track.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator import TRACK_AI
from levi.creator.ai.rules import check_sfw
from levi.creator.store import ai_read_all, ai_write

_MAX_GROUP_MEMBERS = 50


class ChatError(ValueError):
    """A chat operation was invalid."""


class ChatDeniedError(PermissionError):
    """The caller is not a member / not the owner."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_chat(chat_id: str, home: Optional[Path]) -> Dict[str, Any]:
    chat = next(
        (c for c in ai_read_all(home, "creator_chats") if c["id"] == chat_id), None
    )
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
    if not other_id or not other_id.strip():
        raise ChatError("the other party is required")
    return ai_write(
        home,
        "creator_chats",
        {
            "track": TRACK_AI,
            "kind": "dm",
            "owner": creator_handle,
            "name": None,
            "members": [creator_handle, other_id.strip()],
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
    name = check_sfw(name or "", home)
    clean = [m.strip() for m in (member_ids or []) if m and m.strip()]
    members = [creator_handle] + [m for m in clean if m != creator_handle]
    if len(members) > _MAX_GROUP_MEMBERS:
        raise ChatError("group is capped at %d members" % _MAX_GROUP_MEMBERS)
    return ai_write(
        home,
        "creator_chats",
        {
            "track": TRACK_AI,
            "kind": "group",
            "owner": creator_handle,
            "name": name,
            "members": members,
            "open": True,
            "created_at": _utcnow(),
        },
    )


def send_chat_message(
    chat_id: str, sender_id: str, body: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Send a message into a chat. Members only, chat must be open."""
    chat = _get_chat(chat_id, home)
    _require_member(chat, sender_id)
    if not chat["open"]:
        raise ChatError("this chat is closed")
    return ai_write(
        home,
        "creator_chat_messages",
        {
            "track": TRACK_AI,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "body": check_sfw(body or "", home),
            "sent_at": _utcnow(),
        },
    )


def chat_thread(chat_id: str, user_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read a chat's messages. Members only."""
    chat = _get_chat(chat_id, home)
    _require_member(chat, user_id)
    return [m for m in ai_read_all(home, "creator_chat_messages") if m["chat_id"] == chat_id]


def list_chats(user_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Chats the user belongs to — metadata, no message bodies."""
    return [
        dict(c) for c in ai_read_all(home, "creator_chats") if user_id in c["members"]
    ]


def add_member(
    chat_id: str, owner_id: str, member_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Add a member to a group chat. Owner only."""
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    if chat["kind"] != "group":
        raise ChatError("only group chats take new members")
    member_id = (member_id or "").strip()
    if not member_id:
        raise ChatError("member_id is required")
    members = chat["members"]
    if member_id not in members:
        if len(members) >= _MAX_GROUP_MEMBERS:
            raise ChatError("group is capped at %d members" % _MAX_GROUP_MEMBERS)
        members = members + [member_id]
        _rewrite_chat(home, chat_id, {"members": members})
    return dict(_get_chat(chat_id, home), members=members)


def remove_member(
    chat_id: str, owner_id: str, member_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Remove a member from a group chat. Owner only; never the owner."""
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    if chat["kind"] != "group":
        raise ChatError("only group chats lose members")
    if member_id == chat["owner"]:
        raise ChatError("the owner cannot be removed")
    members = [m for m in chat["members"] if m != member_id]
    _rewrite_chat(home, chat_id, {"members": members})
    return dict(_get_chat(chat_id, home), members=members)


def close_chat(chat_id: str, owner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Close a chat. Owner only; sending stops, history stays readable."""
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    _rewrite_chat(home, chat_id, {"open": False, "closed_at": _utcnow()})
    return _get_chat(chat_id, home)


def reopen_chat(chat_id: str, owner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Reopen a closed chat. Owner only."""
    chat = _get_chat(chat_id, home)
    _require_owner(chat, owner_id)
    _rewrite_chat(home, chat_id, {"open": True})
    return _get_chat(chat_id, home)


def _rewrite_chat(home: Optional[Path], chat_id: str, updates: Dict[str, Any]) -> None:
    """Patch one chat record in the plain AI store (no seal on this track)."""
    from levi.creator.store import _ai_dir
    import json as _json

    path = _ai_dir(home) / "creator_chats.jsonl"
    records = ai_read_all(home, "creator_chats")
    for rec in records:
        if rec["id"] == chat_id:
            rec.update(updates)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(_json.dumps(rec, sort_keys=True) + "\n")
