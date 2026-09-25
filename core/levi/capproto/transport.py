"""Local transport for capproto/1: AF_UNIX sockets, loopback-TCP fallback.

No network beyond this machine, ever. The primary transport is an
AF_UNIX socket at ``<home>/sockets/<name>.sock`` (owner-only dir, 0700).
Where AF_UNIX is unavailable, the transport falls back to TCP on
127.0.0.1 with an ephemeral port recorded in ``<home>/sockets/<name>.port``.

Wire framing: newline-delimited UTF-8 JSON (see :mod:`levi.capproto.protocol`).

Shared-secret note: capability tokens are HMAC'd with the telescript
secret. A server and its clients must share ``LEVI_TELESCRIPT_SECRET``;
without it, each process uses a per-process secret and its tokens verify
only in-process. This is documented, not hidden.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from levi.revival.telescript import CapabilityError

from .protocol import (
    ProtocolError,
    ServiceSpec,
    error_response,
    ok_response,
    validate_message,
)

__all__ = [
    "TransportError",
    "socket_dir",
    "CapServer",
    "CapClient",
]

BACKLOG = 8
RECV_CHUNK = 65536


class TransportError(Exception):
    """The local transport failed (bind, connect, framing)."""


def socket_dir(home: Optional[Path] = None) -> Path:
    from .tokens import default_home

    d = (Path(home) if home else default_home()) / "sockets"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


class CapServer:
    """Serve a ServiceSpec on a local socket. Deny-closed per call."""

    def __init__(
        self, spec: ServiceSpec, home: Optional[Path] = None, name: Optional[str] = None
    ):
        self.spec = spec
        self.name = name or spec.name
        self.sockets_dir = socket_dir(home)
        self.sock_path = self.sockets_dir / f"{self.name}.sock"
        self.port_file = self.sockets_dir / f"{self.name}.port"
        self._listener: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.mode = "unix"  # or "tcp"

    # -- lifecycle ------------------------------------------------------
    def start(self) -> "CapServer":
        if self._listener is not None:
            return self
        try:
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                self.sock_path.unlink()
            except FileNotFoundError:
                pass
            self._listener.bind(str(self.sock_path))
            try:
                os.chmod(self.sock_path, 0o600)
            except OSError:
                pass
        except (OSError, AttributeError):
            # AF_UNIX unavailable: loopback TCP fallback.
            self.mode = "tcp"
            if self._listener is not None:
                self._listener.close()
            self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", 0))
            port = self._listener.getsockname()[1]
            self.port_file.write_text(str(port), encoding="utf-8")
            try:
                os.chmod(self.port_file, 0o600)
            except OSError:
                pass
        self._listener.listen(BACKLOG)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._accept_loop, name=f"capproto-{self.name}", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        for stale in (self.sock_path, self.port_file):
            try:
                stale.unlink()
            except FileNotFoundError:
                pass

    @property
    def endpoint(self) -> str:
        if self.mode == "unix":
            return f"unix:{self.sock_path}"
        return f"tcp:127.0.0.1:{self.port_file.read_text(encoding='utf-8').strip()}"

    # -- serving ---------------------------------------------------------
    def _accept_loop(self) -> None:
        assert self._listener is not None
        self._listener.settimeout(0.25)
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except (socket.timeout, OSError):
                continue
            threading.Thread(target=self._serve_conn, args=(conn,), daemon=True).start()

    def _serve_conn(self, conn: socket.socket) -> None:
        from .protocol import MAX_LINE_BYTES

        buf = b""
        try:
            with conn:
                while not self._stop.is_set():
                    chunk = conn.recv(RECV_CHUNK)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if len(line) > MAX_LINE_BYTES:
                            self._send(
                                conn, error_response("?", "protocol", "line too long")
                            )
                            return
                        if line.strip():
                            self._handle_line(conn, line)
        except OSError:
            pass

    def _send(self, conn: socket.socket, msg: Dict[str, Any]) -> None:
        try:
            conn.sendall(
                (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
            )
        except OSError:
            pass

    def _handle_line(self, conn: socket.socket, line: bytes) -> None:
        try:
            raw = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self._send(conn, error_response("?", "protocol", f"not JSON: {exc}"))
            return
        try:
            msg = validate_message(raw)
        except ProtocolError as exc:
            mid = raw.get("id") if isinstance(raw, dict) else "?"
            self._send(conn, error_response(str(mid), "protocol", str(exc)))
            return
        op = msg["op"]
        mid = msg["id"]
        if op == "hello":
            self._send(conn, ok_response(mid, {"service": self.spec.describe()}))
        elif op == "bye":
            self._send(conn, ok_response(mid, {"bye": True}))
        elif op == "revoke":
            try:
                self.spec.revoke_token(msg["token"])
                self._send(conn, ok_response(mid, {"revoked": True}))
            except CapabilityError as exc:
                self._send(conn, error_response(mid, "auth", str(exc)))
        elif op == "call":
            self._handle_call(conn, msg)

    def _handle_call(self, conn: socket.socket, msg: Dict[str, Any]) -> None:
        mid = msg["id"]
        if msg["svc"] != self.spec.name:
            self._send(
                conn,
                error_response(
                    mid, "protocol", f"this endpoint serves {self.spec.name!r}"
                ),
            )
            return
        try:
            result = self.spec.dispatch(
                msg["verb"], msg["token"], msg.get("args") or {}
            )
            self._send(conn, ok_response(mid, result))
        except ProtocolError as exc:
            text = str(exc)
            etype = "unknown_verb" if text.startswith("unknown_verb") else "bad_args"
            self._send(conn, error_response(mid, etype, text))
        except CapabilityError as exc:
            from levi.revival.telescript import ActionRefused

            etype = "refused" if isinstance(exc, ActionRefused) else "auth"
            self._send(conn, error_response(mid, etype, str(exc)))
        except Exception as exc:  # verb implementation error: named, not leaked
            self._send(
                conn, error_response(mid, "server", f"{type(exc).__name__}: {exc}")
            )


class CapClient:
    """Client for a local capproto/1 endpoint."""

    def __init__(self, home: Optional[Path] = None, name: str = ""):
        if not name:
            raise ValueError("CapClient: name must be a non-empty string")
        self.name = name
        self.sockets_dir = socket_dir(home)
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._seq = 0

    def connect(self) -> "CapClient":
        sock_path = self.sockets_dir / f"{self.name}.sock"
        port_file = self.sockets_dir / f"{self.name}.port"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            if sock_path.exists():
                s.connect(str(sock_path))
            elif port_file.exists():
                s.close()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(
                    ("127.0.0.1", int(port_file.read_text(encoding="utf-8").strip()))
                )
            else:
                s.close()
                raise TransportError(
                    f"no capproto endpoint for {self.name!r} "
                    f"(looked for {sock_path.name} / {port_file.name})"
                )
        except OSError as exc:
            try:
                s.close()
            except OSError:
                pass
            raise TransportError(f"connect to {self.name!r} failed: {exc}") from exc
        self._sock = s
        self._rfile = s.makefile("r", encoding="utf-8")
        return self

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None

    def _request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        if self._sock is None:
            raise TransportError("client is not connected")
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            try:
                self._sock.sendall(data)
                line = self._rfile.readline()
            except OSError as exc:
                raise TransportError(f"request failed: {exc}") from exc
        if not line:
            raise TransportError("server closed the connection")
        try:
            resp = json.loads(line)
        except ValueError as exc:
            raise TransportError(f"server sent non-JSON: {exc}") from exc
        if not isinstance(resp, dict) or resp.get("id") != msg["id"]:
            raise TransportError("server response mismatched request id")
        return resp

    def call(
        self, svc: str, verb: str, token: str, args: Optional[Dict[str, Any]] = None
    ) -> Any:
        from .protocol import msg_call

        self._seq += 1
        resp = self._request(msg_call(svc, verb, token, args, msg_id=f"c{self._seq}"))
        if resp.get("ok"):
            return resp.get("result")
        raise CapCallError(resp.get("error_type", "server"), resp.get("error", "?"))

    def hello(self, agent: str = "capproto-client") -> Dict[str, Any]:
        from .protocol import msg_hello

        resp = self._request(msg_hello(agent))
        if resp.get("ok"):
            return resp.get("result", {})
        raise CapCallError(resp.get("error_type", "server"), resp.get("error", "?"))

    def revoke(self, token: str) -> None:
        from .protocol import msg_revoke

        resp = self._request(msg_revoke(token))
        if not resp.get("ok"):
            raise CapCallError(resp.get("error_type", "server"), resp.get("error", "?"))


class CapCallError(Exception):
    """A remote call returned ok=false."""

    def __init__(self, error_type: str, message: str):
        super().__init__(f"[{error_type}] {message}")
        self.error_type = error_type
