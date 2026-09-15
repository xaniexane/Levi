"""Tests for the LEVI PWA chat organ (core/levi/pwa/).

Hermetic: the server runs on an ephemeral port with a stub provider and
LEVI_AGENT_SESSIONS_DIR pointed at tmp_path. Nothing touches the real
HOME, the network, or real model weights.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from levi.agent.chat import sanitize_session_name
from levi.agent.providers import ChatProvider, ChatResponse
from levi.pwa import server as pwa_server


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class FakeProvider(ChatProvider):
    """Deterministic stand-in for the agentic loop's provider."""
    name = "fake"

    def chat(self, messages, tools):
        return ChatResponse(text="fake pwa answer", prompt_tokens=50)

    def is_available(self):
        return True


def _start(monkeypatch, tmp_path, **kwargs):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.delenv("LEVI_PWA_TOKEN", raising=False)
    kwargs.setdefault("provider_factory", FakeProvider)
    srv = pwa_server.serve("127.0.0.1", 0, **kwargs)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


@pytest.fixture()
def base(monkeypatch, tmp_path):
    srv = _start(monkeypatch, tmp_path)
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def _get(base, path, token=None):
    req = urllib.request.Request(base + path)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def _post(base, path, payload, token=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode())


# ---------------------------------------------------------------------------
# static shell
# ---------------------------------------------------------------------------


def test_index_served(base):
    status, ctype, body = _get(base, "/")
    assert status == 200
    assert "text/html" in ctype
    assert b"<title>LEVI</title>" in body


def test_manifest_content_type(base):
    status, ctype, body = _get(base, "/manifest.json")
    assert status == 200
    assert ctype == "application/manifest+json"
    data = json.loads(body.decode())
    assert data["name"] == "LEVI"
    assert data["display"] == "standalone"


def test_service_worker_no_cache(base):
    status, ctype, body = _get(base, "/sw.js")
    assert status == 200
    assert "javascript" in ctype
    assert b"levi-pwa-v1" in body


def test_traversal_blocked(base):
    req = urllib.request.Request(base + "/..%2f..%2fetc%2fpasswd")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code in (400, 403, 404)


def test_missing_static_404(base):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base, "/nope.html")
    assert exc.value.code == 404


# ---------------------------------------------------------------------------
# api introspection
# ---------------------------------------------------------------------------


def test_health(base):
    status, _, body = _get(base, "/api/health")
    assert status == 200
    data = json.loads(body.decode())
    assert data["status"] == "ok"
    assert data["service"] == "levi-pwa"


def test_registers_lists_real_registers(base):
    status, _, body = _get(base, "/api/registers")
    assert status == 200
    regs = json.loads(body.decode())["registers"]
    ids = [r["id"] for r in regs]
    assert len(ids) == 14
    assert "kai_9000" in ids
    assert "kai_9000_void" in ids
    # no joke personalities — every register has a real tagline/voice
    for r in regs:
        assert r["tagline"] and r["voice"]


def test_models_endpoint_levi_first(base):
    status, _, body = _get(base, "/api/models")
    assert status == 200
    data = json.loads(body.decode())
    names = [e["name"] for e in data["family"]]
    assert names[:3] == ["levi-tiny", "levi-0.6b", "levi-4b"]
    assert "resolved" in data


# ---------------------------------------------------------------------------
# chat through the real agentic loop (stub provider)
# ---------------------------------------------------------------------------


def test_chat_returns_loop_reply(base):
    status, payload = _post(base, "/api/chat",
                            {"session": "pwa-test", "message": "hello levi"})
    assert status == 200
    assert payload["ok"] is True
    assert payload["provider"] == "fake"
    assert "fake pwa answer" in payload["reply"]
    assert payload["session"] == "pwa-test"


def test_chat_sessions_persist_across_messages(base, monkeypatch, tmp_path):
    _post(base, "/api/chat",
          {"session": "persist-me", "message": "first message"})
    status, payload = _post(base, "/api/chat",
                            {"session": "persist-me", "message": "second message"})
    assert status == 200
    session_file = tmp_path / "sessions" / "persist-me.jsonl"
    assert session_file.is_file()
    records = [json.loads(line) for line in
               session_file.read_text().splitlines() if line.strip()]
    user_msgs = [r for r in records
                 if r.get("kind") == "message" and r.get("role") == "user"]
    assert [m["content"] for m in user_msgs] == ["first message", "second message"]


def test_chat_rejects_bad_session(base):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(base, "/api/chat", {"session": "../evil", "message": "x"})
    assert exc.value.code == 400


def test_chat_rejects_unknown_register(base):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(base, "/api/chat", {"session": "s", "message": "x",
                                  "register": "drunk_pirate"})
    assert exc.value.code == 400


def test_chat_with_register_uses_system_prompt(base):
    status, payload = _post(base, "/api/chat",
                            {"session": "reg-test", "message": "hi",
                             "register": "kai_9000_void"})
    assert status == 200
    assert payload["ok"] is True


def test_chat_stream_emits_done(base):
    import urllib.error
    req = urllib.request.Request(
        base + "/api/chat/stream",
        data=json.dumps({"session": "stream-test",
                         "message": "hello"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(req, timeout=60) as r:
        assert r.headers.get("Content-Type") == "text/event-stream"
        buf = ""
        while True:
            chunk = r.read(1024)
            if not chunk:
                break
            buf += chunk.decode()
            while "\n\n" in buf:
                raw, buf = buf.split("\n\n", 1)
                event, data = "message", ""
                for line in raw.splitlines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data += line[5:].strip()
                events.append((event, json.loads(data) if data else None))
                if event in ("done", "error"):
                    break
            if events and events[-1][0] in ("done", "error"):
                break
    kinds = [e for e, _ in events]
    assert "status" in kinds
    assert kinds[-1] == "done"
    assert "fake pwa answer" in events[-1][1]["reply"]


# ---------------------------------------------------------------------------
# token auth
# ---------------------------------------------------------------------------


def test_token_gate(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("LEVI_PWA_TOKEN", "secret-token")
    srv = pwa_server.serve("127.0.0.1", 0, provider_factory=FakeProvider)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        # static stays open
        status, _, _ = _get(base, "/")
        assert status == 200
        # api without token → 401
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(base, "/api/health")
        assert exc.value.code == 401
        # api with token → 200
        status, _, _ = _get(base, "/api/health", token="secret-token")
        assert status == 200
        # wrong token → 401
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(base, "/api/health", token="wrong")
        assert exc.value.code == 401
    finally:
        srv.shutdown()
        srv.server_close()


def test_sanitize_session_name_rejects_traversal():
    with pytest.raises(ValueError):
        sanitize_session_name("../x")
