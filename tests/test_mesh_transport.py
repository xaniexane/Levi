"""Mesh transport tests: discovery, messaging, lane pluggability."""

import time

import pytest

from levi.mesh.node import MeshNode, derive_node_id
from levi.mesh.transport import (
    DeepWebTransport,
    LocalTransport,
    Transport,
    TransportUnavailable,
)


def make_node(name, rendezvous_dir, **kw):
    return MeshNode(
        device_id=f"dev-{name}",
        device_name=name,
        transport=LocalTransport(rendezvous_dir=rendezvous_dir),
        **kw,
    )


@pytest.fixture
def rdv(tmp_path):
    return tmp_path / "rendezvous"


def test_derive_node_id_deterministic_and_bound():
    a = derive_node_id("dev-1", "phone")
    assert a == derive_node_id("dev-1", "phone")
    assert a != derive_node_id("dev-2", "phone")
    assert a != derive_node_id("dev-1", "tablet")
    assert len(a) == 32
    with pytest.raises(ValueError):
        derive_node_id("", "phone")


def test_discovery_two_nodes(rdv):
    a = make_node("a", rdv, heartbeat_interval=0.1)
    b = make_node("b", rdv, heartbeat_interval=0.1)
    a.join()
    b.join()
    try:
        seen = b.discover(timeout=1.5)
        ids = {p["node_id"] for p in seen}
        assert a.node_id in ids
    finally:
        a.leave()
        b.leave()


def test_send_recv_roundtrip(rdv):
    a = make_node("a2", rdv, heartbeat_interval=10)
    b = make_node("b2", rdv, heartbeat_interval=10)
    a.join()
    b.join()
    try:
        b.discover(timeout=1.0)
        a.send(b.node_id, {"type": "ping", "n": 7})
        got = b.recv(timeout=3.0)
        assert got is not None
        sender, msg = got
        assert sender == a.node_id
        assert msg["n"] == 7
    finally:
        a.leave()
        b.leave()


def test_send_unknown_peer_raises(rdv):
    a = make_node("a3", rdv, heartbeat_interval=10)
    a.join()
    try:
        with pytest.raises(TransportUnavailable):
            a.send("no-such-node", {"type": "ping"})
    finally:
        a.leave()


def test_heartbeat_carries_offer(rdv):
    a = make_node("a4", rdv, heartbeat_interval=0.1)
    b = make_node("b4", rdv, heartbeat_interval=0.1)
    a.join(offer={"cpu_units": 2.0})
    b.join()
    try:
        seen = {p["node_id"]: p for p in b.discover(timeout=1.5)}
        assert seen[a.node_id]["offer"] == {"cpu_units": 2.0}
    finally:
        a.leave()
        b.leave()


class InMemoryTransport(Transport):
    """Proves the abstraction: MeshNode runs on a non-socket lane."""

    _bus = {}  # node_id -> InMemoryTransport

    def __init__(self):
        self._node_id = None
        self._inbox = []

    def bind(self, node_id):
        self._node_id = node_id
        InMemoryTransport._bus[node_id] = self

    def announce(self, info):
        pass

    def send(self, node_id, message):
        peer = InMemoryTransport._bus.get(node_id)
        if peer is None:
            raise TransportUnavailable("unknown peer")
        env = {"from": self._node_id}
        env.update(message)
        peer._inbox.append((env.pop("from"), env))

    def recv(self, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._inbox:
                return self._inbox.pop(0)
            time.sleep(0.01)
        return None

    def discover(self, timeout=1.0):
        return [
            {"node_id": nid} for nid in InMemoryTransport._bus if nid != self._node_id
        ]

    def capabilities(self):
        return {"lane": "in-memory-test"}

    def close(self):
        InMemoryTransport._bus.pop(self._node_id, None)


def test_concurrent_announce_no_tmp_race(rdv, tmp_path):
    """Heartbeat + discover threads announcing at once must not collide."""
    import threading

    node = make_node("race", rdv, heartbeat_interval=10)
    node.join()
    errors = []

    def hammer():
        try:
            for _ in range(30):
                node.heartbeat()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert not errors, errors[:1]
        assert (rdv / f"{node.node_id}.json").exists()
    finally:
        node.leave()


def test_transport_pluggable_mock_lane():
    InMemoryTransport._bus.clear()
    a = MeshNode("dev-ma", "ma", InMemoryTransport())
    b = MeshNode("dev-mb", "mb", InMemoryTransport())
    a.join()
    b.join()
    try:
        a.send(b.node_id, {"type": "hello"})
        sender, msg = b.recv(timeout=2.0)
        assert sender == a.node_id and msg["type"] == "hello"
        assert {p["node_id"] for p in a.discover()} == {b.node_id}
    finally:
        a.leave()
        b.leave()


def test_mesh_imports_no_external_network_clients():
    """Gateway Law: the mesh is fleet-internal — no HTTP/external clients."""
    import pathlib
    import levi.mesh as m

    pkg = pathlib.Path(m.__file__).parent
    banned = (
        "import urllib",
        "import requests",
        "import httpx",
        "from urllib",
        "from requests",
        "from httpx",
        "import http.client",
        "from http.client",
    )
    for path in sorted(pkg.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for snippet in banned:
            assert snippet not in text, (path.name, snippet)


def test_deep_web_transport_is_interface_only():
    d = DeepWebTransport()
    d.bind("some-node")
    caps = d.capabilities()
    assert caps["lane"] == "deep-web"
    assert caps["onion_routing"].startswith("planned")
    assert "tor" in caps["integration_point"].lower()
    for op in (
        lambda: d.send("x", {}),
        lambda: d.recv(0.1),
        lambda: d.announce({}),
        lambda: d.discover(0.1),
    ):
        with pytest.raises(TransportUnavailable):
            op()
    # Gateway Law holds on every lane, even the planned one.
    assert caps["external_reach"] is False
    assert LocalTransport().capabilities()["external_reach"] is False
