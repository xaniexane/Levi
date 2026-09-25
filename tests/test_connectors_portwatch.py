"""Tests for the portwatch connector — the ear on local service ports.

Proofs for the laws in ``levi/connectors/portwatch.py``: observe-only
(bare connect, no bytes sent), honest baseline, edge-only events, and
the deny-closed input gates.
"""

import socket
import threading

import pytest

from levi.connectors import portwatch, registry
from levi.connectors.base import ConnectorError


class _Server:
    """A real listening TCP server on an ephemeral port."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            # Observe-only contract: the poll sends nothing; we accept
            # and close immediately without reading.
            try:
                conn.close()
            except OSError:
                pass

    def close(self):
        self._stop.set()
        self.sock.close()
        self._thread.join(timeout=2)


@pytest.fixture()
def server():
    srv = _Server()
    yield srv
    srv.close()


def _closed_port():
    """A port nothing is listening on."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _poll(**inputs):
    return registry.poll("portwatch", **inputs)


def test_portwatch_registers():
    ids = {c.id for c in registry.list()}
    assert "portwatch" in ids
    desc = registry.get("portwatch")
    assert desc.risk == "info"
    assert desc.poll is portwatch.poll_portwatch


def test_first_poll_emits_honest_baseline_up(server):
    events, state = _poll(host="127.0.0.1", port=server.port, state={})
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "baseline"
    assert ev["status"] == "up"
    assert ev["prev_status"] is None
    assert ev["host"] == "127.0.0.1"
    assert ev["port"] == server.port
    assert ev["latency_ms"] is not None
    assert state == {"status": "up"}


def test_first_poll_emits_honest_baseline_down():
    events, state = _poll(host="127.0.0.1", port=_closed_port(), state={})
    assert len(events) == 1
    assert events[0]["kind"] == "baseline"
    assert events[0]["status"] == "down"
    assert events[0]["latency_ms"] is None
    assert state == {"status": "down"}


def test_steady_status_is_silent(server):
    events, state = _poll(host="127.0.0.1", port=server.port, state={})
    assert events[0]["status"] == "up"
    events2, state2 = _poll(host="127.0.0.1", port=server.port, state=state)
    assert events2 == []
    assert state2 == {"status": "up"}


def test_flap_emits_exactly_one_event(server):
    events, state = _poll(host="127.0.0.1", port=server.port, state={})
    assert events[0]["status"] == "up"
    server.close()
    events2, state2 = _poll(
        host="127.0.0.1", port=server.port, state=state, timeout_sec=1
    )
    assert len(events2) == 1
    assert events2[0]["kind"] == "status_changed"
    assert events2[0]["status"] == "down"
    assert events2[0]["prev_status"] == "up"
    assert state2 == {"status": "down"}


def test_missing_inputs_refused():
    with pytest.raises(ConnectorError):
        _poll(port=80, state={})
    with pytest.raises(ConnectorError):
        _poll(host="127.0.0.1", state={})


def test_bad_host_refused():
    for bad in ("", "   ", 123, ["x"]):
        with pytest.raises(ConnectorError):
            _poll(host=bad, port=80, state={})


def test_bad_port_refused():
    for bad in (0, 65536, -1, "80", 80.5, True):
        with pytest.raises(ConnectorError):
            _poll(host="127.0.0.1", port=bad, state={})


def test_bad_timeout_refused():
    for bad in (0, -1, 31, "2", True):
        with pytest.raises(ConnectorError):
            _poll(host="127.0.0.1", port=80, timeout_sec=bad, state={})


def test_unknown_state_status_refused(server):
    with pytest.raises(ConnectorError):
        _poll(
            host="127.0.0.1",
            port=server.port,
            state={"status": "maybe"},
        )
    with pytest.raises(ConnectorError):
        _poll(host="127.0.0.1", port=server.port, state="up")
