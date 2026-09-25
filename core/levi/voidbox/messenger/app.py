"""Void Box Messenger — the standalone messenger surface (app layer).

:class:`Messenger` unifies 1:1 conversations (via ``veil_chat``) and
group conversations (via ``rooms``) over the ``relay`` transport. It is
the keeper's own agent: it seals/opens only with the keeper's own keys,
it opens only envelopes addressed to the keeper or to a room the keeper
belongs to (M6), and every public entry point calls
``require_adult()`` FIRST (M7).

DM plaintexts are JSON frames so the 1:1 channel can carry control
traffic alongside chat:
- ``{"type": "chat", "text": ...}`` — a chat message;
- ``{"type": "room-sync", "room_id": ..., "payload": ...}`` — room state
  for the recipient's own store (epoch keys inside are sealed by the
  DM's E2E envelope — M5).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from levi.cybrus.veil import _utcnow
from levi.cybrus.veil_chat import VeilChat, VeilChatError, x25519_backend
from levi.plaiground.gate import require_adult, verify_adult
from levi.voidbox.messenger.client import MessengerTransport
from levi.voidbox.messenger.roomsync import (
    RoomSyncError,
    apply_room_state,
    export_room_state,
)
from levi.voidbox.relay import DEFAULT_HOST, DEFAULT_PORT
from levi.voidbox.rooms import (
    EpochError,
    NotMemberError,
    ReplayError,
    RoomError,
    RoomStore,
)

__all__ = ["Messenger", "MessengerError", "KEEPER_ID_RE"]

#: Keeper ids double as relay addresses AND room member ids, so they
#: must satisfy the strictest charset of the two: rooms' member ids.
KEEPER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_MESSENGER_SUBDIR = "messenger"
_STATE_FILE = "state.json"


class MessengerError(ValueError):
    """All messenger-surface failures. Every refusal names its remedy
    (keeper's law)."""


def _check_keeper_id(value: object, what: str = "keeper_id") -> str:
    if not isinstance(value, str) or not KEEPER_ID_RE.match(value):
        raise MessengerError(
            "invalid %s %r: use 1-64 chars of [A-Za-z0-9._-]" % (what, value)
        )
    return value


class Messenger:
    """One keeper's Messenger endpoint.

    ``Messenger(passphrase, keeper_id, home=None, relay_host=...,
    relay_port=...)`` — ``keeper_id`` is this keeper's address on the
    relay and their member id in rooms. ``home`` is the test seam: the
    gate record, the VeilChat store, the RoomStore and the messenger
    state all root there (mirrors the plaiground convention);
    production passes nothing and the real owner record applies.

    The adult gate is re-checked on EVERY public call, so closing the
    gate mid-session locks the messenger immediately (M7).
    """

    def __init__(
        self,
        passphrase: str,
        keeper_id: str,
        home: Optional[Path] = None,
        relay_host: str = DEFAULT_HOST,
        relay_port: int = DEFAULT_PORT,
        relay_timeout: float = 10.0,
    ) -> None:
        require_adult(home)  # M7: FIRST, before any store is touched
        _check_keeper_id(keeper_id)
        self._gate_home = home
        self.keeper_id = keeper_id
        # M2/M3: the keeper's OWN crypto endpoints — never another's.
        self.chat = VeilChat(passphrase, home=home)
        self.rooms = RoomStore(passphrase, home=home)
        # M4: the relay is the ONLY transport.
        self.transport = MessengerTransport(
            host=relay_host, port=relay_port, timeout=relay_timeout, home=home
        )
        base = Path(home) if home is not None else Path.home()
        self._state_dir = base / ".levi" / "voidbox" / _MESSENGER_SUBDIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._state_dir, 0o700)
        self._state = self._load_state()
        # Packets that arrived before their room sync: deferred in memory
        # (never acked, so the relay keeps them) and retried next sweep.
        self._deferred: list[dict] = []
        # (sender, conv_id) of handshake offers already reported as
        # parked — reported once, then silently retried.
        self._parked: set[tuple[str, str]] = set()
        # Messages swept by poll_inbox but not yet collected by the
        # matching read_* call: held here (memory only) so read_dm never
        # swallows a group message and read_group never swallows a DM.
        self._unread_dms: list[dict] = []
        self._unread_groups: list[dict] = []

    # -- internal ----------------------------------------------------------

    def _require_adult(self) -> None:
        """M7: the gate is re-checked on every public call."""
        require_adult(self._gate_home)

    def _state_path(self) -> Path:
        return self._state_dir / _STATE_FILE

    def _load_state(self) -> dict:
        path = self._state_path()
        if not path.exists():
            return {"dms": {}, "groups": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise MessengerError("messenger state unreadable: %s" % exc) from exc
        if not isinstance(data, dict):
            raise MessengerError("messenger state corrupt")
        data.setdefault("dms", {})
        data.setdefault("groups", {})
        return data

    def _save_state(self) -> None:
        path = self._state_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)

    def _conv_for_peer(self, peer_id: str) -> str:
        """Resolve an established DM conversation for a peer. Fails
        closed with the remedy when the handshake isn't done."""
        _check_keeper_id(peer_id, "peer_id")
        entry = self._state["dms"].get(peer_id)
        if entry is None:
            raise MessengerError(
                "no DM with %r — start one first with start_dm(peer_id, "
                "public_key)" % (peer_id,)
            )
        if not entry.get("established"):
            raise MessengerError(
                "handshake with %r is not complete — poll your inbox "
                "(poll_inbox) so the handshake can finish, then retry"
                % (peer_id,)
            )
        live = {c["conv_id"] for c in self.chat.list_conversations()}
        if entry["conv_id"] not in live:
            raise MessengerError(
                "DM conversation with %r is gone locally — re-run "
                "start_dm(peer_id, public_key) to open a fresh one" % (peer_id,)
            )
        return entry["conv_id"]

    def _send_frame(self, peer_id: str, frame: dict) -> dict:
        """Seal a JSON frame through the 1:1 E2E channel and POST it."""
        conv_id = self._conv_for_peer(peer_id)
        blob = json.dumps(frame, sort_keys=True, separators=(",", ":")).encode("utf-8")
        envelope = self.chat.send_message(conv_id, blob)
        return self.transport.send_packet(
            peer_id,
            {"kind": "dm", "from": self.keeper_id, "envelope": envelope},
            sender=self.keeper_id,
        )

    def _sync_room(self, room_id: str) -> list[dict]:
        """Push fresh room state to every active member with an
        established DM. Returns the members that could NOT be synced
        (no DM yet) — the caller reports them, never silently drops
        them."""
        failed: list[dict] = []
        meta = self.rooms.get_room(room_id)
        for member_id, m in meta["members"].items():
            if member_id == self.keeper_id or not m["active"]:
                continue
            entry = self._state["dms"].get(member_id)
            if entry is None or not entry.get("established"):
                failed.append(
                    {
                        "member_id": member_id,
                        "reason": "no established DM — run start_dm and "
                        "complete the handshake, then re-invite/sync",
                    }
                )
                continue
            try:
                payload = export_room_state(
                    self.rooms, room_id, member_id, home=self._gate_home
                )
                self._send_frame(
                    member_id,
                    {
                        "type": "room-sync",
                        "room_id": room_id,
                        "payload": payload,
                        "sent_at": _utcnow(),
                    },
                )
            except (RoomSyncError, VeilChatError, MessengerError) as exc:
                failed.append({"member_id": member_id, "reason": str(exc)})
        return failed

    # -- identity ----------------------------------------------------------

    def my_identity(self) -> dict:
        """This keeper's public identity: keeper id, X25519 public key,
        and fingerprint for the out-of-band verification ceremony."""
        self._require_adult()
        ident = self.chat.identity()
        return {
            "keeper_id": self.keeper_id,
            "public_key": ident["public_key"],
            "fingerprint": ident["fingerprint"],
        }

    # -- 1:1 conversations ---------------------------------------------------

    def register_peer(self, peer_id: str, public_key: bytes, name: str = "") -> dict:
        """Register a peer's public key from the out-of-band exchange,
        WITHOUT starting a handshake — the recipient-side step. The key
        is never TOFU'd: it comes from the caller, not from the wire."""
        self._require_adult()
        _check_keeper_id(peer_id, "peer_id")
        if peer_id == self.keeper_id:
            raise MessengerError("cannot register yourself as a peer")
        if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
            raise MessengerError("peer public key must be 32 bytes")
        try:
            return self.chat.add_peer(peer_id, bytes(public_key), name)
        except VeilChatError as exc:
            raise MessengerError(str(exc)) from exc

    def start_dm(self, peer_id: str, public_key: bytes, name: str = "",
                 wait_seconds: float = 0.0) -> dict:
        """Open a DM: register the peer's public key (out-of-band
        exchange — never TOFU'd), run the X25519 handshake offer, and
        POST it to the peer's mailbox. The peer's messenger answers on
        its next poll; the handshake completes on ours after that.

        Single-process rule: ``veil_chat`` holds the handshake's
        ephemeral key in memory only, so the offer and the peer's
        answer must be handled by ONE Messenger lifetime. Pass
        ``wait_seconds > 0`` to sweep the inbox right here until the
        handshake is established or the timeout expires — this is how
        the CLI completes a handshake in a single invocation. With
        ``wait_seconds=0`` (default) the offer is just posted; call
        ``poll_inbox()`` later *in this same process* to finish it.

        Returns the DM status dict (``established`` True/False)."""
        self._require_adult()
        _check_keeper_id(peer_id, "peer_id")
        if peer_id == self.keeper_id:
            raise MessengerError("cannot DM yourself")
        if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
            raise MessengerError("peer public key must be 32 bytes")
        if wait_seconds < 0:
            raise MessengerError("wait_seconds must be >= 0")
        record = self.register_peer(peer_id, public_key, name)
        try:
            offer = self.chat.handshake_offer(peer_id)
        except VeilChatError as exc:
            raise MessengerError("handshake offer failed: %s" % exc) from exc
        self._state["dms"][peer_id] = {
            "conv_id": offer["conv_id"],
            "established": False,
        }
        self._save_state()
        self.transport.send_packet(
            peer_id,
            {"kind": "hs-offer", "from": self.keeper_id, "offer": offer},
            sender=self.keeper_id,
        )
        if wait_seconds > 0:
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                self.poll_inbox()
                if self.dm_status(peer_id)["established"]:
                    break
                time.sleep(0.5)
        status = self.dm_status(peer_id)
        return {
            "peer_id": peer_id,
            "conv_id": offer["conv_id"],
            "fingerprint": record["fingerprint"],
            "established": status["established"],
        }

    def dm_status(self, peer_id: str) -> dict:
        """DM state for a peer: registered, handshake done, live conv."""
        self._require_adult()
        _check_keeper_id(peer_id, "peer_id")
        try:
            peer = self.chat.get_peer(peer_id)
        except VeilChatError:
            return {"peer_id": peer_id, "registered": False, "established": False}
        entry = self._state["dms"].get(peer_id, {})
        live = {c["conv_id"] for c in self.chat.list_conversations()}
        return {
            "peer_id": peer_id,
            "registered": True,
            "fingerprint": peer["fingerprint"],
            "verified": bool(peer.get("verified")),
            "established": bool(entry.get("established"))
            and entry.get("conv_id") in live,
            "conv_id": entry.get("conv_id"),
        }

    def send_dm(self, peer_id: str, text: str) -> dict:
        """Seal a chat message through the 1:1 E2E channel and POST it
        to the peer's mailbox."""
        self._require_adult()
        if not isinstance(text, str) or not text.strip():
            raise MessengerError("message text must be non-empty")
        if len(text) > 65536:
            raise MessengerError("message text too long (max 65536 chars)")
        conv_id = self._conv_for_peer(peer_id)
        frame = {"type": "chat", "text": text, "sent_at": _utcnow()}
        blob = json.dumps(frame, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            envelope = self.chat.send_message(conv_id, blob)
        except VeilChatError as exc:
            raise MessengerError("sealing the DM failed: %s" % exc) from exc
        report = self.transport.send_packet(
            peer_id,
            {"kind": "dm", "from": self.keeper_id, "envelope": envelope},
            sender=self.keeper_id,
        )
        return {"peer_id": peer_id, "conv_id": conv_id, "relay": report}

    # -- group conversations -------------------------------------------------

    def create_group(self, name: str, public: bool = False) -> dict:
        """Create a group room. This keeper becomes admin and first
        member. Returns the room metadata."""
        self._require_adult()
        try:
            meta = self.rooms.create_room(name, self.keeper_id, public=public)
        except RoomError as exc:
            raise MessengerError(str(exc)) from exc
        self._state["groups"][meta["room_id"]] = {"name": meta["name"]}
        self._save_state()
        return meta

    def invite(self, room_id: str, peer_id: str) -> dict:
        """Admin invites a peer to a group: membership change re-keys
        the room (rooms L2), then fresh room state is pushed to every
        active member over their 1:1 E2E channel (M5). Members without
        an established DM are reported, not silently skipped."""
        self._require_adult()
        _check_keeper_id(peer_id, "peer_id")
        try:
            meta = self.rooms.add_member(room_id, peer_id, by_admin=self.keeper_id)
        except (RoomError, NotMemberError) as exc:
            raise MessengerError(str(exc)) from exc
        failed = self._sync_room(room_id)
        self._save_state()
        return {"room": meta, "sync_failed": failed}

    def remove(self, room_id: str, peer_id: str) -> dict:
        """Admin removes a member: re-keys immediately; the removed
        member's key copies stop at the removal epoch (rooms L3), so
        their reads stop. Remaining members get fresh state."""
        self._require_adult()
        _check_keeper_id(peer_id, "peer_id")
        try:
            meta = self.rooms.remove_member(room_id, peer_id, by_admin=self.keeper_id)
        except (RoomError, NotMemberError) as exc:
            raise MessengerError(str(exc)) from exc
        failed = self._sync_room(room_id)
        self._save_state()
        return {"room": meta, "sync_failed": failed}

    def leave_group(self, room_id: str) -> dict:
        """Leave a group yourself (admins can't — see the remedy).
        Re-keys; remaining members get fresh state."""
        self._require_adult()
        try:
            meta = self.rooms.leave_room(room_id, self.keeper_id)
        except (RoomError, NotMemberError) as exc:
            raise MessengerError(str(exc)) from exc
        failed = self._sync_room(room_id)
        self._state["groups"].pop(room_id, None)
        self._save_state()
        return {"room": meta, "sync_failed": failed}

    def send_group(self, room_id: str, text: str) -> dict:
        """Seal a group message under the room's current epoch key and
        POST it to every active member's mailbox (fan-out). Each member
        polls only their own mailbox, so per-member acks never delete
        another member's copy; dispatch is by the room id carried in
        the packet. Your own sends are not echoed back to you."""
        self._require_adult()
        if not isinstance(text, str) or not text.strip():
            raise MessengerError("message text must be non-empty")
        if len(text) > 65536:
            raise MessengerError("message text too long (max 65536 chars)")
        try:
            envelope = self.rooms.seal_message(room_id, self.keeper_id, text)
            meta = self.rooms.get_room(room_id)
        except (RoomError, NotMemberError) as exc:
            raise MessengerError(str(exc)) from exc
        packet = {
            "kind": "room-sealed",
            "room_id": room_id,
            "from": self.keeper_id,
            "envelope": envelope,
        }
        delivered, reports = [], []
        for member_id, m in meta["members"].items():
            if member_id == self.keeper_id or not m["active"]:
                continue
            reports.append(
                self.transport.send_packet(
                    member_id, packet, sender=self.keeper_id
                )
            )
            delivered.append(member_id)
        return {"room_id": room_id, "delivered_to": delivered, "relay": reports}

    # -- inbox: poll + dispatch ----------------------------------------------

    def poll_inbox(self, limit: int = 50) -> dict:
        """One inbox sweep: POLL our mailbox, dispatch by kind, ack what
        was handled. Returns ``{"dms", "groups", "events"}`` — new chat
        messages, new group messages, and a ledger of everything else
        (handshakes answered, room syncs applied, duplicates ignored,
        failures named)."""
        self._require_adult()
        dms: list[dict] = []
        groups: list[dict] = []
        events: list[dict] = []
        items = list(self._deferred)
        self._deferred = []
        items.extend(self.transport.fetch_packets(self.keeper_id, limit=limit))
        ack_ids: list[str] = []
        for item in items:
            packet = item["packet"]
            try:
                handled = self._dispatch_packet(item, dms, groups, events)
            except Exception as exc:  # one bad packet never wedges the inbox
                events.append(
                    {
                        "event": "packet-failed",
                        "kind": packet.get("kind"),
                        "from": item.get("from"),
                        "error": str(exc),
                    }
                )
                handled = True
            if handled:
                ack_ids.append(item["id"])
            else:
                # Not processable yet (room sync hasn't arrived) — defer
                # to the next sweep WITHOUT acking, so the relay keeps it.
                self._deferred.append(item)
        self.transport.ack(self.keeper_id, ack_ids)
        self._save_state()
        # Drain the hold buffers into this result: poll_inbox is the
        # complete primitive — nothing swept is ever left behind here.
        out = {
            "dms": self._unread_dms + dms,
            "groups": self._unread_groups + groups,
            "events": events,
        }
        self._unread_dms = []
        self._unread_groups = []
        return out

    def read_dm(self, peer_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Sweep the inbox and return new 1:1 chat messages, optionally
        filtered to one peer. Group messages swept along the way are
        NOT dropped — they're held for the next read_group/poll_inbox
        call (memory only; see poll_inbox). A peer_id filter is a VIEW,
        not a drain: messages from other peers are held (memory only)
        for the next matching read, because the sweep already acked
        them — dropping them here would lose them forever."""
        self._require_adult()
        if peer_id is not None:
            _check_keeper_id(peer_id, "peer_id")
        result = self.poll_inbox(limit=limit)
        self._unread_groups.extend(result["groups"])
        msgs = result["dms"]
        if peer_id is not None:
            self._unread_dms.extend(m for m in msgs if m["from"] != peer_id)
            msgs = [m for m in msgs if m["from"] == peer_id]
        return msgs

    def read_group(self, room_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Sweep the inbox and return new group messages, optionally
        filtered to one room. DM messages swept along the way are NOT
        dropped — they're held for the next read_dm/poll_inbox call
        (memory only; see poll_inbox). A room_id filter is a VIEW, not
        a drain: messages from other rooms are held (memory only) for
        the next matching read, because the sweep already acked them —
        dropping them here would lose them forever."""
        self._require_adult()
        result = self.poll_inbox(limit=limit)
        self._unread_dms.extend(result["dms"])
        msgs = result["groups"]
        if room_id is not None:
            self._unread_groups.extend(m for m in msgs if m["room_id"] != room_id)
            msgs = [m for m in msgs if m["room_id"] == room_id]
        return msgs

    # -- dispatch ------------------------------------------------------------

    def _dispatch_packet(self, item: dict, dms: list, groups: list, events: list) -> bool:
        """Dispatch one packet. Returns True when the packet was fully
        handled (safe to ack), False when it must be deferred without
        acking (room sync not yet arrived — the relay keeps it)."""
        packet = item["packet"]
        kind = packet.get("kind")
        sender = packet.get("from", "")
        if kind == "hs-offer":
            return self._on_hs_offer(packet["offer"], sender, events)
        elif kind == "hs-answer":
            self._on_hs_answer(packet["answer"], sender, events)
        elif kind == "dm":
            self._on_dm(item, dms, events)
        elif kind == "room-sealed":
            return self._on_room_sealed(item, groups, events)
        else:
            events.append(
                {"event": "unknown-packet-kind", "kind": kind, "from": sender}
            )
        return True

    def _on_hs_offer(self, offer: dict, sender: str, events: list) -> bool:
        """Answer a handshake offer. Unknown peer fingerprint: the key
        was never exchanged out of band, so the offer is PARKED —
        reported once, then deferred without acking (the relay keeps
        it) until the peer is registered via register_peer(), when the
        next sweep answers it. Never TOFU'd (NON_CLAIMS)."""
        try:
            answer = self.chat.handshake_answer(offer)
        except VeilChatError as exc:
            if "unknown peer fingerprint" in str(exc):
                key = (sender, str(offer.get("conv_id", "")))
                if key not in self._parked:
                    self._parked.add(key)
                    events.append(
                        {
                            "event": "hs-offer-parked",
                            "from": sender,
                            "error": str(exc),
                            "remedy": "exchange public keys out of band, "
                            "register the peer (register_peer / dm-add), "
                            "then sweep the inbox again — the parked offer "
                            "is retried, not dropped",
                        }
                    )
                return False  # defer: don't ack, retry next sweep
            events.append(
                {"event": "hs-offer-rejected", "from": sender, "error": str(exc)}
            )
            return True
        conv_id = answer["conv_id"]
        self._parked.discard((sender, conv_id))
        self._state["dms"][sender] = {"conv_id": conv_id, "established": True}
        self.transport.send_packet(
            sender,
            {"kind": "hs-answer", "from": self.keeper_id, "answer": answer},
            sender=self.keeper_id,
        )
        events.append(
            {"event": "hs-answered", "peer_id": sender, "conv_id": conv_id}
        )
        return True

    def _on_hs_answer(self, answer: dict, sender: str, events: list) -> None:
        try:
            conv_id = self.chat.handshake_finish(answer)
        except VeilChatError as exc:
            remedy = ""
            if "no pending handshake" in str(exc):
                # The offer was made by an older process lifetime; the
                # ephemeral handshake key is gone with it (veil_chat
                # keeps it in memory only). Re-run start_dm (dm-start)
                # to open a fresh offer — the stale answer is harmless.
                remedy = (
                    "the handshake offer came from an earlier process; "
                    "re-run start_dm (dm-start --wait) to open a fresh "
                    "offer in this process"
                )
            events.append(
                {"event": "hs-answer-rejected", "from": sender, "error": str(exc),
                 "remedy": remedy}
            )
            return
        self._state["dms"][sender] = {"conv_id": conv_id, "established": True}
        events.append(
            {"event": "hs-established", "peer_id": sender, "conv_id": conv_id}
        )

    def _on_dm(self, item: dict, dms: list, events: list) -> None:
        sender = item["packet"].get("from", "")
        envelope = item["packet"]["envelope"]
        try:
            opened = self.chat.receive_message(envelope)
        except VeilChatError as exc:
            events.append(
                {"event": "dm-rejected", "from": sender, "error": str(exc)}
            )
            return
        try:
            frame = json.loads(bytes(opened["plaintext"]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            events.append(
                {"event": "dm-bad-frame", "from": sender, "error": str(exc)}
            )
            return
        ftype = frame.get("type")
        if ftype == "chat":
            dms.append(
                {
                    "from": sender,
                    "text": frame.get("text", ""),
                    "sent_at": frame.get("sent_at"),
                    "seq": opened.get("seq"),
                }
            )
        elif ftype == "room-sync":
            try:
                applied = apply_room_state(
                    self.rooms, frame["payload"], self.keeper_id,
                    home=self._gate_home,
                )
            except RoomSyncError as exc:
                events.append(
                    {"event": "room-sync-rejected", "from": sender, "error": str(exc)}
                )
                return
            room_id = applied["room_id"]
            self._state["groups"][room_id] = {
                "name": frame["payload"].get("name", room_id)
            }
            events.append(
                {
                    "event": "room-synced",
                    "room_id": room_id,
                    "epoch": applied["epoch"],
                    "new_room": applied["new_room"],
                    "from": sender,
                }
            )
        else:
            events.append(
                {"event": "dm-unknown-frame", "from": sender, "type": ftype}
            )

    def _on_room_sealed(self, item: dict, groups: list, events: list) -> bool:
        """Open a fanned-out group envelope. Returns False (defer, don't
        ack) when the room sync hasn't arrived yet — the sender posts
        the sync before any message, so this only triggers on
        out-of-order delivery."""
        packet = item["packet"]
        room_id = packet.get("room_id", "")
        envelope = packet["envelope"]
        try:
            self.rooms.get_room(room_id)
        except (RoomError, ValueError):
            events.append(
                {
                    "event": "room-sealed-before-sync",
                    "room_id": room_id,
                    "from": packet.get("from", ""),
                    "remedy": "waiting for the room-sync packet — it is "
                    "deferred, not dropped",
                }
            )
            return False
        try:
            opened = self.rooms.open_message(room_id, self.keeper_id, envelope)
        except ReplayError as exc:
            # rooms L5: each member accepts an envelope at most once.
            events.append(
                {"event": "room-duplicate-ignored", "room_id": room_id,
                 "error": str(exc)}
            )
            return True
        except (EpochError, NotMemberError, RoomError) as exc:
            events.append(
                {"event": "room-open-failed", "room_id": room_id, "error": str(exc)}
            )
            return True
        try:
            text = bytes(opened["plaintext"]).decode("utf-8")
        except UnicodeDecodeError as exc:
            events.append(
                {"event": "room-bad-plaintext", "room_id": room_id, "error": str(exc)}
            )
            return True
        groups.append(
            {
                "room_id": room_id,
                "sender": opened["sender"],
                "text": text,
                "seq": opened["seq"],
                "key_epoch": opened["key_epoch"],
                "sent_at": opened.get("timestamp"),
            }
        )
        return True

    # -- lock discipline -------------------------------------------------------

    def lock(self) -> None:
        """Best-effort zeroize: lock both crypto endpoints."""
        self._require_adult()
        self.chat.lock()
        self.rooms.lock()

    def unlock(self, passphrase: str) -> None:
        """Re-derive both endpoints' keys after :meth:`lock`."""
        self._require_adult()
        self.chat.unlock(passphrase)
        self.rooms.unlock(passphrase)

    # -- reports ---------------------------------------------------------------

    def crypto_report(self) -> dict:
        """Honest posture: what this messenger is and is not."""
        self._require_adult()
        from levi.voidbox.messenger import LAWS, NON_CLAIMS

        return {
            "surface": "voidbox-messenger (standalone; Messenger vs platform)",
            "keeper_id": self.keeper_id,
            "gate_open": verify_adult(self._gate_home),
            "transport": "relay %s:%d (ciphertext-only store-and-forward)"
            % (self.transport.host, self.transport.port),
            "x25519": x25519_backend(),
            "dm_conversations": len(self.chat.list_conversations()),
            "peers": len(self._state["dms"]),
            "groups": len(self._state["groups"]),
            "non_claims": list(NON_CLAIMS),
            "laws": [lid for lid, _ in LAWS],
        }

    def verify_laws(self) -> list[tuple[str, bool, str]]:
        """Runtime law checks over this messenger's live state.

        Returns ``(law_id, holds, detail)`` per law — honestly named:
        machine-checked invariants, not proof.
        """
        self._require_adult()  # M7 applies to the law-check itself, first.
        from levi.voidbox.messenger import LAWS

        results: list[tuple[str, bool, str]] = []

        def check(law: str, ok: bool, detail: str = "") -> None:
            results.append((law, ok, detail))

        import inspect as _inspect
        import pathlib as _pl

        pkg = _pl.Path(__file__).parent
        sources = {
            p.name: p.read_text(encoding="utf-8")
            for p in (pkg / "__init__.py", pkg / "app.py",
                      pkg / "client.py", pkg / "roomsync.py")
            if p.exists()
        }

        # M1: separate surface — no platform imports. Allowed: the crypto
        # primitives, the relay transport, the gate, and this package.
        allowed = (
            "levi.cybrus.veil",
            "levi.cybrus.veil_chat",
            "levi.voidbox.rooms",
            "levi.voidbox.relay",
            "levi.voidbox.messenger",
            "levi.plaiground.gate",
        )
        bad_imports = []
        for name, src in sources.items():
            for line in src.splitlines():
                s = line.strip()
                if s.startswith("from levi.") or s.startswith("import levi."):
                    mod = s.split()[1].split(" as ")[0].rstrip(",")
                    if not mod.startswith(allowed):
                        bad_imports.append("%s: %s" % (name, s))
        check("M1", not bad_imports,
              "; ".join(bad_imports) if bad_imports else "no platform imports")

        # M2/M3: the crypto endpoints are the keeper's own — one VeilChat,
        # one RoomStore, built from the keeper's own passphrase.
        check("M2", isinstance(self.chat, VeilChat), type(self.chat).__name__)
        check("M3", isinstance(self.rooms, RoomStore), type(self.rooms).__name__)

        # M4: the relay is the only transport.
        check("M4", isinstance(self.transport, MessengerTransport),
              "MessengerTransport -> %s:%d"
              % (self.transport.host, self.transport.port))

        # M5: room-sync re-wraps under the RECIPIENT's own keys —
        # structural: roomsync seals copies under _member_wrap_key(member_id).
        check("M5", "_member_wrap_key(member_id)" in sources.get("roomsync.py", ""),
              "copies wrapped under the recipient's own member key")

        # M6: opens go through the keeper's own endpoints only.
        check("M6",
              "self.chat.receive_message(" in sources.get("app.py", "")
              and "self.rooms.open_message(room_id, self.keeper_id" in sources.get("app.py", ""),
              "opens only via own chat / own room membership")

        # M7: every public method of Messenger re-checks the gate FIRST —
        # the gate call must precede any other self-call in the method
        # body (order, not just presence).
        public = [
            name for name in dir(Messenger)
            if not name.startswith("_") and callable(getattr(Messenger, name))
        ]
        missing, misordered = [], []
        for name in public:
            fn_src = _inspect.getsource(getattr(Messenger, name))
            lines = fn_src.splitlines()[1:]  # skip the def line
            gate_line = next(
                (i for i, ln in enumerate(lines) if "require_adult(" in ln),
                None,
            )
            if gate_line is None:
                missing.append(name)
                continue
            other_call = next(
                (i for i, ln in enumerate(lines)
                 if re.search(r"self\.[A-Za-z_][A-Za-z0-9_]*\s*\(", ln)
                 and "_require_adult" not in ln),
                None,
            )
            if other_call is not None and other_call < gate_line:
                misordered.append(name)
        detail_parts = []
        if missing:
            detail_parts.append("gate missing in: " + ", ".join(missing))
        if misordered:
            detail_parts.append("gate not first in: " + ", ".join(misordered))
        check("M7", not missing and not misordered,
              "; ".join(detail_parts) if detail_parts
              else "%d public methods all call the gate first" % len(public))

        # M7 (cont.): the transport's public surface and the room-sync
        # helpers are public entry points too — gate first there as well.
        from levi.voidbox.messenger import roomsync as _roomsync_mod

        t_problems = []
        for mname in ("__init__", "send_packet", "fetch_packets",
                      "malformed_count", "ack", "ping"):
            fn = getattr(MessengerTransport, mname)
            lines = _inspect.getsource(fn).splitlines()[1:]
            gl = next(
                (i for i, ln in enumerate(lines) if "require_adult(" in ln),
                None,
            )
            if gl is None:
                t_problems.append("MessengerTransport.%s: no gate" % mname)
                continue
            oc = next(
                (i for i, ln in enumerate(lines)
                 if (re.search(r"self\.[A-Za-z_][A-Za-z0-9_]*\s*\(", ln)
                     or "RelayClient(" in ln)
                 and "_require_adult" not in ln),
                None,
            )
            if oc is not None and oc < gl:
                t_problems.append(
                    "MessengerTransport.%s: gate not first" % mname)
        for fname in ("export_room_state", "apply_room_state"):
            fn_src = _inspect.getsource(getattr(_roomsync_mod, fname))
            gl = fn_src.find("require_adult(")
            st = fn_src.find("store.")
            if gl == -1:
                t_problems.append("roomsync.%s: no gate" % fname)
            elif st != -1 and st < gl:
                t_problems.append("roomsync.%s: gate not first" % fname)
        check("M7-transport-sync", not t_problems,
              "; ".join(t_problems) if t_problems
              else "transport + room-sync helpers all call the gate first")

        # M8: honest addressing is named in NON_CLAIMS.
        from levi.voidbox.messenger import NON_CLAIMS

        check("M8", any("plaintext" in c and "ids" in c for c in NON_CLAIMS),
              "addressing metadata named as visible to the relay operator")

        # LAWS tuple complete and well-formed.
        ids = [lid for lid, _ in LAWS]
        check("laws-complete", ids == ["M%d" % i for i in range(1, 9)],
              "LAWS has M1..M8 in order")
        return results
