"""MCP transports for LEVI (LEVI-original, stdlib-only).

* ``serve_stdio`` — newline-delimited JSON-RPC on stdin/stdout, the
  standard pattern MCP clients (Claude Desktop, editors, agents) use to
  spawn a local server. No Content-Length framing.
* ``serve_http`` — Streamable-HTTP-style JSON-RPC:

  - ``POST /mcp`` — JSON-RPC request (single or batch), no session needed
  - ``GET /sse`` — opens a session per the MCP 2024-11-05 SSE handshake:
    the server replies with an ``endpoint`` event naming
    ``/message?sessionId=<id>``; the client then POSTs JSON-RPC there.
    The stream stays open with keep-alive comments; LEVI currently
    sends no spontaneous server→client notifications (documented).

  HTTP binds to 127.0.0.1 by default. ``--token`` enables optional
  Bearer auth (401 JSON when missing/wrong); without it, anyone who can
  reach the port can call the (restricted) tools — keep it on
  localhost or behind your own TLS terminator.
"""

from __future__ import annotations

import hmac
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, BinaryIO, TextIO
from urllib.parse import urlparse, parse_qs

from levi.mcp.protocol import MCPServer, error_response


# ---------------------------------------------------------------------------
# stdio
# ---------------------------------------------------------------------------


def serve_stdio(
    server: MCPServer,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run the MCP server on stdio until stdin closes."""
    inp = stdin or sys.stdin.buffer
    out = stdout or sys.stdout
    for raw in inp:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            _write(out, error_response(None, -32700, "parse error"))
            continue
        response = server.handle(message)
        if response is not None:
            _write(out, response)


def _write(out: TextIO, response: Any) -> None:
    out.write(json.dumps(response) + "\n")
    out.flush()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class _MCPHTTPState:
    """Shared mutable state for one HTTP server instance."""

    def __init__(self, server: MCPServer, token: str = "") -> None:
        self.server = server
        self.token = token
        self.sessions: dict[str, float] = {}
        self.lock = threading.Lock()

    def new_session(self) -> str:
        sid = secrets.token_urlsafe(16)
        with self.lock:
            self.sessions[sid] = time.time()
        return sid

    def valid_session(self, sid: str) -> bool:
        with self.lock:
            return sid in self.sessions

    def check_auth(self, headers: Any) -> bool:
        if not self.token:
            return True
        auth = headers.get("Authorization", "")
        scheme, _, value = auth.partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            value, self.token
        )


class _Handler(BaseHTTPRequestHandler):
    state: _MCPHTTPState  # set on the class by serve_http

    # -- helpers ------------------------------------------------------

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _unauthorized(self) -> None:
        self._send_json(401, {"error": "unauthorized"})

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw.decode("utf-8")) if raw else None

    def log_message(self, *args: Any) -> None:  # quieter than default
        pass

    # -- routes --------------------------------------------------------

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/message":
            qs = parse_qs(parsed.query)
            sid = (qs.get("sessionId") or [""])[0]
            if not self.state.valid_session(sid):
                self._send_json(400, {"error": "unknown session"})
                return
            self._handle_rpc()
        elif parsed.path == "/mcp":
            self._handle_rpc()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_rpc(self) -> None:
        if not self.state.check_auth(self.headers):
            self._unauthorized()
            return
        try:
            message = self._read_json()
        except ValueError:
            self._send_json(200, error_response(None, -32700, "parse error"))
            return
        if message is None:
            self._send_json(400, {"error": "empty body"})
            return
        response = self.state.server.handle(message)
        # A bare notification over HTTP has no response; acknowledge it.
        self._send_json(200, response if response is not None else {"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json(200, {"ok": True, "server": "levi-mcp"})
            return
        if parsed.path != "/sse":
            self._send_json(404, {"error": "not found"})
            return
        if not self.state.check_auth(self.headers):
            self._unauthorized()
            return
        sid = self.state.new_session()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(f"event: endpoint\ndata: /message?sessionId={sid}\n\n".encode())
            self.wfile.flush()
            # Keep the stream open; LEVI sends no spontaneous
            # notifications today, so this is keep-alive only.
            while True:
                time.sleep(15)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def serve_http(
    server: MCPServer,
    *,
    host: str = "127.0.0.1",
    port: int = 8899,
    token: str = "",
) -> None:
    """Serve MCP over HTTP/SSE until interrupted."""
    _Handler.state = _MCPHTTPState(server, token)
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"levi-mcp http on http://{host}:{port} (POST /mcp, GET /sse)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
