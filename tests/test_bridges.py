"""Tests for the Chrome host and MacroDroid bridges.

Hermetic: loopback HTTP only for the outbound POST test, LEVI_HOME not
touched by the chrome-host tests. The workflow engine's dispatch surface
is faked via sys.modules injection where needed.
"""

import io
import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from levi.automation.bridges.chrome_host import (
    FrameError,
    encode_message,
    handle_message,
    read_message,
)
from levi.automation.bridges.macrodroid import (
    build_macrodroid_event,
    fire_macrodroid,
    macrodroid_event,
)


# ---------------------------------------------------------------------------
# Chrome host framing
# ---------------------------------------------------------------------------


def test_frame_round_trip():
    msg = {"type": "ping", "payload": {"a": [1, 2, 3]}}
    buf = io.BytesIO(encode_message(msg))
    assert read_message(buf) == msg


def test_read_message_clean_eof():
    assert read_message(io.BytesIO(b"")) is None


def test_read_message_truncated_payload():
    import struct

    buf = io.BytesIO(struct.pack("<I", 20) + b'{"type":')
    with pytest.raises(FrameError):
        read_message(buf)


def test_read_message_non_object_payload():
    import struct

    payload = b"[1, 2, 3]"
    buf = io.BytesIO(struct.pack("<I", len(payload)) + payload)
    with pytest.raises(FrameError):
        read_message(buf)


def test_read_message_not_json():
    import struct

    payload = b"not-json{{{"
    buf = io.BytesIO(struct.pack("<I", len(payload)) + payload)
    with pytest.raises(FrameError):
        read_message(buf)


def test_handle_ping():
    resp = handle_message({"type": "ping"})
    assert resp == {"ok": True, "type": "pong"}


def test_handle_unknown_type_deny_closed():
    resp = handle_message({"type": "self-destruct"})
    assert resp["ok"] is False
    assert "unknown message type" in resp["error"]


def test_handle_non_dict_message():
    resp = handle_message([1])
    assert resp["ok"] is False


def _fake_engine(monkeypatch, results=("run-1",)):
    fake = types.ModuleType("levi.automation.flows")
    fake.dispatch_trigger = lambda event: list(results)
    monkeypatch.setitem(sys.modules, "levi.automation.flows", fake)
    return fake


def test_fire_workflow_dispatches(monkeypatch):
    fake = _fake_engine(monkeypatch)
    seen = []
    fake.dispatch_trigger = lambda event: seen.append(event) or ["fired"]
    resp = handle_message(
        {"type": "fire-workflow", "flow_id": "nightly", "trigger": {"when": "22:00"}}
    )
    assert resp["ok"] is True
    assert resp["results"] == ["fired"]
    event = seen[0]
    assert event["kind"] == "webhook"
    assert event["source"] == "chrome-extension"
    assert event["payload"]["flow_id"] == "nightly"


def test_fire_workflow_engine_missing_is_clean_refusal(monkeypatch):
    monkeypatch.delitem(sys.modules, "levi.automation.flows", raising=False)
    resp = handle_message({"type": "fire-workflow", "flow_id": "x"})
    assert resp["ok"] is False
    assert "not yet available" in resp["error"]


# ---------------------------------------------------------------------------
# MacroDroid inbound
# ---------------------------------------------------------------------------


def test_build_macrodroid_event():
    event = build_macrodroid_event("/sms", {"from": "+1555", "text": "hi"})
    assert event == {
        "kind": "webhook",
        "source": "macrodroid:sms",
        "payload": {"from": "+1555", "text": "hi"},
    }


def test_build_macrodroid_event_none_payload():
    assert build_macrodroid_event("ping", None)["payload"] == {}


def test_build_macrodroid_event_bad_path():
    with pytest.raises(ValueError):
        build_macrodroid_event("  ", {})


def test_build_macrodroid_event_bad_payload():
    with pytest.raises(TypeError):
        build_macrodroid_event("sms", "not-a-dict")


def test_macrodroid_event_dispatches(monkeypatch):
    fake = _fake_engine(monkeypatch)
    seen = []
    fake.dispatch_trigger = lambda event: seen.append(event)
    event = macrodroid_event("sms", {"text": "hello"})
    assert event["source"] == "macrodroid:sms"
    assert seen == [event]


def test_macrodroid_event_engine_missing_raises(monkeypatch):
    monkeypatch.delitem(sys.modules, "levi.automation.flows", raising=False)
    with pytest.raises(RuntimeError, match="not yet available"):
        macrodroid_event("sms", {})


# ---------------------------------------------------------------------------
# MacroDroid outbound (loopback HTTP)
# ---------------------------------------------------------------------------


class _HookHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(
            {
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )
        if self.path == "/fail":
            self.send_response(500)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ack": true}')

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture()
def hook_server():
    _HookHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=5)


def test_fire_macrodroid_ok(hook_server):
    result = fire_macrodroid(f"{hook_server}/hook", {"event": "ping", "n": 2})
    assert result["ok"] is True
    assert result["status"] == 200
    hit = _HookHandler.received[-1]
    assert hit["content_type"] == "application/json"
    assert json.loads(hit["body"]) == {"event": "ping", "n": 2}


def test_fire_macrodroid_http_error(hook_server):
    result = fire_macrodroid(f"{hook_server}/fail", {"event": "ping"})
    assert result["ok"] is False
    assert result["status"] == 500


def test_fire_macrodroid_unreachable():
    result = fire_macrodroid("http://127.0.0.1:1/nope", {"event": "ping"})
    assert result["ok"] is False
    assert result["status"] is None
    assert "evidence" in result


def test_fire_macrodroid_bad_scheme():
    with pytest.raises(ValueError):
        fire_macrodroid("ftp://example.com/hook", {})


def test_fire_macrodroid_bad_payload():
    with pytest.raises(TypeError):
        fire_macrodroid("http://127.0.0.1:1/hook", "nope")
