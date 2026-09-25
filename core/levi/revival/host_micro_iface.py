"""Structured host commands instead of screen-scraping.

Studied from: dead-networks-20260916 report.md
[CompuServe HMI / RLE vector graphics protocol].

The mechanism under study: a graphical client talks to a host through a
*binary command protocol* — frames carrying opcodes and typed arguments —
instead of scraping the host's text CLI. The host answers with typed
responses. The core discipline: never parse presentation; use the API.

A vector-graphics command set rides on the same frames: drawing is done
with cheap run-length-friendly primitives (line, rect, text, clear)
rather than shipped bitmaps, so a whole screen is a short command list.

Original, from-scratch implementation for LEVI. Time is caller-provided.
No wall clock. stdlib-only. No network.

Public surface:
- ``Command`` — opcode + args; ``encode()`` / ``decode()`` binary frames.
- ``Response`` — status + values; ``encode()`` / ``decode()``.
- ``HostIface`` — ``register(name, fn)``, ``handle(frame) -> frame``;
  named-value store (GET/SET/LIST), procedure calls (RUN), and a vector
  display list (DRAW).

Honest limits: frames live in memory (no socket layer); the display list
is a command log, not a rasterizer; argument types are str/int/bytes only.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

ORIGIN = "levi-revival/host_micro_iface"

_MAGIC = b"HMI1"

OP_GET = 0x01
OP_SET = 0x02
OP_RUN = 0x03
OP_LIST = 0x04
OP_DRAW = 0x10

STATUS_OK = 0
STATUS_ERR = 1

# arg type tags
_T_STR = 0
_T_INT = 1
_T_BYTES = 2

_DRAW_OPS = {"clear", "line", "rect", "text", "circle"}


def _pack_arg(value) -> bytes:
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return struct.pack(">BI", _T_STR, len(raw)) + raw
    if isinstance(value, int):
        return struct.pack(">BI", _T_INT, 8) + struct.pack(">q", value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return struct.pack(">BI", _T_BYTES, len(raw)) + raw
    raise TypeError(f"unsupported arg type: {type(value).__name__}")


def _unpack_args(buf: bytes, count: int) -> Tuple[List, bytes]:
    args: List = []
    off = 0
    for _ in range(count):
        tag, length = struct.unpack_from(">BI", buf, off)
        off += 5
        raw = buf[off : off + length]
        off += length
        if tag == _T_STR:
            args.append(raw.decode("utf-8"))
        elif tag == _T_INT:
            args.append(struct.unpack(">q", raw)[0])
        elif tag == _T_BYTES:
            args.append(raw)
        else:
            raise ValueError(f"unknown arg tag {tag}")
    return args, buf[off:]


@dataclass
class Command:
    """One structured host command: opcode + typed arguments."""

    opcode: int
    args: List = field(default_factory=list)

    def encode(self) -> bytes:
        body = b"".join(_pack_arg(a) for a in self.args)
        return _MAGIC + struct.pack(">HH", self.opcode, len(self.args)) + body

    @classmethod
    def decode(cls, frame: bytes) -> "Command":
        try:
            if frame[:4] != _MAGIC:
                raise ValueError("bad frame magic")
            opcode, count = struct.unpack_from(">HH", frame, 4)
            args, rest = _unpack_args(frame[8:], count)
        except struct.error as exc:
            raise ValueError(f"bad frame: {exc}") from None
        if rest:
            raise ValueError("trailing bytes in frame")
        return cls(opcode, args)


@dataclass
class Response:
    """Typed host answer: status 0 = ok, 1 = error, plus values."""

    status: int
    values: List = field(default_factory=list)

    def encode(self) -> bytes:
        body = b"".join(_pack_arg(v) for v in self.values)
        return _MAGIC + struct.pack(">BH", self.status, len(self.values)) + body

    @classmethod
    def decode(cls, frame: bytes) -> "Response":
        try:
            if frame[:4] != _MAGIC:
                raise ValueError("bad frame magic")
            status, count = struct.unpack_from(">BH", frame, 4)
            values, rest = _unpack_args(frame[7:], count)
        except struct.error as exc:
            raise ValueError(f"bad frame: {exc}") from None
        if rest:
            raise ValueError("trailing bytes in frame")
        return cls(status, values)


class HostIface:
    """The host side: dispatches structured commands, never screen text.

    Holds a named-value store, registered procedures, and a vector
    display list. Unknown opcodes and bad arguments yield error
    responses, never exceptions across the frame boundary.
    """

    def __init__(self) -> None:
        self.store: Dict[str, object] = {}
        self.procs: Dict[str, Callable[..., object]] = {}
        self.display: List[Tuple[str, tuple]] = []  # (primitive, params)

    def register(self, name: str, fn: Callable[..., object]) -> None:
        """Register a host procedure callable by clients via RUN."""
        self.procs[name] = fn

    # -- frame entry point -------------------------------------------------
    def handle(self, frame: bytes) -> bytes:
        """Decode one command frame, dispatch, return a response frame."""
        try:
            cmd = Command.decode(frame)
        except (ValueError, struct.error) as exc:
            return Response(STATUS_ERR, [f"decode: {exc}"]).encode()
        try:
            resp = self._dispatch(cmd)
        except Exception as exc:  # host errors become error responses
            resp = Response(STATUS_ERR, [str(exc)])
        return resp.encode()

    # -- dispatch ----------------------------------------------------------
    def _dispatch(self, cmd: Command) -> Response:
        if cmd.opcode == OP_GET:
            name = self._str_arg(cmd, 0)
            if name not in self.store:
                return Response(STATUS_ERR, [f"unknown name: {name}"])
            return Response(STATUS_OK, [self.store[name]])
        if cmd.opcode == OP_SET:
            name = self._str_arg(cmd, 0)
            self.store[name] = cmd.args[1]
            return Response(STATUS_OK, [])
        if cmd.opcode == OP_LIST:
            return Response(STATUS_OK, sorted(self.store))
        if cmd.opcode == OP_RUN:
            name = self._str_arg(cmd, 0)
            if name not in self.procs:
                return Response(STATUS_ERR, [f"unknown procedure: {name}"])
            result = self.procs[name](*cmd.args[1:])
            return Response(STATUS_OK, [result])
        if cmd.opcode == OP_DRAW:
            prim = self._str_arg(cmd, 0)
            if prim not in _DRAW_OPS:
                return Response(STATUS_ERR, [f"unknown draw op: {prim}"])
            self.display.append((prim, tuple(cmd.args[1:])))
            return Response(STATUS_OK, [len(self.display)])
        return Response(STATUS_ERR, [f"unknown opcode: {cmd.opcode:#x}"])

    @staticmethod
    def _str_arg(cmd: Command, idx: int) -> str:
        try:
            value = cmd.args[idx]
        except IndexError:
            raise ValueError("missing argument") from None
        if not isinstance(value, str):
            raise ValueError("argument must be str")
        return value

    # -- client conveniences (encode only; host still answers via handle) --
    def clear_display(self) -> None:
        self.display.clear()


def demo() -> Dict[str, object]:
    """Exercise the command loop end to end; returns a summary dict."""
    host = HostIface()
    host.register("add", lambda a, b: a + b)
    out: Dict[str, object] = {}
    out["set"] = Response.decode(
        host.handle(Command(OP_SET, ["greeting", "hello"]).encode())
    ).status
    out["get"] = Response.decode(
        host.handle(Command(OP_GET, ["greeting"]).encode())
    ).values
    out["run"] = Response.decode(
        host.handle(Command(OP_RUN, ["add", 20, 22]).encode())
    ).values
    out["draw"] = Response.decode(
        host.handle(Command(OP_DRAW, ["line", 0, 0, 256, 192]).encode())
    ).values
    out["display"] = host.display
    return out
