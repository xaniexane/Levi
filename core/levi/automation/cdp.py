"""LEVI CDP session manager — recovery state machine + HITL, stdlib only.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.
The ``websockets`` third-party dependency is replaced with a minimal
stdlib-only RFC 6455 client written below (asyncio + socket + hashlib).

Binding boundaries (see docs/AUTOMATION_SAFETY.md):
- Loopback only: the CDP host must be 127.0.0.1, ::1, or localhost.
  Anything else raises immediately.
- No credential or cookie persistence: session state files carry only
  non-sensitive metadata (target id, timestamps). Nothing auth-shaped
  is ever written.
- Login / captcha / 2FA / payment paths force HITL via the flag-file
  pattern; they never auto-continue.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Minimal stdlib RFC 6455 websocket client (asyncio)
# ---------------------------------------------------------------------------

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA


class WebSocketError(Exception):
    """Transport-level websocket failure."""


def _accept_key(key: str) -> str:
    digest = hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


class WSConnection:
    """A minimal asyncio RFC 6455 client connection (already handshaked)."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self.closed = False

    async def send_text(self, text: str) -> None:
        await self._send_frame(_OP_TEXT, text.encode("utf-8"))

    async def ping(self) -> None:
        await self._send_frame(_OP_PING, b"")

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise WebSocketError("connection closed")
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        head = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + n.to_bytes(2, "big")
        else:
            head += bytes([0x80 | 127]) + n.to_bytes(8, "big")
        self._writer.write(head + mask_key + masked)
        await self._writer.drain()

    async def _read_exact(self, n: int) -> bytes:
        data = await self._reader.readexactly(n)
        if len(data) != n:
            raise WebSocketError("short read")
        return data

    async def _read_frame(self) -> tuple:
        b1, b2 = await self._read_exact(2)
        opcode = b1 & 0x0F
        masked = bool(b2 & 0x80)
        length = b2 & 0x7F
        if length == 126:
            length = int.from_bytes(await self._read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(await self._read_exact(8), "big")
        mask_key = await self._read_exact(4) if masked else b""
        payload = await self._read_exact(length) if length else b""
        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    async def recv_text(self) -> Optional[str]:
        """Next text message, or None on clean close."""
        chunks: List[bytes] = []
        while True:
            opcode, payload = await self._read_frame()
            if opcode == _OP_CLOSE:
                self.closed = True
                return None
            if opcode == _OP_PING:
                await self._send_frame(_OP_PONG, payload)
                continue
            if opcode == _OP_PONG:
                continue
            if opcode == _OP_TEXT:
                chunks.append(payload)
                return b"".join(chunks).decode("utf-8", errors="replace")
            if opcode == _OP_BINARY:
                chunks.append(payload)
                continue
            # continuation (0x0) falls through to accumulation; unknown → skip
            if opcode == 0x0 and chunks:
                chunks.append(payload)

    async def close(self) -> None:
        if not self.closed:
            try:
                await self._send_frame(_OP_CLOSE, b"")
            except (OSError, WebSocketError):
                pass
            self.closed = True
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except (OSError, RuntimeError):
            pass


async def ws_connect(host: str, port: int, path: str = "/") -> WSConnection:
    """Open a websocket to ``host:port``. Loopback hosts only."""
    _require_loopback(host)
    reader, writer = await asyncio.open_connection(host, port)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    writer.write(request.encode("ascii"))
    await writer.drain()
    header = b""
    while b"\r\n\r\n" not in header:
        chunk = await reader.read(1024)
        if not chunk:
            writer.close()
            raise WebSocketError("handshake: connection closed")
        header += chunk
        if len(header) > 16384:
            writer.close()
            raise WebSocketError("handshake: header too large")
    head_text = header.split(b"\r\n\r\n", 1)[0].decode("latin1")
    lines = head_text.split("\r\n")
    if not lines[0].startswith("HTTP/1.1 101"):
        writer.close()
        raise WebSocketError(f"handshake rejected: {lines[0]}")
    accept = ""
    for line in lines[1:]:
        if line.lower().startswith("sec-websocket-accept:"):
            accept = line.split(":", 1)[1].strip()
    if accept != _accept_key(key):
        writer.close()
        raise WebSocketError("handshake: bad Sec-WebSocket-Accept")
    return WSConnection(reader, writer)


# ---------------------------------------------------------------------------
# Session state machine + error taxonomy
# ---------------------------------------------------------------------------


class SessionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECOVERING = "recovering"
    HITL_PAUSED = "hitl_paused"
    FAILED = "failed"


class ErrorClass(Enum):
    TRANSIENT = "transient"
    SESSION_LOST = "session_lost"
    TIMEOUT = "timeout"
    CAPTCHA_OR_AUTH = "captcha_or_auth"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


_AUTH_HINTS = ("captcha", "login", "auth", "2fa", "challenge", "verify-you-are-human")


def classify_error(exc: BaseException) -> ErrorClass:
    """Classify an exception into the CDP error taxonomy."""
    if isinstance(exc, asyncio.TimeoutError) or isinstance(exc, TimeoutError):
        return ErrorClass.TIMEOUT
    text = str(exc).lower()
    if any(h in text for h in _AUTH_HINTS):
        return ErrorClass.CAPTCHA_OR_AUTH
    if isinstance(exc, (ConnectionError, WebSocketError)):
        return ErrorClass.SESSION_LOST
    if "protocol" in text or "handshake" in text:
        return ErrorClass.PROTOCOL
    return ErrorClass.UNKNOWN


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _require_loopback(host: str) -> None:
    if str(host or "").lower() not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"CDP host must be loopback (127.0.0.1/::1/localhost), got {host!r}"
        )


@dataclass
class CDPConfig:
    host: str = "127.0.0.1"
    port: int = 9222
    target_id: Optional[str] = None
    max_retries: int = 5
    base_backoff_sec: float = 1.0
    max_backoff_sec: float = 30.0
    command_timeout_sec: float = 15.0
    hitl_timeout_sec: float = 300.0
    state_file: Path = field(
        default_factory=lambda: Path.home() / ".levi" / "cdp" / "session.json"
    )

    def validate(self) -> None:
        _require_loopback(self.host)
        if not 1 <= int(self.port) <= 65535:
            raise ValueError(f"bad CDP port {self.port!r}")


@dataclass
class RecoveryResult:
    success: bool
    new_ws_url: Optional[str] = None
    message: str = ""
    required_hitl: bool = False


# ---------------------------------------------------------------------------
# HITL flag-file pattern
# ---------------------------------------------------------------------------


class HITLFlag:
    """Human-in-the-loop via flag file.

    ``request`` writes a message file and polls for the flag file; the
    human answers by writing one of the offered options into it. Nothing
    auto-continues: on timeout the answer is ``"timeout"`` and the caller
    must treat it as *not approved*.
    """

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.flag_file = self.state_dir / "hitl_continue.flag"
        self.message_file = self.state_dir / "hitl_message.txt"

    async def request(
        self,
        title: str,
        body: str,
        options: Optional[List[str]] = None,
        timeout_sec: float = 300.0,
    ) -> str:
        options = options or ["continue", "abort", "retry"]
        self.message_file.write_text(
            f"{title}\n\n{body}\n\nOptions: {options}", encoding="utf-8"
        )
        if self.flag_file.exists():
            self.flag_file.unlink()
        print("\n" + "=" * 60)
        print(f"HITL REQUIRED: {title}\n{body}\nOptions: {options}")
        print(f"Write your choice into: {self.flag_file}")
        print("=" * 60)
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if self.flag_file.exists():
                choice = self.flag_file.read_text(encoding="utf-8").strip().lower()
                try:
                    self.flag_file.unlink()
                except OSError:
                    pass
                return choice if choice in options else options[0]
            await asyncio.sleep(1.0)
        return "timeout"

    def clear(self) -> None:
        for f in (self.flag_file, self.message_file):
            try:
                f.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CDP session
# ---------------------------------------------------------------------------


class CDPSession:
    """CDP session with recovery state machine and HITL error handling.

    Attaches to a *user-owned* Chromium exposing the DevTools protocol on
    loopback. Drives pages via CDP; any auth/captcha-shaped failure pauses
    for a human. No credentials or cookies are persisted — ever.
    """

    def __init__(self, config: Optional[CDPConfig] = None) -> None:
        self.config = config or CDPConfig()
        self.config.validate()
        self.state = SessionState.DISCONNECTED
        self.ws: Optional[WSConnection] = None
        self.session_id: Optional[str] = None
        self.message_id = 0
        self.pending: Dict[int, asyncio.Future] = {}
        self.hitl = HITLFlag(self.config.state_file.parent)
        self._listen_task: Optional[asyncio.Task] = None

    # -- DevTools HTTP endpoints (no auth; protocol metadata only) ---------

    def _http_json(self, path: str) -> Any:
        url = f"http://{self.config.host}:{self.config.port}{path}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _pick_ws_url(self) -> str:
        targets = self._http_json("/json/list")
        pages = [
            t
            for t in targets
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
        ]
        if pages:
            if self.config.target_id:
                for t in pages:
                    if t.get("id") == self.config.target_id:
                        return t["webSocketDebuggerUrl"]
            return pages[0]["webSocketDebuggerUrl"]
        return self._http_json("/json/version")["webSocketDebuggerUrl"]

    @staticmethod
    def _ws_parts(ws_url: str) -> tuple:
        # ws://127.0.0.1:9222/devtools/page/ABC
        rest = ws_url.split("://", 1)[1]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        return host, int(port or 80), "/" + path

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        self.state = SessionState.CONNECTING
        try:
            ws_url = self._pick_ws_url()
            host, port, path = self._ws_parts(ws_url)
            self.ws = await ws_connect(host, port, path)
            self.state = SessionState.CONNECTED
            self.session_id = str(uuid.uuid4())
            self._listen_task = asyncio.create_task(self._listen_loop())
            for domain in ("Page", "Runtime", "DOM", "Network"):
                try:
                    await self.send(f"{domain}.enable")
                except (RuntimeError, WebSocketError, asyncio.TimeoutError):
                    pass
            self._save_state()
        except Exception:
            self.state = SessionState.FAILED
            raise

    async def _listen_loop(self) -> None:
        assert self.ws is not None
        try:
            while True:
                raw = await self.ws.recv_text()
                if raw is None:  # clean close
                    await self._handle_disconnect(ErrorClass.SESSION_LOST)
                    return
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if "id" in msg and msg["id"] in self.pending:
                    fut = self.pending.pop(msg["id"])
                    if not fut.done():
                        if "error" in msg:
                            fut.set_exception(RuntimeError(str(msg["error"])))
                        else:
                            fut.set_result(msg.get("result"))
                elif msg.get("method") in (
                    "Inspector.detached",
                    "Inspector.targetCrashed",
                ):
                    await self._handle_disconnect(ErrorClass.SESSION_LOST)
                    return
        except (WebSocketError, ConnectionError, OSError):
            await self._handle_disconnect(ErrorClass.SESSION_LOST)
        except Exception:
            await self._handle_disconnect(ErrorClass.UNKNOWN)

    async def send(self, method: str, params: Optional[dict] = None) -> Any:
        if self.state != SessionState.CONNECTED or self.ws is None:
            raise RuntimeError(f"CDP send in bad state {self.state.value}")
        self.message_id += 1
        mid = self.message_id
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self.pending[mid] = fut
        await self.ws.send_text(
            json.dumps({"id": mid, "method": method, "params": params or {}})
        )
        try:
            return await asyncio.wait_for(fut, timeout=self.config.command_timeout_sec)
        except asyncio.TimeoutError:
            self.pending.pop(mid, None)
            raise TimeoutError(method) from None

    async def safe_send(self, method: str, params: Optional[dict] = None) -> Any:
        """Send with recovery + HITL on failure. Auth-shaped errors pause."""
        try:
            return await self.send(method, params)
        except (asyncio.TimeoutError, TimeoutError):
            return await self._on_error(ErrorClass.TIMEOUT, method)
        except (WebSocketError, ConnectionError, OSError):
            await self._handle_disconnect(ErrorClass.SESSION_LOST)
            if self.state == SessionState.CONNECTED:
                return await self.send(method, params)
            raise
        except Exception as exc:
            cls = classify_error(exc)
            if cls == ErrorClass.CAPTCHA_OR_AUTH:
                return await self._on_error(cls, method, str(exc))
            return await self._on_error(ErrorClass.UNKNOWN, method, str(exc))

    async def _handle_disconnect(self, cls: ErrorClass) -> None:
        if self.state in (SessionState.RECOVERING, SessionState.HITL_PAUSED):
            return
        self.state = SessionState.RECOVERING
        result = await self.recover()
        if not result.success and result.required_hitl:
            choice = await self.hitl.request(
                "CDP Recovery Failed",
                result.message,
                options=["retry", "abort", "new_session"],
                timeout_sec=self.config.hitl_timeout_sec,
            )
            if choice == "retry":
                await self._handle_disconnect(cls)
            elif choice == "new_session":
                await self.connect()
            else:
                self.state = SessionState.FAILED

    async def recover(self) -> RecoveryResult:
        """Exponential-backoff reattach. Returns HITL requirement on failure."""
        for attempt in range(1, self.config.max_retries + 1):
            backoff = min(
                self.config.base_backoff_sec * (2 ** (attempt - 1)),
                self.config.max_backoff_sec,
            )
            await asyncio.sleep(backoff)
            try:
                ws_url = self._pick_ws_url()
                host, port, path = self._ws_parts(ws_url)
                if self.ws:
                    await self.ws.close()
                self.ws = await ws_connect(host, port, path)
                self.state = SessionState.CONNECTED
                if self._listen_task and not self._listen_task.done():
                    self._listen_task.cancel()
                self._listen_task = asyncio.create_task(self._listen_loop())
                for domain in ("Page", "Runtime", "DOM", "Network"):
                    try:
                        await self.send(f"{domain}.enable")
                    except (RuntimeError, WebSocketError, asyncio.TimeoutError):
                        pass
                self._save_state()
                return RecoveryResult(True, ws_url, "recovered")
            except Exception:
                continue
        return RecoveryResult(
            False,
            message=f"recovery failed after {self.config.max_retries} attempts",
            required_hitl=True,
        )

    async def _on_error(self, cls: ErrorClass, method: str, detail: str = "") -> Any:
        self.state = SessionState.HITL_PAUSED
        choice = await self.hitl.request(
            f"CDP Error: {cls.value}",
            f"{method}\n{detail}",
            options=["retry", "abort", "skip"],
            timeout_sec=self.config.hitl_timeout_sec,
        )
        self.state = (
            SessionState.CONNECTED if choice != "abort" else SessionState.FAILED
        )
        if choice == "retry":
            return await self.safe_send(method)
        if choice == "skip":
            return None
        raise RuntimeError(f"HITL abort: {method}")

    async def close(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()
        self.state = SessionState.DISCONNECTED
        self.hitl.clear()

    # -- state (non-sensitive metadata only) ---------------------------------

    def _save_state(self) -> None:
        """Persist non-sensitive session metadata. Never auth material."""
        try:
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.config.state_file.write_text(
                json.dumps(
                    {
                        "session_id": self.session_id,
                        "host": self.config.host,
                        "port": self.config.port,
                        "target_id": self.config.target_id,
                        "state": self.state.value,
                        "saved_at": time.time(),
                    }
                ),
                encoding="utf-8",
            )
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    def _skill_cdp_status(args):
        return (
            "CDP session manager: loopback-only (127.0.0.1:9222), stdlib websocket, "
            "recovery state machine + HITL flag-file. No credentials persisted. "
            "Browser driving requires an explicit human-confirmed session."
        )

    CDP_SKILLS = [
        Skill(
            id="automation_cdp",
            name="CDP Session",
            description="Attach to a user-owned Chromium via CDP (loopback only) with recovery + HITL",
            category="automation",
            risk_level=SkillRisk.HIGH,
            permissions=["automation.cdp"],
            requires_confirmation=True,
            handler=_skill_cdp_status,
            tags=["automation", "cdp", "browser"],
        ),
    ]
except ImportError:  # pragma: no cover
    CDP_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
