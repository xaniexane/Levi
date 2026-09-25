"""Transports for the CLEAR reference — loopback-proven, nothing wider.

Two transports, both local:

* VirtualWire — in-process, fully deterministic. Used by the test suite
  and by multi-tower simulations on one machine.
* LoopbackPair — a real TCP connection pinned to 127.0.0.1. Proves the
  framing and the protocol survive a real socket without ever touching
  a non-loopback address.

The hard rule: no network exposure beyond 127.0.0.1 without Chauncey's
word. `assert_loopback` refuses any other host, and wide-area peering
stays gated. A tower that needs our server to deliver a message has
failed the design — there is no cloud relay in this file.
"""

from __future__ import annotations

import socket
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .tower import ClearTower

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

_LEN = struct.Struct("!I")


class NetworkExposureError(Exception):
    """Refused: the requested host is not loopback. Wide-area peering is gated."""


def assert_loopback(host: str) -> None:
    if host not in LOOPBACK_HOSTS:
        raise NetworkExposureError(
            f"refusing non-loopback host {host!r}: "
            "wide-area peering is gated on the owner's explicit word"
        )


class VirtualWire:
    """Deterministic in-process wire between towers on one machine."""

    def __init__(self):
        self.endpoints: dict[bytes, "ClearTower"] = {}
        self.transcript: list[tuple[bytes, bytes, bytes]] = []

    def attach(self, tower: "ClearTower") -> None:
        self.endpoints[bytes(tower.node_id)] = tower
        tower.wire = self

    def transmit(self, src_id: bytes, dst_id: bytes, frame: bytes) -> bool:
        self.transcript.append((bytes(src_id), bytes(dst_id), bytes(frame)))
        endpoint = self.endpoints.get(bytes(dst_id))
        if endpoint is None:
            return False
        endpoint.inbox.append(bytes(frame))
        return True


def _send_frame(sock: socket.socket, frame: bytes) -> None:
    sock.sendall(_LEN.pack(len(frame)) + frame)


def _recv_frame(sock: socket.socket, timeout: float = 5.0) -> bytes:
    sock.settimeout(timeout)
    header = b""
    while len(header) < _LEN.size:
        chunk = sock.recv(_LEN.size - len(header))
        if not chunk:
            raise ConnectionError("loopback peer closed the connection")
        header += chunk
    (length,) = _LEN.unpack(header)
    if length > 1 << 20:
        raise ConnectionError("absurd frame length on loopback")
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("loopback peer closed mid-frame")
        body += chunk
    return body


class LoopbackPair:
    """One real TCP connection over 127.0.0.1, both ends in hand.

    Proves the protocol on a real socket. The constructor itself is the
    proof: bind, connect, and accept all happen on 127.0.0.1.
    """

    def __init__(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        conn, peer = server.accept()
        assert_loopback(peer[0])
        server.close()
        self.a = client  # dialer end
        self.b = conn  # listener end

    def send_a(self, frame: bytes) -> None:
        _send_frame(self.a, frame)

    def send_b(self, frame: bytes) -> None:
        _send_frame(self.b, frame)

    def recv_a(self, timeout: float = 5.0) -> bytes:
        return _recv_frame(self.a, timeout)

    def recv_b(self, timeout: float = 5.0) -> bytes:
        return _recv_frame(self.b, timeout)

    def close(self) -> None:
        for sock in (self.a, self.b):
            try:
                sock.close()
            except OSError:
                pass


def loopback_connect(host: str, port: int, timeout: float = 5.0) -> socket.socket:
    """Dial a loopback host. Anything else raises NetworkExposureError."""
    assert_loopback(host)
    return socket.create_connection((host, port), timeout=timeout)


__all__ = [
    "LOOPBACK_HOSTS",
    "NetworkExposureError",
    "assert_loopback",
    "VirtualWire",
    "LoopbackPair",
    "loopback_connect",
]
