"""LanTransport tests: cross-machine-style nodes over TCP, direct-peer discovery."""

import hashlib
import time

import pytest

from levi.mesh.node import MeshNode
from levi.mesh.resources import ResourceOffer, ResourcePool
from levi.mesh.tasks import TaskFarmer, Worker
from levi.mesh.transport import LanTransport, TransportUnavailable

LOOPBACK = "127.0.0.1"


def make_node(name, offer=None):
    transport = LanTransport(bind_host=LOOPBACK, bind_port=0, known_peers=[])
    node = MeshNode(device_id=f"dev-{name}", device_name=name, transport=transport)
    if offer is not None:
        offer = ResourceOffer(node_id=node.node_id, **offer).to_dict()
    node.join(offer=offer)
    return node, transport


def pair_up(na, ta, nb, tb):
    """Wire two bound nodes as known peers of each other."""
    ta.add_peer(LOOPBACK, tb._tcp_port)
    tb.add_peer(LOOPBACK, ta._tcp_port)


@pytest.fixture
def pair():
    na, ta = make_node("lan-a")
    nb, tb = make_node(
        "lan-b",
        offer={"cpu_units": 2.0, "memory_mb": 512.0, "storage_mb": 1024.0},
    )
    pair_up(na, ta, nb, tb)
    yield na, ta, nb, tb
    na.leave()
    nb.leave()


def test_lan_discovery_finds_peer(pair):
    na, _ta, nb, _tb = pair
    seen = {p["node_id"] for p in na.discover(timeout=1.5)}
    assert nb.node_id in seen
    seen_b = {p["node_id"] for p in nb.discover(timeout=1.5)}
    assert na.node_id in seen_b


def test_lan_discover_carries_offer(pair):
    na, _ta, nb, _tb = pair
    payloads = {p["node_id"]: p for p in na.discover(timeout=1.5)}
    assert payloads[nb.node_id]["offer"]["cpu_units"] == 2.0


def test_lan_send_recv(pair):
    na, _ta, nb, _tb = pair
    na.discover(timeout=1.0)  # learn nb's address first
    na.send(nb.node_id, {"type": "ping", "n": 7})
    incoming = nb.recv(timeout=2.0)
    assert incoming is not None
    sender, msg = incoming
    assert sender == na.node_id
    assert msg == {"type": "ping", "n": 7}


def test_lan_send_unknown_peer_raises(pair):
    na, _ta, _nb, _tb = pair
    with pytest.raises(TransportUnavailable):
        na.send("no-such-node", {"type": "ping"})


def test_lan_farm_across_nodes(pair):
    """Farmer on A, worker on B: a real task crosses the TCP lane."""
    na, _ta, nb, _tb = pair
    worker = Worker(nb).start()
    try:
        pool = ResourcePool()
        for p in na.discover(timeout=1.5):
            if "offer" in p:
                pool.advertise(ResourceOffer.from_dict(p["offer"]))
        assert nb.node_id in pool.node_ids()

        data = b"fleet task over the lan lane"
        result = TaskFarmer(na, pool).submit(
            data, "sha256_hex", num_chunks=4, replication=1, timeout=15.0
        )
        # chunk_bytes splits contiguously: recompute the expected hashes.
        n = 4
        base, rem = divmod(len(data), n)
        chunks, off = [], 0
        for i in range(n):
            size = base + (1 if i < rem else 0)
            chunks.append(data[off : off + size])
            off += size
        expected = [hashlib.sha256(c).hexdigest() for c in chunks]
        assert result["results"] == expected
    finally:
        worker.stop()


def test_lan_bye_removes_peer(pair):
    na, _ta, nb, tb = pair
    assert nb.node_id in {p["node_id"] for p in na.discover(timeout=1.5)}
    nb.leave()
    # nb announced "bye" on leave; a fresh discover window must not
    # resurrect it (its heartbeat is gone too).
    time.sleep(0.3)
    tb_announce_dead = True
    try:
        na.discover(timeout=1.0)
    except Exception:
        tb_announce_dead = False
    assert tb_announce_dead
    assert nb.node_id not in {p["node_id"] for p in na.discover(timeout=0.2)}


def test_lan_capabilities_lane():
    t = LanTransport()
    caps = t.capabilities()
    assert caps["lane"] == "lan"
    assert caps["external_reach"] is False  # Gateway Law holds on every lane
    t.close()
