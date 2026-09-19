"""Tests for levi.automation.nodes — workflow node packs.

Hermetic: LEVI_HOME is redirected to a tmp dir (no user HOME writes),
webhook-out is exercised against a local in-test HTTP server, Google is
never touched.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from levi.automation import nodes
from levi.automation.nodes import FlowError


@pytest.fixture(autouse=True)
def hermetic_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# webhook-out
# ---------------------------------------------------------------------------


class _OKHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length)
        type(self).received.append(
            (
                self.path,
                body,
                self.headers.get("X-Test"),
                self.headers.get("X-Levi-Dedupe-Key"),
            )
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"delivered": true}')

    def log_message(self, *args):
        pass


class _FlakyHandler(BaseHTTPRequestHandler):
    hits = 0

    def do_POST(self):
        type(self).hits += 1
        if type(self).hits == 1:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"boom")
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"delivered": true}')

    def log_message(self, *args):
        pass


def _serve(handler_cls):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _node(url, **overrides):
    cfg = {
        "url": url,
        "method": "POST",
        "headers": {"X-Test": "1"},
        "body_template": '{"event":"{event.summary}","n":{n}}',
        "timeout_s": 5,
        "retries": 1,
    }
    cfg.update(overrides)
    return {"id": "w1", "kind": "webhook-out", "config": cfg}


def test_webhook_out_posts_rendered_body():
    _OKHandler.received = []
    server = _serve(_OKHandler)
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        ctx = {"event": {"summary": "hi"}, "n": 3}
        result = nodes.handle_webhook_out(_node(url), ctx, {"run_id": "r1"})
    finally:
        server.shutdown()
    assert result["ok"] is True
    assert result["output"]["status"] == 200
    assert result["output"]["attempts"] == 1
    assert "-> 200" in result["evidence"]
    path, body, x_test, dedupe = _OKHandler.received[0]
    assert path == "/hook"
    assert json.loads(body) == {"event": "hi", "n": 3}
    assert x_test == "1"
    assert dedupe == "levi-r1"


def test_webhook_out_retries_5xx_then_succeeds():
    _FlakyHandler.hits = 0
    server = _serve(_FlakyHandler)
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        result = nodes.handle_webhook_out(
            _node(url, retries=2, body_template=""), {}, {}
        )
    finally:
        server.shutdown()
    assert result["ok"] is True
    assert result["output"]["status"] == 200
    assert result["output"]["attempts"] == 2
    assert _FlakyHandler.hits == 2


def test_webhook_out_connection_failure_is_receipted():
    # Port 1 on loopback refuses connections; nothing real is contacted.
    result = nodes.handle_webhook_out(
        _node("http://127.0.0.1:1/hook", retries=1, timeout_s=2, body_template=""),
        {},
        {},
    )
    assert result["ok"] is False
    assert result["output"]["status"] is None
    assert result["output"]["attempts"] == 2
    assert "error" in result["output"]
    assert "failed after 2 attempt(s)" in result["evidence"]


def test_webhook_out_bad_config_refused():
    with pytest.raises(FlowError):
        nodes.handle_webhook_out({"id": "w", "config": {}}, {}, {})
    with pytest.raises(FlowError):
        nodes.handle_webhook_out({"id": "w", "config": {"url": "ftp://x/y"}}, {}, {})
    with pytest.raises(FlowError):
        nodes.handle_webhook_out(
            {"id": "w", "config": {"url": "http://x/y", "method": "GET"}}, {}, {}
        )


def test_webhook_out_unknown_placeholder_refused():
    result_cfg = _node("http://127.0.0.1:1/hook", body_template="{nope.missing}")
    with pytest.raises(FlowError):
        nodes.handle_webhook_out(result_cfg, {}, {})


def test_preview_webhook_out():
    line = nodes.preview_webhook_out(_node("https://example.com/hook"))
    assert line == "POST https://example.com/hook (timeout 5s, 1 retries)"


# ---------------------------------------------------------------------------
# python runner
# ---------------------------------------------------------------------------


def test_python_inline_hello_world():
    node = {
        "id": "p1",
        "kind": "python",
        "config": {"script": 'print("hello levi")', "timeout_s": 10},
    }
    result = nodes.handle_python(node, {}, {})
    assert result["ok"] is True
    assert result["output"]["exit_code"] == 0
    assert result["output"]["timed_out"] is False
    assert "hello levi" in result["output"]["stdout"]
    assert "exit 0" in result["evidence"]


def test_python_nonzero_exit_is_receipted():
    node = {
        "id": "p2",
        "kind": "python",
        "config": {"script": "import sys; sys.exit(3)", "timeout_s": 10},
    }
    result = nodes.handle_python(node, {}, {})
    assert result["ok"] is False
    assert result["output"]["exit_code"] == 3
    assert "exit 3" in result["evidence"]


def test_python_timeout_enforced():
    node = {
        "id": "p3",
        "kind": "python",
        "config": {"script": "import time; time.sleep(30)", "timeout_s": 1},
    }
    result = nodes.handle_python(node, {}, {})
    assert result["ok"] is False
    assert result["output"]["timed_out"] is True
    assert result["output"]["exit_code"] is None
    assert "timed out after 1s" in result["evidence"]


def test_python_sandbox_escape_blocked():
    with pytest.raises(FlowError):
        nodes.handle_python(
            {"id": "p", "config": {"script_path": "/etc/hostname"}}, {}, {}
        )
    with pytest.raises(FlowError):
        nodes.handle_python(
            {"id": "p", "config": {"script_path": "../../escape.py"}}, {}, {}
        )
    with pytest.raises(FlowError):
        nodes.handle_python(
            {"id": "p", "config": {"script": "x", "script_path": "y.py"}}, {}, {}
        )


def test_python_script_path_under_home_allowed(hermetic_home):
    scripts = hermetic_home / "automation" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "t.py").write_text('print("from file")\n', encoding="utf-8")
    node = {
        "id": "p4",
        "kind": "python",
        "config": {"script_path": "automation/scripts/t.py", "timeout_s": 10},
    }
    result = nodes.handle_python(node, {}, {})
    assert result["ok"] is True
    assert "from file" in result["output"]["stdout"]


def test_python_env_is_scrubbed(monkeypatch):
    monkeypatch.setenv("LEVI_SECRET_TEST", "should-not-leak")
    node = {
        "id": "p5",
        "kind": "python",
        "config": {
            "script": "import os; print('LEVI_SECRET_TEST' in os.environ)",
            "timeout_s": 10,
        },
    }
    result = nodes.handle_python(node, {}, {})
    assert result["ok"] is True
    assert "False" in result["output"]["stdout"]


def test_preview_python():
    node = {"id": "p", "config": {"script": "print('x')\nprint('y')", "timeout_s": 7}}
    assert nodes.preview_python(node) == "python: print('x') (timeout 7s)"
    node2 = {"id": "p", "config": {"script_path": "a/b.py"}}
    assert nodes.preview_python(node2) == "python: a/b.py (timeout 30s)"


# ---------------------------------------------------------------------------
# macro player
# ---------------------------------------------------------------------------


def test_macro_plays_canned_routine():
    from levi.automation.routines import RoutineStep, record_routine

    routine = record_routine(
        "canned",
        [
            RoutineStep(label="step one", note="n1"),
            RoutineStep(label="step two", note="n2"),
        ],
    )
    node = {
        "id": "m1",
        "kind": "macro",
        "config": {"routine_id": routine.id},
    }
    result = nodes.handle_macro(node, {}, {"dry_run": True, "responder": None})
    assert result["ok"] is True
    assert result["output"]["routine_id"] == routine.id
    assert len(result["output"]["step_notes"]) == 2
    assert "step 1 [note]: step one" in result["output"]["step_notes"][0]
    assert "macro" in result["evidence"]


def test_macro_unknown_routine_refused():
    with pytest.raises(FlowError):
        nodes.handle_macro({"id": "m", "config": {"routine_id": "nope-123"}}, {}, {})


def test_preview_macro_unknown():
    line = nodes.preview_macro({"id": "m", "config": {"routine_id": "nope-123"}})
    assert "would refuse" in line


# ---------------------------------------------------------------------------
# webhook-in registry
# ---------------------------------------------------------------------------


def test_webhook_in_register_match_miss(hermetic_home):
    # Outbound executor map must survive inbound registration untouched.
    webhooks_file = hermetic_home / "automation" / "webhooks.json"
    webhooks_file.parent.mkdir(parents=True, exist_ok=True)
    webhooks_file.write_text(
        json.dumps({"minion-1": "https://out.example/hook"}), encoding="utf-8"
    )

    reg = nodes.register_webhook("/hook/test", "flow-1")
    assert reg == {"path": "/hook/test", "flow_id": "flow-1"}

    raw = json.loads(webhooks_file.read_text(encoding="utf-8"))
    assert raw["minion-1"] == "https://out.example/hook"
    assert raw["_inbound"] == {"/hook/test": "flow-1"}

    event = nodes.match_webhook("/hook/test", {"a": 1})
    assert event == {
        "kind": "webhook",
        "source": "/hook/test",
        "payload": {"a": 1},
        "flow_id": "flow-1",
    }
    assert nodes.match_webhook("/hook/nope", {}) is None


def test_webhook_in_bad_path_refused():
    with pytest.raises(FlowError):
        nodes.register_webhook("no-leading-slash", "flow-1")
    with pytest.raises(FlowError):
        nodes.register_webhook("/a/../b", "flow-1")
    with pytest.raises(FlowError):
        nodes.register_webhook("/ok", "")


def test_webhook_in_unregister():
    nodes.register_webhook("/hook/gone", "flow-9")
    assert nodes.unregister_webhook("/hook/gone") is True
    assert nodes.match_webhook("/hook/gone", {}) is None
    assert nodes.unregister_webhook("/hook/gone") is False


def test_ensure_registered_returns_list():
    assert isinstance(nodes.ensure_registered(), list)
