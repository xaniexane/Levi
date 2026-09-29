"""beacon — UDP-broadcast presence with signed, expiring tokens.

Stdlib only (socket, json, hmac, hashlib, time, threading, secrets).

Design notes:
- The broadcast target defaults to ``255.255.255.255`` (LAN broadcast);
  tests use ``127.0.0.1`` for hermetic loopback. The send path never
  targets routable internet addresses — ``_assert_local_target`` refuses
  anything that isn't broadcast or loopback/private range.
- The signing key is 32 random bytes generated once into
  ``~/.levi/streetpass/key`` (dir 0700, file 0600) or supplied by the
  caller. No keyring lookup happens over the network; the key never
  leaves the machine.
- The listener thread only accepts tokens that verify, have not
  expired, and carry a plausible issued-at. Everything else is dropped.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

from . import HOME_DIRNAME, PresenceToken, StreetPassError

__all__ = [
    "sign_token",
    "verify_token",
    "load_or_create_key",
    "Beacon",
    "Listener",
    "DEFAULT_PORT",
    "DEFAULT_TTL",
]

DEFAULT_PORT = 41819
DEFAULT_TTL = 300.0  # a presence announcement lives five minutes


def _home() -> Path:
    home = Path.home() / ".levi" / HOME_DIRNAME
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def load_or_create_key() -> bytes:
    """Return the keeper's streetpass signing key (32 bytes), creating it."""
    path = _home() / "key"
    if path.is_file():
        data = path.read_bytes()
        if len(data) == 32:
            return data
        raise StreetPassError("corrupt streetpass key at %s" % path)
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def _assert_local_target(host: str) -> None:
    """Refuse non-local beacon targets — this protocol never crosses the LAN."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        raise StreetPassError("beacon target must be a literal IP: %r" % host)
    if addr.is_multicast:
        raise StreetPassError("beacon target must not be multicast: %s" % host)
    if not (addr.is_private or addr.is_loopback or str(addr) == "255.255.255.255"):
        raise StreetPassError("beacon target must be local (LAN/private/loopback): %s" % host)


def sign_token(key: bytes, name: str, tags: list, ttl: float = DEFAULT_TTL,
               now: float | None = None) -> str:
    """Mint a signed presence token. Only declared fields go on the wire."""
    if not name or not name.strip():
        raise StreetPassError("presence name must be non-empty")
    name = name.strip()
    if len(name) > 64:
        raise StreetPassError("presence name too long (>64 chars)")
    clean_tags = sorted({str(t).strip() for t in tags if str(t).strip()})[:16]
    payload = {
        "name": name,
        "tags": clean_tags,
        "issued": float(now if now is not None else time.time()),
        "ttl": float(ttl),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(key, body, hashlib.sha256).hexdigest()
    return body.decode() + "." + sig


def verify_token(key: bytes, wire: str, now: float | None = None) -> PresenceToken | None:
    """Verify a wire token; return None for anything unverifiable.

    Deny-closed: malformed, foreign-signed, future-dated, or expired
    tokens all return None. Unknown fields are ignored, never stored.
    """
    now = now if now is not None else time.time()
    try:
        body, sig = wire.rsplit(".", 1)
    except ValueError:
        return None
    expect = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    try:
        name = str(payload["name"])
        tags = tuple(str(t) for t in payload.get("tags", []))
        issued = float(payload["issued"])
        ttl = float(payload["ttl"])
    except (KeyError, TypeError, ValueError):
        return None
    if not name or ttl <= 0 or ttl > 3600:
        return None
    if issued > now + 60:  # not from the future
        return None
    if issued + ttl < now:  # already dead
        return None
    return PresenceToken(name, tags, issued, ttl)


class Beacon:
    """Periodically broadcast the keeper's signed presence."""

    def __init__(self, key: bytes, name: str, tags: list | None = None,
                 target: str = "255.255.255.255", port: int = DEFAULT_PORT,
                 interval: float = 30.0, ttl: float = DEFAULT_TTL):
        _assert_local_target(target)
        self.key = key
        self.name = name
        self.tags = list(tags or [])
        self.target = target
        self.port = port
        self.interval = interval
        self.ttl = ttl
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def announce(self) -> None:
        """Send one presence announcement right now."""
        wire = sign_token(self.key, self.name, self.tags, ttl=self.ttl)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            if self.target == "255.255.255.255":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(wire.encode(), (self.target, self.port))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="streetpass-beacon")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.announce()
            except OSError:
                pass  # a failed announcement is not fatal; retry next tick

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)


class Listener:
    """Collect verified, unexpired neighbors from the LAN."""

    def __init__(self, key: bytes, port: int = DEFAULT_PORT,
                 bind: str = "0.0.0.0"):
        self.key = key
        self.port = port
        self.bind = bind
        self._neighbors: dict[str, PresenceToken] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="streetpass-listener")
        self._thread.start()

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except OSError:
                pass
            sock.bind((self.bind, self.port))
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    data, _addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                token = verify_token(self.key, data.decode(errors="replace"))
                if token is None:
                    continue
                with self._lock:
                    self._neighbors[token.name] = token

    def neighbors(self, now: float | None = None) -> list[PresenceToken]:
        """Current unexpired neighbors; expiry sweep happens here."""
        now = now if now is not None else time.time()
        with self._lock:
            live = {n: t for n, t in self._neighbors.items()
                    if t.issued + t.ttl >= now}
            self._neighbors = live
            return list(live.values())

    def shared_tags(self, token: PresenceToken, mine: list) -> list[str]:
        """Opt-in matching: which of the keeper's tags a neighbor shares."""
        return sorted(set(token.tags) & set(mine))

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
