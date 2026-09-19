"""Mesh node — identity bound to the Cybrus device identity.

A node's identity is DERIVED, not invented: ``node_id`` is a stdlib
sha256 over the Cybrus-enrolled device id and name, namespaced to the
mesh. No new crypto, no new key material — the device's Cybrus
enrollment is the root of trust.

Lifecycle: ``join()`` binds the transport and starts heartbeats;
``leave()`` stops heartbeats and releases the transport.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Dict, Optional

from .transport import Transport

NODE_ID_LEN = 32
_DEFAULT_HEARTBEAT_INTERVAL = 5.0


def derive_node_id(device_id: str, device_name: str) -> str:
    """Deterministic node id from a Cybrus device enrollment.

    ``device_id``/``device_name`` are the values enrolled in
    ``levi.cybrus.devices.DeviceTrust``. The derivation is a plain
    namespaced sha256 — stdlib only, no invented crypto.
    """
    device_id = (device_id or "").strip()
    device_name = (device_name or "").strip()
    if not device_id:
        raise ValueError("device_id must be a non-empty string")
    material = f"levi-mesh-v1:{device_id}:{device_name}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:NODE_ID_LEN]


class MeshNode:
    """One fleet device on the mesh."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        transport: Transport,
        heartbeat_interval: float = _DEFAULT_HEARTBEAT_INTERVAL,
    ) -> None:
        self.device_id = device_id
        self.device_name = device_name
        self.node_id = derive_node_id(device_id, device_name)
        self.transport = transport
        self._heartbeat_interval = heartbeat_interval
        self._stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._joined = False
        self._offer: Optional[Dict] = None

    # -- lifecycle ----------------------------------------------------

    def join(self, offer: Optional[Dict] = None) -> "MeshNode":
        """Bind the transport and start heartbeating. Idempotent."""
        if self._joined:
            return self
        self.transport.bind(self.node_id)
        self._offer = offer
        self._stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()
        self.heartbeat()
        self._joined = True
        return self

    def leave(self) -> None:
        """Stop heartbeats, announce departure, release the transport."""
        if not self._joined:
            return
        self._stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None
        try:
            self.transport.announce({"kind": "bye", "node_id": self.node_id})
        except Exception:
            pass
        self.transport.close()
        self._joined = False

    def heartbeat(self) -> None:
        """One presence announcement (also carries the resource offer)."""
        info: Dict = {"kind": "heartbeat", "device_name": self.device_name}
        if self._offer is not None:
            info["offer"] = self._offer
        self.transport.announce(info)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self._heartbeat_interval):
            try:
                self.heartbeat()
            except Exception:
                continue

    # -- messaging ----------------------------------------------------

    def send(self, node_id: str, message: Dict) -> None:
        self.transport.send(node_id, message)

    def recv(self, timeout: float = 1.0):
        return self.transport.recv(timeout)

    def discover(self, timeout: float = 1.0):
        return self.transport.discover(timeout)

    @property
    def joined(self) -> bool:
        return self._joined

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"MeshNode({self.node_id[:8]}…)"
