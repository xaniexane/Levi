"""Hub API + CLI entrypoint tests — real HTTP on localhost, hermetic."""

import json
import urllib.error
import urllib.request

import pytest

from levi.hub import api as hub_api
from levi.hub import auth
from levi.hub.__main__ import main as hub_main


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def server(hubdir):
    srv, thread = hub_api.serve_in_thread("127.0.0.1", 0)
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    thread.join(timeout=5)


def _call(base, method, path, body=None, token=None, raw=False):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode()
            if raw:
                return r.status, text
            return r.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def test_index_and_status_open(server):
    code, text = _call(server, "GET", "/", raw=True)
    assert code == 200 and "<title>Hub" in text
    code, body = _call(server, "GET", "/api/status")
    assert code == 200 and body["ok"] is True
    assert code == 200 and body["ok"] is True


def test_auth_wall_and_login(server):
    code, body = _call(server, "GET", "/api/hitl/pending")
    assert code == 401
    auth.register("cj", "test-pass-1")
    code, body = _call(
        server, "POST", "/api/auth/login", {"username": "cj", "password": "test-pass-1"}
    )
    assert code == 200 and body["token"]
    code, body = _call(server, "GET", "/api/hitl/pending", token=body["token"])
    assert code == 200 and body["ok"] is True


def test_hitl_roundtrip_over_http(server):
    auth.register("cj", "test-pass-1")
    _, login = _call(
        server, "POST", "/api/auth/login", {"username": "cj", "password": "test-pass-1"}
    )
    tok = login["token"]
    code, body = _call(
        server, "POST", "/api/hitl/decide", {"id": 999, "approved": True}, token=tok
    )
    assert code == 400  # no such request — honest error, not crash


def test_heartbeat_over_http(server):
    auth.register("cj", "test-pass-1")
    _, login = _call(
        server, "POST", "/api/auth/login", {"username": "cj", "password": "test-pass-1"}
    )
    code, body = _call(server, "GET", "/api/agent/heartbeat", token=login["token"])
    assert code == 200 and body["ok"] is True


def test_cli_status_and_help(hubdir, capsys):
    assert hub_main(["status"]) == 0
    out = capsys.readouterr().out
    assert "levi.hub" in out
    with pytest.raises(SystemExit) as e:
        hub_main(["--help"])
    assert e.value.code == 0


def test_cli_agent_chat_and_alpha_catalog(hubdir, capsys):
    assert hub_main(["chat", "hello"]) == 0
    assert hub_main(["alpha", "catalog"]) == 0
