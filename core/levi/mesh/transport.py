"""Mesh transport — pluggable send/recv/discover abstraction.

``Transport`` is the seam. ``LocalTransport`` is the prototype:
TCP for messages, local file rendezvous for discovery. ``DeepWebTransport``
is the onion-style hidden-service lane Chauncey ordered ("even deep
web"): interface + capability contract only — a real onion transport
needs a tor daemon, which is out of prototype scope, but the
abstraction accepts it later with zero changes above this layer.

Discovery note (honest): the prototype discovers peers through a
shared rendezvous directory — each node writes its heartbeat as
``<node_id>.json`` and reads the directory. Deterministic, no
configuration, works everywhere including sandboxes where multicast
is blocked. LAN-grade discovery (multicast/mDNS) is the planned
upgrade and changes nothing above this class.

Gateway Law: transports move fleet-internal messages only. There is
no HTTP client, no external dial-out anywhere in this module.
"""

from __future__ import annotations

import json
import os
import queue
import socket
import struct
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_TCP_BACKLOG = 16
_RECV_BYTES = 65536
_MSG_SIZE_CAP = 10 * 1024 * 1024


class TransportUnavailable(RuntimeError):
    """Raised when a transport lane cannot operate in this environment."""


class Transport(ABC):
    """Pluggable mesh transport. Implementations move dict messages."""

    @abstractmethod
    def bind(self, node_id: str) -> None:
        """Claim this node's identity on the transport."""

    @abstractmethod
    def announce(self, info: Dict) -> None:
        """Broadcast presence/info for discovery (heartbeat)."""

    @abstractmethod
    def send(self, node_id: str, message: Dict) -> None:
        """Deliver one message to a peer. Raises on unknown/unreachable peer."""

    @abstractmethod
    def recv(self, timeout: float = 1.0) -> Optional[Tuple[str, Dict]]:
        """Next inbound message as (sender_id, message), or None on timeout."""

    @abstractmethod
    def discover(self, timeout: float = 1.0) -> List[Dict]:
        """Peers heard recently: [{node_id, address, port, ...}]."""

    @abstractmethod
    def capabilities(self) -> Dict:
        """What this lane can and cannot do — the honest contract."""

    @abstractmethod
    def close(self) -> None:
        """Release sockets and threads."""


def _pack(message: Dict) -> bytes:
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def _read_exact(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        part = conn.recv(n - len(buf))
        if not part:
            raise ConnectionError("peer closed mid-message")
        buf += part
    return buf


def default_rendezvous_dir() -> Path:
    base = os.environ.get("LEVI_MESH_DIR", "")
    if base:
        return Path(base) / "rendezvous"
    return Path.home() / ".levi" / "mesh" / "rendezvous"


class LocalTransport(Transport):
    """Localhost transport for the prototype.

    * Discovery: file rendezvous. ``announce()`` writes
      ``<rendezvous_dir>/<node_id>.json`` (tcp port, offer, timestamp);
      ``discover()`` reads every fresh file. ``close()``/``leave``
      removes the file. Entries older than ``registry_ttl`` are
      treated as gone.
    * Messages: TCP to the peer's advertised port on 127.0.0.1,
      4-byte length-prefixed JSON.
    """

    def __init__(
        self,
        rendezvous_dir: Optional[Path] = None,
        registry_ttl: float = 15.0,
    ) -> None:
        self._rendezvous_dir = (
            Path(rendezvous_dir) if rendezvous_dir else default_rendezvous_dir()
        )
        self._registry_ttl = registry_ttl
        self._node_id: Optional[str] = None
        self._tcp: Optional[socket.socket] = None
        self._tcp_port = 0
        self._inbox: "queue.Queue[Tuple[str, Dict]]" = queue.Queue()
        self._stop = threading.Event()
        self._accept_thread: Optional[threading.Thread] = None
        # node_id -> (tcp_port, seen_ts): avoids a full discover() per send.
        self._port_cache: Dict[str, Tuple[int, float]] = {}

    # -- lifecycle ----------------------------------------------------

    def bind(self, node_id: str) -> None:
        if self._tcp is not None:
            raise TransportUnavailable("already bound")
        self._node_id = node_id
        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp.bind(("127.0.0.1", 0))
        self._tcp.listen(_TCP_BACKLOG)
        self._tcp.settimeout(0.5)
        self._tcp_port = self._tcp.getsockname()[1]
        self._stop.clear()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
            self._accept_thread = None
        if self._tcp is not None:
            try:
                self._tcp.close()
            except OSError:
                pass
            self._tcp = None
        self._drop_rendezvous_file()

    def _rendezvous_file(self) -> Path:
        assert self._node_id is not None
        return self._rendezvous_dir / f"{self._node_id}.json"

    def _drop_rendezvous_file(self) -> None:
        if self._node_id is None:
            return
        try:
            self._rendezvous_file().unlink(missing_ok=True)
        except OSError:
            pass

    # -- discovery ----------------------------------------------------

    def announce(self, info: Dict) -> None:
        if self._node_id is None:
            raise TransportUnavailable("bind() before announce()")
        payload = {
            "node_id": self._node_id,
            "tcp_port": self._tcp_port,
            "ts": time.time(),
        }
        payload.update(info)
        self._rendezvous_dir.mkdir(parents=True, exist_ok=True)
        # Unique temp name per call: heartbeat and discover() threads can
        # announce concurrently — a shared tmp name would let one thread
        # rename the file out from under the other (FileNotFoundError).
        tmp = self._rendezvous_dir / (
            f"{self._node_id}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self._rendezvous_file())

    def discover(self, timeout: float = 1.0) -> List[Dict]:
        # Nudge our own announce so a fresh bind is visible, then read.
        try:
            self.announce({"kind": "discover-ping"})
        except TransportUnavailable:
            pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.05)
        peers = []
        now = time.time()
        if self._rendezvous_dir.is_dir():
            for path in sorted(self._rendezvous_dir.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (ValueError, OSError, UnicodeDecodeError):
                    continue
                if payload.get("node_id") == self._node_id:
                    continue
                if now - float(payload.get("ts", 0)) > self._registry_ttl:
                    continue
                peers.append(payload)
            # Sweep stale announce temp files (a crashed announce can
            # leave one behind; fresh ones belong to a live writer).
            for tmp in self._rendezvous_dir.glob("*.tmp"):
                try:
                    if now - tmp.stat().st_mtime > self._registry_ttl:
                        tmp.unlink(missing_ok=True)
                except OSError:
                    continue
        return peers

    # -- messaging ----------------------------------------------------

    def _peer_port(self, node_id: str) -> int:
        now = time.time()
        cached = self._port_cache.get(node_id)
        if cached is not None and now - cached[1] <= self._registry_ttl:
            return cached[0]
        for peer in self.discover(timeout=0.5):
            nid = peer.get("node_id")
            if nid and "tcp_port" in peer:
                self._port_cache[nid] = (int(peer["tcp_port"]), now)
        cached = self._port_cache.get(node_id)
        if cached is None:
            raise TransportUnavailable(f"unknown peer {node_id!r}")
        return cached[0]

    def send(self, node_id: str, message: Dict) -> None:
        if self._node_id is None:
            raise TransportUnavailable("bind() before send()")
        port = self._peer_port(node_id)
        envelope = {"from": self._node_id}
        envelope.update(message)
        raw = _pack(envelope)
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        except OSError:
            # Port was cached but the peer is gone (killed between
            # heartbeat and send). Drop the stale entry and report it
            # as an unknown peer so the farmer re-farms elsewhere.
            self._port_cache.pop(node_id, None)
            raise TransportUnavailable(f"peer {node_id!r} unreachable") from None
        try:
            sock.sendall(raw)
        finally:
            sock.close()

    def _accept_loop(self) -> None:
        assert self._tcp is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                (length,) = struct.unpack(">I", _read_exact(conn, 4))
                if length > _MSG_SIZE_CAP:
                    continue
                body = _read_exact(conn, length)
                message = json.loads(body.decode("utf-8"))
            except (
                ConnectionError,
                ValueError,
                struct.error,
                UnicodeDecodeError,
                OSError,
            ):
                continue
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
            sender = message.pop("from", "unknown")
            self._inbox.put((sender, message))

    def recv(self, timeout: float = 1.0) -> Optional[Tuple[str, Dict]]:
        try:
            return self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def capabilities(self) -> Dict:
        return {
            "lane": "local",
            "discovery": (
                "file rendezvous (prototype); multicast/mDNS planned for LAN"
            ),
            "messages": "TCP loopback, length-prefixed JSON",
            "onion_routing": False,
            "external_reach": False,  # Gateway Law: fleet-internal only
            "limits": (
                "single host; no NAT traversal; rendezvous dir "
                "shared by co-located nodes (prototype)"
            ),
        }


class LanTransport(LocalTransport):
    """LAN lane: TCP across machines, direct-peer discovery.

    ``LocalTransport`` is loopback-only. ``LanTransport`` binds the
    real interface and discovers through an explicit peer list — no
    multicast, no mDNS, no broadcast. Each node is configured with
    the (host, port) of its known peers (your LAN IPs); ``announce()``
    pushes a heartbeat message to every known peer over TCP, and
    ``discover()`` returns peers heard-from within ``registry_ttl``.
    Deterministic on any LAN, including old Windows stacks where
    multicast is unreliable.

    Addressing: a peer's host is learned from the source address of
    its heartbeat connection; its listen port comes from the
    heartbeat payload. Same-LAN only — no NAT traversal, no
    hole-punching (honest limit, documented in capabilities()).

    Heartbeats never enter the message inbox — they are recorded in
    the seen-peer table and dropped, so the inbox cannot grow
    unboundedly on an always-on node.
    """

    def __init__(
        self,
        bind_host: str = "0.0.0.0",
        bind_port: int = 0,
        known_peers: Sequence[Tuple[str, int]] = (),
        registry_ttl: float = 15.0,
    ) -> None:
        super().__init__(rendezvous_dir=None, registry_ttl=registry_ttl)
        self._bind_host = bind_host
        self._bind_port = int(bind_port)
        self._known_peers: List[Tuple[str, int]] = [
            (str(h), int(p)) for h, p in known_peers
        ]
        self._seen: Dict[str, Dict] = {}
        self._seen_lock = threading.Lock()
        # Last non-ping announce info (heartbeat + offer). A
        # discover-ping reply re-sends this instead of a bare
        # heartbeat, so the offer survives the fast discovery path.
        self._standing_info: Dict = {}

    # -- peer list ----------------------------------------------------

    def add_peer(self, host: str, port: int) -> None:
        """Add a known peer at runtime (useful when DHCP moves LAN IPs)."""
        entry = (str(host), int(port))
        if entry not in self._known_peers:
            self._known_peers.append(entry)

    # -- lifecycle ----------------------------------------------------

    def bind(self, node_id: str) -> None:
        if self._tcp is not None:
            raise TransportUnavailable("already bound")
        self._node_id = node_id
        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp.bind((self._bind_host, self._bind_port))
        self._tcp.listen(_TCP_BACKLOG)
        self._tcp.settimeout(0.5)
        self._tcp_port = self._tcp.getsockname()[1]
        self._stop.clear()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self) -> None:  # noqa: C901 - one framing loop
        assert self._tcp is not None
        while not self._stop.is_set():
            try:
                conn, addr = self._tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            peer_host = addr[0] if addr else "unknown"
            try:
                (length,) = struct.unpack(">I", _read_exact(conn, 4))
                if length > _MSG_SIZE_CAP:
                    continue
                body = _read_exact(conn, length)
                message = json.loads(body.decode("utf-8"))
            except (
                ConnectionError,
                ValueError,
                struct.error,
                UnicodeDecodeError,
                OSError,
            ):
                continue
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
            sender = message.pop("from", "unknown")
            kind = message.get("kind", "")
            if kind in ("heartbeat", "discover-ping", "bye"):
                self._note_heartbeat(sender, peer_host, message)
                if kind == "discover-ping":
                    # A peer is actively looking for us: answer now
                    # instead of making it wait for our next interval.
                    # Re-send our standing info (offer included), not a
                    # bare heartbeat — a bare reply would clobber the
                    # peer's view of our offer with an offer-less entry.
                    reply = dict(self._standing_info)
                    reply["kind"] = "heartbeat"
                    try:
                        self._push(reply)
                    except TransportUnavailable:
                        pass
                continue
            self._inbox.put((sender, message))

    def _note_heartbeat(self, sender: str, peer_host: str, message: Dict) -> None:
        if not sender or sender == self._node_id:
            return
        if message.get("kind") == "bye":
            with self._seen_lock:
                self._seen.pop(sender, None)
            return
        try:
            port = int(message["tcp_port"])
        except (KeyError, TypeError, ValueError):
            return
        entry: Dict = {
            "node_id": sender,
            "host": peer_host,
            "tcp_port": port,
            "ts": time.time(),
        }
        entry.update(message)
        with self._seen_lock:
            self._seen[sender] = entry

    # -- discovery ----------------------------------------------------

    def announce(self, info: Dict) -> None:
        if self._node_id is None:
            raise TransportUnavailable("bind() before announce()")
        if info.get("kind") != "discover-ping":
            # Standing info (heartbeat + offer) is what ping replies
            # re-send. A ping must never clobber it.
            self._standing_info = dict(info)
        self._push(info)

    def _push(self, info: Dict) -> None:
        if self._node_id is None:
            raise TransportUnavailable("bind() before announce()")
        payload = {
            "node_id": self._node_id,
            "tcp_port": self._tcp_port,
            "ts": time.time(),
        }
        payload.update(info)
        envelope = {"from": self._node_id}
        envelope.update(payload)
        raw = _pack(envelope)
        for host, port in list(self._known_peers):
            try:
                sock = socket.create_connection((host, port), timeout=1.0)
            except OSError:
                continue  # peer not up (yet) — heartbeats are lossy by design
            try:
                sock.sendall(raw)
            except OSError:
                pass
            finally:
                try:
                    sock.close()
                except OSError:
                    pass

    def discover(self, timeout: float = 1.0) -> List[Dict]:
        try:
            self.announce({"kind": "discover-ping"})
        except TransportUnavailable:
            pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.05)
        now = time.time()
        with self._seen_lock:
            return [
                dict(entry)
                for entry in self._seen.values()
                if now - float(entry.get("ts", 0)) <= self._registry_ttl
            ]

    # -- messaging ----------------------------------------------------

    def _peer_addr(self, node_id: str) -> Tuple[str, int]:
        with self._seen_lock:
            entry = self._seen.get(node_id)
        if entry is not None and (
            time.time() - float(entry.get("ts", 0)) <= self._registry_ttl
        ):
            return str(entry["host"]), int(entry["tcp_port"])
        raise TransportUnavailable(f"unknown peer {node_id!r}")

    def send(self, node_id: str, message: Dict) -> None:
        if self._node_id is None:
            raise TransportUnavailable("bind() before send()")
        host, port = self._peer_addr(node_id)
        envelope = {"from": self._node_id}
        envelope.update(message)
        raw = _pack(envelope)
        try:
            sock = socket.create_connection((host, port), timeout=5.0)
        except OSError:
            with self._seen_lock:
                self._seen.pop(node_id, None)
            raise TransportUnavailable(f"peer {node_id!r} unreachable") from None
        try:
            sock.sendall(raw)
        finally:
            sock.close()

    def capabilities(self) -> Dict:
        return {
            "lane": "lan",
            "discovery": (
                "direct-peer: heartbeats pushed to configured "
                "(host, port) peers; no multicast/mDNS"
            ),
            "messages": "TCP, length-prefixed JSON",
            "onion_routing": False,
            "external_reach": False,  # Gateway Law: fleet-internal only
            "limits": (
                "same LAN only; no NAT traversal; peers configured by "
                "IP — DHCP changes need add_peer() or a config edit"
            ),
        }


class DeepWebTransport(Transport):
    """Onion-style hidden-service lane — interface + contract, not a build.

    Chauncey's order: "even deep web." The fleet mesh gets a deep-web
    lane so fleet traffic can ride onion-style hidden services where
    the operator wants that protection.

    Honest scope: a real onion transport needs a running tor daemon
    (or equivalent) and hidden-service key management. The prototype
    ships the interface, the capability contract, and the exact
    integration point — ``bind`` against a tor control port, ``send``
    over ``.onion`` addresses — so a real implementation drops in
    later with zero changes to nodes, tasks, or the ledger.
    """

    TOR_CONTROL_PORT = 9051
    TOR_SOCKS_PORT = 9050

    def __init__(self, tor_control_port: int = TOR_CONTROL_PORT) -> None:
        self._tor_control_port = tor_control_port
        self._node_id: Optional[str] = None
        self._onion_address: Optional[str] = None

    def _unavailable(self, op: str) -> TransportUnavailable:
        return TransportUnavailable(
            f"DeepWebTransport.{op}: prototype interface only — needs a "
            f"running tor daemon on control port {self._tor_control_port}. "
            "No traffic is sent; nothing is silently downgraded to clearnet."
        )

    def bind(self, node_id: str) -> None:
        # Records intent; the real bind negotiates a hidden service
        # via the tor control port and stores the .onion address.
        self._node_id = node_id

    def announce(self, info: Dict) -> None:
        raise self._unavailable("announce")

    def send(self, node_id: str, message: Dict) -> None:
        raise self._unavailable("send")

    def recv(self, timeout: float = 1.0) -> Optional[Tuple[str, Dict]]:
        raise self._unavailable("recv")

    def discover(self, timeout: float = 1.0) -> List[Dict]:
        raise self._unavailable("discover")

    def capabilities(self) -> Dict:
        return {
            "lane": "deep-web",
            "status": "interface-only prototype",
            "onion_routing": "planned — requires tor daemon",
            "hidden_service": "planned — .onion address per node",
            "discovery": "planned — via hidden-service directory",
            "external_reach": False,  # Gateway Law holds on every lane
            "integration_point": (
                "bind(): authenticate to tor control port, ADD_ONION; "
                "send(): SOCKS5h to <peer>.onion; announce(): publish "
                "descriptor. Nothing above this class changes."
            ),
        }

    def close(self) -> None:
        self._node_id = None
        self._onion_address = None
