"""Phase 3 liveq (B12) acceptance battery: T1-T7.

Offline: sockets are blocked for the whole file by the fixture below
(own tiny fixture; never imports the beginning team's offline module).
"""

import pytest

import socket

from levi.phase3.linda import LocalSpace
from levi.phase3.liveq import LiveQFault, LiveQHub, StubMemoryView


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("network disabled: offline test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# ---------------------------------------------------------------------------
# T1 freshness: 100 changes -> delivered by next boundary
# ---------------------------------------------------------------------------


def test_t1_freshness_100_changes():
    hub = LiveQHub()
    seen = []
    hub.register_query(
        lambda k, v: k.startswith("tgt"), lambda qid, facts: seen.extend(facts)
    )
    for i in range(100):
        hub.view.write_fact("tgt-%d" % i, i)
    assert seen == []  # nothing mid-cycle: the boundary pushes
    hub.boundary_flush()
    assert len(seen) == 100
    assert [f["value"] for f in seen] == list(range(100))


# ---------------------------------------------------------------------------
# T2 schema discipline: 200 msgs, half malformed -> 100/100, zero silent
# ---------------------------------------------------------------------------


def test_t2_schema_discipline_200():
    hub = LiveQHub()
    hub.create_port("p", {"kind": str, "n": int}, owner="m1")
    faults = 0
    for i in range(200):
        if i % 2 == 0:
            hub.send("p", {"kind": "k", "n": i})
        else:
            with pytest.raises(LiveQFault) as excinfo:
                # malformed: wrong type / missing field / extra shape
                bad = [
                    {"kind": "k"},  # missing n
                    {"kind": "k", "n": "not-an-int"},
                    {"kind": "k", "n": True},  # bool is not int: strict
                    "not-a-dict",
                ][i % 4]
                hub.send("p", bad)
            assert "schema violation" in excinfo.value.receipt["reason"]
            faults += 1
    assert faults == 100
    hub.boundary_flush()
    inbox = hub._ports["p"].inbox
    assert len(inbox) == 100
    assert [m["payload"]["n"] for m in inbox] == list(range(0, 200, 2))


# ---------------------------------------------------------------------------
# T3 delivery determinism: same sequence x30 -> identical order
# ---------------------------------------------------------------------------


def _t3_run():
    hub = LiveQHub()
    hub.create_port("b-port", {"v": int}, owner="m")
    hub.create_port("a-port", {"v": int}, owner="m")
    for i in range(10):
        hub.send("b-port", {"v": i})
        hub.send("a-port", {"v": i})
    hub.boundary_flush()
    return [(m["port_id"], m["payload"]["v"]) for m in hub.delivery_order()]


def test_t3_delivery_determinism_30_runs():
    baseline = _t3_run()
    # (cycle, port_id, seq): a-port sorts before b-port at every cycle
    assert baseline == [("a-port", i) for i in range(10)] + [
        ("b-port", i) for i in range(10)
    ]
    for _ in range(29):
        assert _t3_run() == baseline


# ---------------------------------------------------------------------------
# T4 boundary quantization: 500 events, all stamped at boundaries
# ---------------------------------------------------------------------------


def test_t4_boundary_quantization_500():
    hub = LiveQHub()
    hub.create_port("q", {"i": int}, owner="m")
    for i in range(500):
        hub.send("q", {"i": i})
        assert hub._queue[-1]["cycle"] == 0  # stamped at send-time cycle
    hub.boundary_flush()
    assert hub.cycle == 1
    for m in hub.delivery_order():
        assert isinstance(m["cycle"], int)
        assert m["cycle"] == 0  # quantized to a cycle, never finer
    # second wave stamps at cycle 1, delivers at boundary 2
    for i in range(10):
        hub.send("q", {"i": i})
    hub.boundary_flush()
    assert hub.cycle == 2
    assert all(m["cycle"] == 1 for m in hub.delivery_order()[500:])


# ---------------------------------------------------------------------------
# T5 query lifecycle: 50 register/update/close, all receipted, no leaks
# ---------------------------------------------------------------------------


def test_t5_query_lifecycle_50():
    hub = LiveQHub()
    for i in range(50):
        got = []
        receipt = hub.register_query(
            {"key": "k%d" % i}, lambda qid, facts, _got=got: _got.extend(facts)
        )
        assert receipt["op"] == "query_register"
        hub.view.write_fact("k%d" % i, i)
        hub.boundary_flush()
        assert len(got) == 1
        close_receipt = hub.close_query(receipt["query_id"])
        assert close_receipt["op"] == "query_close"
    assert hub.open_queries() == []
    regs = [r for r in hub.receipts() if r["op"] == "query_register"]
    closes = [r for r in hub.receipts() if r["op"] == "query_close"]
    assert len(regs) == 50 and len(closes) == 50


def test_close_unknown_query_faults():
    hub = LiveQHub()
    with pytest.raises(LiveQFault):
        hub.close_query("q-999")


# ---------------------------------------------------------------------------
# T6 port+tuple integration: 50 Linda outs travel through typed ports
# ---------------------------------------------------------------------------


def test_t6_port_tuple_integration_50():
    hub = LiveQHub()
    space = LocalSpace()
    space.declare_tag("task", 2)
    hub.create_port("tuple-bus", {"tag": str, "fields": list}, owner="coordinator")
    for i in range(50):
        hub.send("tuple-bus", {"tag": "task", "fields": ["scan", i]})
    hub.boundary_flush()
    for message in hub._ports["tuple-bus"].inbox:
        payload = message["payload"]
        space.out(payload["tag"], *payload["fields"])
    for i in range(50):
        got = space.in_(("task", "?job", "?n"))
        assert got["fields"] == ["scan", i]
    assert space._tuples == []


# ---------------------------------------------------------------------------
# Hooks + misc
# ---------------------------------------------------------------------------


def test_cycle_hook_fires_at_boundary():
    hub = LiveQHub()
    seen = []

    class Hook:
        def on_boundary(self, cycle):
            seen.append(cycle)

    hub.add_hook(Hook())
    hub.boundary_flush()
    hub.boundary_flush()
    assert seen == [1, 2]


def test_send_unknown_port_faults():
    hub = LiveQHub()
    with pytest.raises(LiveQFault) as excinfo:
        hub.send("nope", {"a": 1})
    assert excinfo.value.receipt["reason"] == "unknown port"


def test_duplicate_port_faults():
    hub = LiveQHub()
    hub.create_port("p", {"a": int}, owner="m")
    with pytest.raises(LiveQFault):
        hub.create_port("p", {"a": int}, owner="m")


def test_callable_schema():
    hub = LiveQHub()
    hub.create_port("p", lambda payload: payload.get("ok") is True, owner="m")
    hub.send("p", {"ok": True})
    with pytest.raises(LiveQFault):
        hub.send("p", {"ok": False})


def test_t7_offline_socket_blocked():
    with pytest.raises(RuntimeError):
        socket.socket()


def test_stub_memory_view_versions():
    view = StubMemoryView()
    view.write_fact("a", 1)
    view.write_fact("b", 2)
    assert view.current_version() == 2
    assert len(view.match(lambda k, v: True, since_version=0)) == 2
    assert len(view.match(lambda k, v: True, since_version=1)) == 1
    assert view.match({"key": "a"}, since_version=0)[0]["value"] == 1
