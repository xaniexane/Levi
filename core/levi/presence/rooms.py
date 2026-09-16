"""Room state machine: rooms, membership, presence, message fan-out.

Pure logic — no sockets. The TCP layer (server.py) turns the events this
module returns into wire messages. Everything is guarded by one lock so
the threaded server cannot corrupt room state.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "peer") -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12])


class RoomBook:
    """In-memory drop-in rooms.

    Clients are identified by self-asserted display name + an ephemeral
    client id. There are no accounts: identity here is a nametag, not a
    credential, and the docs say so plainly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # room name -> {"topic": str, "created_at": str,
        #               "members": {client_id: member dict}}
        self._rooms: Dict[str, Dict] = {}
        # client_id -> {"name": str, "rooms": set[str]}
        self._clients: Dict[str, Dict] = {}

    # -- client bookkeeping -------------------------------------------------
    def register(self, name: str, client_id: Optional[str] = None) -> str:
        """Register (or re-register) a display name. Returns the client id."""
        cid = client_id or new_id()
        name = (name or "anonymous").strip()[:64] or "anonymous"
        with self._lock:
            entry = self._clients.get(cid, {"rooms": set()})
            entry["name"] = name
            self._clients[cid] = entry
        return cid

    def name_of(self, client_id: str) -> str:
        with self._lock:
            entry = self._clients.get(client_id)
            return entry["name"] if entry else "anonymous"

    # -- rooms ---------------------------------------------------------------
    def create_room(self, name: str, topic: str = "") -> Tuple[bool, str]:
        name = (name or "").strip()[:64]
        if not name:
            return False, "room name is empty"
        with self._lock:
            if name in self._rooms:
                return False, "room %r already exists" % name
            self._rooms[name] = {
                "topic": (topic or "")[:280],
                "created_at": now_iso(),
                "members": {},
            }
        return True, "room %r created" % name

    def list_rooms(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    "name": name,
                    "topic": room["topic"],
                    "members": len(room["members"]),
                    "created_at": room["created_at"],
                }
                for name, room in sorted(self._rooms.items())
            ]

    def room_members(self, room: str) -> Tuple[bool, List[Dict]]:
        with self._lock:
            data = self._rooms.get(room)
            if data is None:
                return False, []
            return True, [
                {
                    "client_id": cid,
                    "name": m["name"],
                    "joined_at": m["joined_at"],
                    "last_seen": m["last_seen"],
                }
                for cid, m in sorted(data["members"].items())
            ]

    # -- presence -------------------------------------------------------------
    def join(self, client_id: str, room: str) -> Tuple[bool, object]:
        """Join a room. Returns (ok, event-or-error)."""
        with self._lock:
            data = self._rooms.get(room)
            client = self._clients.get(client_id)
            if data is None:
                return False, "no such room %r" % room
            if client is None:
                return False, "unknown client; send hello first"
            stamp = now_iso()
            data["members"][client_id] = {
                "name": client["name"],
                "joined_at": stamp,
                "last_seen": stamp,
            }
            client["rooms"].add(room)
            event = {
                "event": "presence",
                "room": room,
                "name": client["name"],
                "client_id": client_id,
                "state": "joined",
                "at": stamp,
            }
            recipients = [cid for cid in data["members"] if cid != client_id]
            return True, (event, recipients)

    def leave(self, client_id: str, room: str) -> Tuple[bool, object]:
        with self._lock:
            data = self._rooms.get(room)
            client = self._clients.get(client_id)
            if data is None or client is None:
                return False, "no such room or unknown client"
            member = data["members"].pop(client_id, None)
            client["rooms"].discard(room)
            if member is None:
                return False, "not in room %r" % room
            event = {
                "event": "presence",
                "room": room,
                "name": member["name"],
                "client_id": client_id,
                "state": "left",
                "at": now_iso(),
            }
            recipients = list(data["members"])
            return True, (event, recipients)

    def disconnect(self, client_id: str) -> List[Tuple[Dict, List[str]]]:
        """Drop a client from every room. Returns [(event, recipients)]."""
        with self._lock:
            client = self._clients.pop(client_id, None)
            if client is None:
                return []
            out = []
            for room in sorted(client["rooms"]):
                data = self._rooms.get(room)
                if data is None:
                    continue
                member = data["members"].pop(client_id, None)
                if member is None:
                    continue
                out.append(
                    (
                        {
                            "event": "presence",
                            "room": room,
                            "name": member["name"],
                            "client_id": client_id,
                            "state": "left",
                            "at": now_iso(),
                        },
                        list(data["members"]),
                    )
                )
            return out

    def heartbeat(self, client_id: str) -> None:
        stamp = now_iso()
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return
            for room in client["rooms"]:
                data = self._rooms.get(room)
                member = data["members"].get(client_id) if data else None
                if member is not None:
                    member["last_seen"] = stamp

    def touch(self, client_id: str, room: str) -> None:
        """Mark activity (a posted message counts as presence)."""
        stamp = now_iso()
        with self._lock:
            data = self._rooms.get(room)
            if data is None:
                return
            member = data["members"].get(client_id)
            if member is not None:
                member["last_seen"] = stamp

    def sweep(self, idle_seconds: float = 180.0) -> List[Tuple[Dict, List[str]]]:
        """Time out members idle longer than *idle_seconds*.

        Returns [(event, recipients)] like disconnect(). Presence is
        honest: a timed-out peer is reported as timed out, not as left.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            out = []
            for room, data in self._rooms.items():
                for cid, member in list(data["members"].items()):
                    try:
                        last = datetime.fromisoformat(member["last_seen"])
                    except ValueError:
                        continue
                    if (now - last).total_seconds() > idle_seconds:
                        data["members"].pop(cid, None)
                        client = self._clients.get(cid)
                        if client is not None:
                            client["rooms"].discard(room)
                        out.append(
                            (
                                {
                                    "event": "presence",
                                    "room": room,
                                    "name": member["name"],
                                    "client_id": cid,
                                    "state": "timeout",
                                    "at": now_iso(),
                                },
                                list(data["members"]),
                            )
                        )
            return out

    # -- messages ---------------------------------------------------------------
    def post(self, client_id: str, room: str, text: str) -> Tuple[bool, object]:
        """Post a message. Returns (ok, (message, recipients) | error)."""
        text = (text or "").strip()
        if not text:
            return False, "empty message"
        if len(text) > 4000:
            return False, "message too long (4000 chars max)"
        with self._lock:
            data = self._rooms.get(room)
            client = self._clients.get(client_id)
            if data is None:
                return False, "no such room %r" % room
            if client is None:
                return False, "unknown client; send hello first"
            member = data["members"].get(client_id)
            if member is None:
                return False, "join room %r before posting" % room
            member["last_seen"] = now_iso()
            message = {
                "event": "message",
                "room": room,
                "from": client["name"],
                "client_id": client_id,
                "text": text,
                "at": member["last_seen"],
            }
            recipients = [cid for cid in data["members"] if cid != client_id]
            return True, (message, recipients)
