"""Plan 9-style per-task namespaces + 9P-style local IPC.

Inspired by Plan 9's per-process namespaces and the 9P protocol's
"everything is a file / everything is a message" discipline. Original,
from-scratch reimplementation for LEVI — no Plan 9 code is used.

Two parts:

(a) ``Namespace`` — per-task isolation for running tools. A tool runs in a
    subprocess with:
    - a restricted working directory (a fresh temp sandbox, or an explicit root),
    - a scrubbed environment (minimal default; an explicit allowlist may pass
      selected host variables through),
    - enforced wall-clock timeouts (whole process group is killed),
    - optional Linux resource limits (CPU seconds, address-space bytes) via
      ``resource.setrlimit`` in the child; silently skipped where the
      ``resource`` module is unavailable.
    Output is captured. Deny-closed defaults: empty env, cwd outside the
    project tree is never assumed.

(b) 9P-STYLE message surface — NOT a real 9P server. Newline-delimited JSON
    frames over ``socket.socketpair()`` for module-to-module communication
    inside one process (loopback only, no network). API:

    - :func:`create_channel` -> ``(client, server)`` channel pair
    - :meth:`Channel.send` — one-way typed message
    - :meth:`Channel.request` — request with correlated reply (by id)
    - :meth:`Channel.recv` — receive the next message
    - :func:`serve` — blocking handler loop; exceptions in the handler are
      returned as error replies, never crash the server

    Message shape: ``{"id": str, "type": str, "payload": ...}``;
    replies: ``{"id": str, "type": "reply", "in_reply_to": str, "ok": bool,
    "payload": ..., "error": ...}``.
"""

from __future__ import annotations

import collections
import itertools
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = [
    "Namespace",
    "NamespaceError",
    "NamespaceTimeout",
    "RunResult",
    "Channel",
    "ChannelError",
    "ChannelTimeout",
    "ChannelClosed",
    "StopServing",
    "create_channel",
    "serve",
]


# ===========================================================================
# (a) Namespace — per-task tool isolation
# ===========================================================================


class NamespaceError(Exception):
    """Base class for namespace failures."""


class NamespaceTimeout(NamespaceError):
    """The tool exceeded its wall-clock timeout (process group killed)."""


@dataclass
class RunResult:
    """Outcome of a namespaced tool run."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    elapsed: float
    resource_limits_applied: bool = False


# Minimal environment a tool gets by default: nothing that leaks the host.
_DEFAULT_ENV = {"PATH": "/usr/bin:/bin"}


def _scrubbed_env(env_allow: tuple[str, ...] = ()) -> dict[str, str]:
    env = dict(_DEFAULT_ENV)
    for name in env_allow:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def _preexec_factory(cpu_seconds: Optional[int], mem_bytes: Optional[int]) -> Optional[Callable[[], None]]:
    try:
        import resource  # noqa: F401  (Linux/macOS only)
    except ImportError:
        return None

    def preexec() -> None:
        import resource as _resource

        # New process group so the parent can kill the whole tree on timeout.
        try:
            os.setsid()
        except OSError:
            pass
        if cpu_seconds is not None:
            _resource.setrlimit(_resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if mem_bytes is not None:
            _resource.setrlimit(_resource.RLIMIT_AS, (mem_bytes, mem_bytes))

    return preexec


class Namespace:
    """A per-task execution namespace for tools (stdlib subprocess only).

    Parameters
    ----------
    root: directory the tool runs in. If None, a fresh temp dir is created
        and removed on ``close()`` / context-manager exit.
    env: explicit environment mapping for the child. If None, a scrubbed
        minimal env is used (see ``env_allow``).
    env_allow: host variable names copied through when ``env`` is None.
    timeout: default wall-clock timeout in seconds for :meth:`run`.
    cpu_seconds / mem_bytes: optional Linux resource limits for the child.
    keep_root: when ``root`` was auto-created, keep it after close (default False).
    """

    def __init__(
        self,
        root: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        env_allow: tuple[str, ...] = (),
        timeout: float = 30.0,
        cpu_seconds: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        keep_root: bool = False,
    ) -> None:
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive or None")
        self._auto_root = root is None
        self.root = root or tempfile.mkdtemp(prefix="levi-ns-")
        os.makedirs(self.root, exist_ok=True)
        self._env = dict(env) if env is not None else _scrubbed_env(tuple(env_allow))
        self.timeout = timeout
        self.cpu_seconds = cpu_seconds
        self.mem_bytes = mem_bytes
        self._keep_root = keep_root
        self._closed = False

    # -- context manager -----------------------------------------------------
    def __enter__(self) -> "Namespace":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._auto_root and not self._keep_root and not self._closed:
            shutil.rmtree(self.root, ignore_errors=True)
        self._closed = True

    # -- execution -----------------------------------------------------------
    def run(
        self,
        args: list[str],
        input: Optional[str] = None,  # noqa: A002 - mirrors subprocess API
        timeout: Optional[float] = None,
        extra_env: Optional[dict[str, str]] = None,
    ) -> RunResult:
        """Run ``args`` inside the namespace; capture output; enforce timeout."""
        if self._closed:
            raise NamespaceError("namespace is closed")
        if not args:
            raise NamespaceError("no command given")
        limit = self.timeout if timeout is None else timeout
        env = dict(self._env)
        if extra_env:
            env.update(extra_env)

        preexec = _preexec_factory(self.cpu_seconds, self.mem_bytes)
        started = time.monotonic()
        proc = subprocess.Popen(
            [str(a) for a in args],
            cwd=self.root,
            env=env,
            stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=preexec,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(input=input, timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Kill the whole process group (child was setsid'd when possible).
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    proc.kill()
                except OSError:
                    pass
            stdout, stderr = proc.communicate()
            raise NamespaceTimeout(
                f"command exceeded {limit}s timeout: {args[0]}"
            ) from None
        elapsed = time.monotonic() - started
        return RunResult(
            args=[str(a) for a in args],
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=timed_out,
            elapsed=elapsed,
            resource_limits_applied=preexec is not None
            and (self.cpu_seconds is not None or self.mem_bytes is not None),
        )

    def write_file(self, name: str, content: str) -> str:
        """Stage an input file inside the namespace root. Rejects path escapes."""
        path = os.path.realpath(os.path.join(self.root, name))
        if not path.startswith(os.path.realpath(self.root) + os.sep):
            raise NamespaceError(f"path escapes namespace root: {name!r}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def read_file(self, name: str) -> str:
        path = os.path.realpath(os.path.join(self.root, name))
        if not path.startswith(os.path.realpath(self.root) + os.sep):
            raise NamespaceError(f"path escapes namespace root: {name!r}")
        with open(path, encoding="utf-8") as fh:
            return fh.read()


# ===========================================================================
# (b) 9P-style message surface over socketpair
# ===========================================================================


class ChannelError(Exception):
    """Base class for channel failures."""


class ChannelTimeout(ChannelError):
    """A recv/request exceeded its timeout."""


class ChannelClosed(ChannelError):
    """The peer closed the channel."""


class StopServing(Exception):
    """Raise from a serve handler to stop the server loop cleanly."""


_id_counter = itertools.count(1)
_id_lock = threading.Lock()


def _next_id() -> str:
    with _id_lock:
        return f"m{next(_id_counter)}"


class Channel:
    """One end of a 9P-style message channel (newline-delimited JSON frames)."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._reader = sock.makefile("r", encoding="utf-8")
        self._write_lock = threading.Lock()
        self._pending: collections.deque[dict] = collections.deque()
        self._closed = False

    # -- low level -----------------------------------------------------------
    def send(self, msg_type: str, payload: Any = None) -> str:
        """Send a one-way typed message; returns its id."""
        return self._send_frame({"id": _next_id(), "type": msg_type, "payload": payload})

    def _send_frame(self, frame: dict) -> str:
        if self._closed:
            raise ChannelClosed("channel is closed")
        data = (json.dumps(frame, separators=(",", ":")) + "\n").encode("utf-8")
        with self._write_lock:
            try:
                self._sock.sendall(data)
            except OSError as exc:
                raise ChannelClosed(f"send failed: {exc}") from exc
        return frame["id"]

    def _recv_frame(self, timeout: Optional[float]) -> dict:
        if self._closed and not self._pending:
            raise ChannelClosed("channel is closed")
        self._sock.settimeout(timeout)
        try:
            line = self._reader.readline()
        except socket.timeout as exc:
            raise ChannelTimeout("recv timed out") from exc
        except OSError as exc:
            raise ChannelClosed(f"recv failed: {exc}") from exc
        finally:
            self._sock.settimeout(None)
        if line == "":
            raise ChannelClosed("peer closed the connection")
        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChannelError(f"malformed frame: {exc}") from exc
        if not isinstance(frame, dict) or "type" not in frame:
            raise ChannelError("malformed frame: missing 'type'")
        return frame

    def recv(self, timeout: Optional[float] = None) -> tuple[str, Any, str]:
        """Receive the next message as ``(type, payload, id)``.

        Buffered out-of-order replies (from :meth:`request`) are delivered first.
        """
        if self._pending:
            frame = self._pending.popleft()
        else:
            frame = self._recv_frame(timeout)
        return frame["type"], frame.get("payload"), frame.get("id", "")

    # -- request/response ----------------------------------------------------
    def request(self, msg_type: str, payload: Any = None, timeout: float = 5.0) -> Any:
        """Send a request and wait for the correlated reply.

        Raises ChannelTimeout on timeout; the peer's error string on ``ok: false``.
        """
        req_id = self._send_frame({"id": _next_id(), "type": msg_type, "payload": payload})
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            frame = self._recv_frame(remaining if remaining != 0 else 0.0)
            if frame.get("type") == "reply" and frame.get("in_reply_to") == req_id:
                if frame.get("ok"):
                    return frame.get("payload")
                raise ChannelError(str(frame.get("error", "remote error")))
            # Not our reply: buffer it for recv()/later requests.
            self._pending.append(frame)

    def close(self) -> None:
        self._closed = True
        try:
            self._reader.close()
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


def create_channel() -> tuple[Channel, Channel]:
    """Create a connected channel pair (loopback socketpair, no network)."""
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    return Channel(a), Channel(b)


def serve(
    channel: Channel,
    handler: Callable[[str, Any], Any],
    *,
    request_types: Optional[set[str]] = None,
    on_notify: Optional[Callable[[str, Any], None]] = None,
) -> None:
    """Blocking server loop over ``channel``.

    Each ``{"type", "payload", "id"}`` frame whose type is not ``"reply"``
    is dispatched to ``handler(msg_type, payload)`` and the return value is
    sent back as a correlated ``ok: true`` reply. If the handler raises,
    the exception is sent back as an ``ok: false`` reply and the loop
    continues. Raising :class:`StopServing` (or peer close) ends the loop.
    """
    allowed = request_types
    try:
        while True:
            try:
                msg_type, payload, msg_id = channel.recv()
            except ChannelClosed:
                break
            if msg_type == "reply":
                continue  # stray reply; a requester buffers its own
            if allowed is not None and msg_type not in allowed:
                channel._send_frame(
                    {
                        "id": _next_id(),
                        "type": "reply",
                        "in_reply_to": msg_id,
                        "ok": False,
                        "payload": None,
                        "error": f"unknown message type: {msg_type!r}",
                    }
                )
                continue
            try:
                result = handler(msg_type, payload)
            except StopServing:
                channel._send_frame(
                    {
                        "id": _next_id(),
                        "type": "reply",
                        "in_reply_to": msg_id,
                        "ok": True,
                        "payload": None,
                        "error": None,
                    }
                )
                break
            except Exception as exc:  # handler errors become error replies
                channel._send_frame(
                    {
                        "id": _next_id(),
                        "type": "reply",
                        "in_reply_to": msg_id,
                        "ok": False,
                        "payload": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            if on_notify is not None and msg_type == "notify":
                try:
                    on_notify(msg_type, payload)
                except Exception:
                    pass
            channel._send_frame(
                {
                    "id": _next_id(),
                    "type": "reply",
                    "in_reply_to": msg_id,
                    "ok": True,
                    "payload": result,
                    "error": None,
                }
            )
    finally:
        channel.close()


@dataclass
class ServedChannel:
    """A channel pair with a background server thread."""

    client: Channel = field(repr=False)
    _server: Channel = field(repr=False)
    _thread: threading.Thread = field(repr=False)
    _handler: Callable[[str, Any], Any] = field(repr=False)

    def stop(self) -> None:
        try:
            self.client.send("shutdown", None)
        except ChannelError:
            pass
        self._thread.join(timeout=5)
        try:
            self.client.close()
        except ChannelError:
            pass


def serve_in_background(
    handler: Callable[[str, Any], Any],
    *,
    request_types: Optional[set[str]] = None,
) -> ServedChannel:
    """Start ``serve`` on a background thread; returns the client end."""
    client, server = create_channel()

    def _wrapped(msg_type: str, payload: Any) -> Any:
        if msg_type == "shutdown":
            raise StopServing()
        return handler(msg_type, payload)

    thread = threading.Thread(
        target=serve, args=(server, _wrapped), kwargs={"request_types": request_types}, daemon=True
    )
    thread.start()
    return ServedChannel(client=client, _server=server, _thread=thread, _handler=handler)
