"""LAN peer discovery: UDP multicast beacons + a TTL peer table.

A hub announces itself every few seconds; listeners collect beacons into
a table that expires stale entries. No registry, no central server — the
LAN *is* the directory.

For tests, every address/port is injectable so beacons can run over
plain loopback UDP instead of multicast.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

MULTICAST_GROUP = "239.192.77.77"
DISCOVERY_PORT = 45555
BEACON_INTERVAL = 5.0
BEACON_TTL = 30.0
MAGIC = "levi-presence-v1"


@dataclass
class Beacon:
    hub_id: str
    name: str
    host: str
    port: int
    rooms: List[str] = field(default_factory=list)
    at: str = ""

    def __post_init__(self) -> None:
        if not self.at:
            self.at = datetime.now(timezone.utc).isoformat()

    def encode(self) -> bytes:
        payload = {"magic": MAGIC}
        payload.update(asdict(self))
        return json.dumps(payload).encode("utf-8")

    @classmethod
    def decode(cls, raw: bytes) -> Optional["Beacon"]:
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(obj, dict) or obj.get("magic") != MAGIC:
            return None
        try:
            return cls(
                hub_id=str(obj["hub_id"]),
                name=str(obj["name"]),
                host=str(obj["host"]),
                port=int(obj["port"]),
                rooms=list(obj.get("rooms") or []),
                at=str(obj.get("at") or ""),
            )
        except (KeyError, TypeError, ValueError):
            return None


def send_beacon(beacon: Beacon,
                targets: Optional[List[Tuple[str, int]]] = None) -> None:
    """Send one beacon datagram to each target (default: multicast group).

    Uses a connected UDP socket per target: this works for unicast and
    for multicast group addresses alike, and keeps per-target failures
    isolated (one bad target never kills the others).
    """
    targets = targets or [(MULTICAST_GROUP, DISCOVERY_PORT)]
    raw = beacon.encode()
    for host, port in targets:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Keep multicast on the local network only.
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL,
                            struct.pack("b", 2))
            sock.connect((host, port))
            sock.send(raw)
        except OSError:
            continue  # one bad target must not kill the others
        finally:
            sock.close()


class BeaconSender(threading.Thread):
    """Background thread announcing a hub until stopped."""

    def __init__(self, beacon: Beacon,
                 targets: Optional[List[Tuple[str, int]]] = None,
                 interval: float = BEACON_INTERVAL) -> None:
        super().__init__(daemon=True, name="presence-beacon")
        self._beacon = beacon
        self._targets = targets
        self._interval = interval
        self._stop = threading.Event()

    def run(self) -> None:  # noqa: D102
        while not self._stop.wait(self._interval):
            # Re-stamp so listeners measure freshness honestly.
            self._beacon.at = datetime.now(timezone.utc).isoformat()
            send_beacon(self._beacon, self._targets)

    def stop(self) -> None:
        self._stop.set()


class BeaconListener:
    """Collect beacons into a peer table; entries expire after the TTL."""

    def __init__(self, bind: Tuple[str, int] = ("0.0.0.0", DISCOVERY_PORT),
                 group: str = MULTICAST_GROUP,
                 ttl: float = BEACON_TTL) -> None:
        self._bind = bind
        self._group = group
        self._ttl = ttl
        self._peers: Dict[str, Tuple[Beacon, float]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> "BeaconListener":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.bind(self._bind)
        # Join the multicast group on the default interface; harmless if
        # the bind address is loopback (tests use unicast targets anyway).
        try:
            mreq = struct.pack(
                "4s4s", socket.inet_aton(self._group),
                socket.inet_aton("0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError:
            pass
        sock.settimeout(0.5)
        self._sock = sock
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="presence-listen")
        self._thread.start()
        return self

    def _loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                raw, _addr = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            beacon = Beacon.decode(raw)
            if beacon is None:
                continue
            with self._lock:
                self._peers[beacon.hub_id] = (beacon, time.monotonic())

    def peers(self) -> List[Beacon]:
        """Currently-live peers (stale entries are expired first)."""
        now = time.monotonic()
        with self._lock:
            live = [
                beacon for beacon, seen in self._peers.values()
                if now - seen <= self._ttl
            ]
            self._peers = {
                hid: (b, s) for hid, (b, s) in self._peers.items()
                if now - s <= self._ttl
            }
        return live

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
