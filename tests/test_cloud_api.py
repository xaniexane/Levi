"""Multi-user cloud API tests (hermetic).

Spins up :class:`levi.agent.server._AgentHandler` on 127.0.0.1 with an
ephemeral port, in-process. ``LEVI_CLOUD_DIR`` and ``HOME`` point at
tmp dirs so nothing touches the real user state.
"""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib import request as urlrequest
from urllib.error import HTTPError

import pytest

OWNER_TOKEN = "test-owner-token-0123456789abcdef"


@pytest.fixture()
def cloud_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(tmp_path / "cloud"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_AGENT_TOKEN", OWNER_TOKEN)
    return tmp_path


@pytest.fixture()
def server(cloud_env):
    from levi.agent.server import _AgentHandler
    from levi.cloud.ratelimit import RateLimiter

    # Save/restore shared class attrs (handler class is process-global).
    saved = {
        "token": _AgentHandler.token,
        "owner_token": _AgentHandler.owner_token,
        "rate_limiter": _AgentHandler.rate_limiter,
        "make_registry": _AgentHandler.make_registry,
    }
    _AgentHandler.token = OWNER_TOKEN
    _AgentHandler.owner_token = OWNER_TOKEN
    _AgentHandler.rate_limiter = RateLimiter(per_minute=10_000)
    _AgentHandler.make_registry = None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _AgentHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        for k, v in saved.items():
            setattr(_AgentHandler, k, v)


def _call(base, path, bearer=None, payload=None, method=None):
    """Returns (status, headers, body_dict). Never raises on HTTP errors."""
    data = None
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(base + path, data=data, headers=headers,
                             method=method or ("POST" if data else "GET"))
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read() or b"{}")
    except HTTPError as exc:
        raw = exc.read() or b"{}"
        try:
            body = json.loads(raw)
        except ValueError:
            body = {}
        return exc.code, dict(exc.headers), body


def _make_key(name="alice"):
    from levi.cloud import apikeys

    raw, record = apikeys.create_key(name)
    return raw, record


# -- key lifecycle ---------------------------------------------------------

def test_key_create_verify_revoke(cloud_env):
    from levi.cloud import apikeys

    raw, record = apikeys.create_key("alice")
    assert raw.startswith("levi_sk_")
    assert record["name"] == "alice"
    assert "key_hash" not in record

    # The store holds a hash, never the raw key.
    stored = json.loads((cloud_env / "cloud" / "keys.json").read_text())
    assert len(stored) == 1
    assert stored[0]["key_hash"] != raw
    assert raw not in json.dumps(stored)

    # Verification works, then revocation kills it.
    assert apikeys.find_key(raw)["name"] == "alice"
    assert apikeys.find_key("levi_sk_bogus") is None
    apikeys.revoke_key("alice")
    assert apikeys.find_key(raw) is None
    # Revoked keys stay as an audit trail.
    assert apikeys.list_keys()[0]["revoked"] is True


def test_key_create_duplicate_name_rejected(cloud_env):
    from levi.cloud import apikeys

    apikeys.create_key("alice")
    with pytest.raises(apikeys.KeyError):
        apikeys.create_key("alice")


def test_key_store_is_owner_only(cloud_env):
    import stat

    _make_key()
    mode = stat.S_IMODE((cloud_env / "cloud" / "keys.json").stat().st_mode)
    assert mode == 0o600


# -- auth ------------------------------------------------------------------

def test_healthz_is_open(server):
    status, _, body = _call(server, "/healthz")
    assert status == 200
    assert body["status"] == "ok"
    assert body["service"] == "levi-agent"
    assert body["version"]


def test_v1_requires_auth(server):
    status, _, body = _call(server, "/v1/tools")
    assert status == 401
    assert body["error"] == "unauthorized"


def test_bad_key_rejected(server, cloud_env):
    _make_key()
    status, _, body = _call(server, "/v1/tools", bearer="levi_sk_wrongwrongwrong")
    assert status == 401


def test_revoked_key_rejected(server, cloud_env):
    from levi.cloud import apikeys

    raw, _ = _make_key()
    apikeys.revoke_key("alice")
    status, _, body = _call(server, "/v1/tools", bearer=raw)
    assert status == 401


# -- tool profiles ---------------------------------------------------------

def test_cloud_registry_is_restricted_directly():
    from levi.cloud.profile import (
        CLOUD_SAFE_TOOLS,
        CLOUD_DENIED_TOOLS,
        build_cloud_registry,
    )

    reg = build_cloud_registry()
    names = {t.name for t in reg.list()}
    assert names == set(CLOUD_SAFE_TOOLS)
    # The dangerous tools are absent — no consent flag can reach them.
    for denied in ("shell_exec", "file_write", "file_edit", "file_read",
                   "memory_write", "delegate", "http_request", "web_fetch"):
        assert denied in CLOUD_DENIED_TOOLS
        assert reg.get(denied) is None


def test_owner_gets_full_registry_key_gets_restricted(server, cloud_env):
    raw, _ = _make_key()
    _, _, owner_body = _call(server, "/v1/tools", bearer=OWNER_TOKEN)
    _, _, key_body = _call(server, "/v1/tools", bearer=raw)
    owner_tools = {t["name"] for t in owner_body["tools"]}
    key_tools = {t["name"] for t in key_body["tools"]}
    assert "shell_exec" in owner_tools
    assert "file_write" in owner_tools
    assert "shell_exec" not in key_tools
    assert "file_write" not in key_tools
    assert "file_read" not in key_tools
    assert "memory_write" not in key_tools
    assert "delegate" not in key_tools
    assert "web_search" in key_tools
    assert "news_search" in key_tools


# -- rate limiting ---------------------------------------------------------

def test_rate_limit_429_trips(server, cloud_env):
    from levi.agent.server import _AgentHandler
    from levi.cloud.ratelimit import RateLimiter

    _AgentHandler.rate_limiter = RateLimiter(per_minute=3)
    raw, _ = _make_key()
    codes = [_call(server, "/v1/tools", bearer=raw)[0] for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    status, headers, body = _call(server, "/v1/tools", bearer=raw)
    assert status == 429
    assert body["error"] == "rate limit exceeded"
    assert "Retry-After" in headers


def test_owner_not_rate_limited(server, cloud_env):
    from levi.agent.server import _AgentHandler
    from levi.cloud.ratelimit import RateLimiter

    _AgentHandler.rate_limiter = RateLimiter(per_minute=1)
    codes = [_call(server, "/v1/tools", bearer=OWNER_TOKEN)[0] for _ in range(3)]
    assert codes == [200, 200, 200]


# -- metering --------------------------------------------------------------

def test_usage_is_metered(server, cloud_env):
    from levi.cloud import metering

    raw, record = _make_key()
    _call(server, "/v1/tools", bearer=raw)
    recs = metering.read_usage()
    assert len(recs) == 1
    rec = recs[0]
    assert rec["key_name"] == "alice"
    assert rec["key_prefix"] == record["prefix"]
    assert rec["endpoint"] == "/v1/tools"
    assert rec["ok"] is True
    # Raw keys never appear in the metering log.
    assert raw not in json.dumps(recs)


def test_usage_filter_by_key(server, cloud_env):
    from levi.cloud import metering

    raw_a, _ = _make_key("alice")
    raw_b, _ = _make_key("bob")
    _call(server, "/v1/tools", bearer=raw_a)
    _call(server, "/v1/tools", bearer=raw_b)
    assert [r["key_name"] for r in metering.read_usage(key_name="bob")] == ["bob"]


# -- chat sessions are namespaced per key ----------------------------------

def test_chat_sessions_namespaced_per_key(server, cloud_env):
    raw, record = _make_key()
    payload = {"session_id": "s1", "message": "hello", "provider": "local",
               "max_steps": 2}
    status, _, body = _call(server, "/v1/agent/chat", bearer=raw, payload=payload)
    assert status == 200
    assert body["session_id"].startswith("cloud_")
    assert body["session_id"].endswith("_s1")
    # The on-disk session file is namespaced too.
    sessions = list((cloud_env / "home" / ".levi" / "agent" / "sessions").glob("*.jsonl"))
    assert sessions, "expected a session file to be written"
    assert all(p.stem.startswith("cloud_") for p in sessions)
    # The owner keeps un-namespaced sessions.
    status, _, owner_body = _call(
        server, "/v1/agent/chat", bearer=OWNER_TOKEN, payload=payload)
    assert status == 200
    assert owner_body["session_id"] == "s1"
