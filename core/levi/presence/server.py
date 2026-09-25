"""TCP hub: speaks newline-delimited JSON, fans room events out to members.

Protocol (client -> server), one JSON object per line:
    {"op":"hello","name":"Chauncey"}          -> {"ok":true,"client_id":...}
    {"op":"rooms"}                             -> {"ok":true,"rooms":[...]}
    {"op":"create","room":"lounge","topic":""}
    {"op":"join","room":"lounge"}
    {"op":"leave","room":"lounge"}
    {"op":"say","room":"lounge","text":"hi"}
    {"op":"who","room":"lounge"}               -> presence list
    {"op":"heartbeat"}                         -> {"ok":true}

Server -> client pushes (same framing):
    {"event":"message","room":..,"from":..,"text":..,"at":..}
    {"event":"presence","room":..,"name":..,"state":"joined|left|timeout",...}
"""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from typing import Dict, Optional

from levi.presence.rooms import RoomBook, new_id


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:  # noqa: D102 (socketserver contract)
        hub: "PresenceHub" = self.server.hub  # type: ignore[attr-defined]
        client_id: Optional[str] = None
        try:
            for raw in self.rfile:
                try:
                    req = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    self._send({"ok": False, "error": "not JSON"})
                    continue
                if not isinstance(req, dict):
                    self._send({"ok": False, "error": "object per line"})
                    continue
                client_id = hub.dispatch(self, client_id, req)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            if client_id:
                hub.client_gone(self, client_id)

    def _send(self, obj: Dict) -> None:
        try:
            self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


class _ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


class PresenceHub:
    """A drop-in room hub: no accounts, no auth, LAN-reachable."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.book = RoomBook()
        self._conns: Dict[str, _Handler] = {}
        self._conn_lock = threading.Lock()
        self._server = _ThreadedServer((host, port), _Handler)
        self._server.hub = self  # type: ignore[attr-defined]
        self._thread: Optional[threading.Thread] = None

    @property
    def address(self):
        return self._server.server_address

    def start(self) -> "PresenceHub":
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="presence-hub", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    # -- connection registry -------------------------------------------------
    def _attach(self, handler: _Handler, client_id: str) -> None:
        with self._conn_lock:
            self._conns[client_id] = handler

    def _push(self, client_id: str, obj: Dict) -> None:
        with self._conn_lock:
            handler = self._conns.get(client_id)
        if handler is not None:
            handler._send(obj)

    def _fanout(self, obj: Dict, recipients) -> None:
        for cid in recipients:
            self._push(cid, obj)

    def client_gone(self, handler: _Handler, client_id: str) -> None:
        with self._conn_lock:
            # Stale-close guard: a client may re-attach on a newer connection
            # (the CLI's hello handshake opens a second connection). If this
            # closing connection is no longer the attached one, its teardown
            # must not evict the live client — otherwise a late FIN from the
            # first connection deletes a client that just re-registered.
            if self._conns.get(client_id) is not handler:
                return
            self._conns.pop(client_id, None)
        for event, recipients in self.book.disconnect(client_id):
            self._fanout(event, recipients)

    def sweep(self, idle_seconds: float = 180.0) -> None:
        for event, recipients in self.book.sweep(idle_seconds):
            self._fanout(event, recipients)

    # -- protocol --------------------------------------------------------------
    def dispatch(
        self, handler: _Handler, client_id: Optional[str], req: Dict
    ) -> Optional[str]:
        op = req.get("op")
        if op == "hello":
            cid = self.book.register(
                req.get("name", "anonymous"), req.get("client_id") or new_id()
            )
            self._attach(handler, cid)
            handler._send(
                {"ok": True, "client_id": cid, "name": self.book.name_of(cid)}
            )
            return cid
        if client_id is None:
            handler._send({"ok": False, "error": "send hello first"})
            return None
        if op == "rooms":
            handler._send({"ok": True, "rooms": self.book.list_rooms()})
        elif op == "create":
            ok, msg = self.book.create_room(req.get("room", ""), req.get("topic", ""))
            handler._send(
                {"ok": ok, **({"room": req.get("room")} if ok else {"error": msg})}
            )
        elif op == "join":
            ok, payload = self.book.join(client_id, req.get("room", ""))
            if ok:
                event, recipients = payload
                handler._send({"ok": True, "room": req.get("room")})
                self._fanout(event, recipients)
            else:
                handler._send({"ok": False, "error": payload})
        elif op == "leave":
            ok, payload = self.book.leave(client_id, req.get("room", ""))
            if ok:
                event, recipients = payload
                handler._send({"ok": True, "room": req.get("room")})
                self._fanout(event, recipients)
            else:
                handler._send({"ok": False, "error": payload})
        elif op == "say":
            ok, payload = self.book.post(
                client_id, req.get("room", ""), req.get("text", "")
            )
            if ok:
                message, recipients = payload
                handler._send({"ok": True, "at": message["at"]})
                self._fanout(message, recipients)
            else:
                handler._send({"ok": False, "error": payload})
        elif op == "who":
            ok, members = self.book.room_members(req.get("room", ""))
            handler._send(
                {
                    "ok": ok,
                    **({"members": members} if ok else {"error": "no such room"}),
                }
            )
        elif op == "heartbeat":
            self.book.heartbeat(client_id)
            handler._send({"ok": True})
        else:
            handler._send({"ok": False, "error": "unknown op %r" % (op,)})
        return client_id


def send_request(host: str, port: int, obj: Dict, timeout: float = 5.0) -> Dict:
    """One-shot request/response helper used by the CLI."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n", 1)[0]
        return json.loads(line.decode("utf-8")) if line else {}
