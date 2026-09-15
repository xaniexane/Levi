"""MCP server provider tests (hermetic, stdlib-only).

Covers the JSON-RPC protocol surface, the tool mapping, both security
profiles, and both transports (stdio over a real subprocess, HTTP over
a real localhost socket).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from levi.mcp.protocol import (
    PROTOCOL_VERSION,
    build_http_server,
    build_owner_server,
)
from levi.mcp.transports import _Handler, _MCPHTTPState


# ---------------------------------------------------------------------------
# Protocol surface (in-process)
# ---------------------------------------------------------------------------


def test_mcp_initialize_handshake():
    server = build_owner_server()
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "levi"
    assert "tools" in result["capabilities"] and "resources" in result["capabilities"]


def test_mcp_notification_returns_no_response():
    server = build_owner_server()
    assert (
        server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    )
    assert server.handle({"jsonrpc": "2.0", "method": "ping"}) is None


def test_mcp_ping():
    server = build_owner_server()
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
    assert resp["result"] == {}


def test_mcp_unknown_method_is_32601():
    server = build_owner_server()
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 3, "method": "nope/nope", "params": {}}
    )
    assert resp["error"]["code"] == -32601


def test_mcp_tools_list_has_valid_schemas():
    server = build_owner_server()
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}}
    )
    tools = resp["result"]["tools"]
    assert len(tools) == 24
    for tool in tools:
        assert tool["name"] and tool["description"]
        schema = tool["inputSchema"]
        assert isinstance(schema, dict) and schema.get("type") == "object"
        assert isinstance(schema.get("properties"), dict)


def test_mcp_tools_call_round_trips_read_only_tool():
    server = build_owner_server()
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "lab_footprint",
                "arguments": {"params": "0.6B", "quant": "int4", "ctx": "32k"},
            },
        }
    )
    result = resp["result"]
    assert result["isError"] is False
    assert "600,000,000" in result["content"][0]["text"]


def test_mcp_unknown_tool_is_32602():
    server = build_owner_server()
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "does_not_exist", "arguments": {}},
        }
    )
    assert resp["error"]["code"] == -32602
    assert "does_not_exist" in resp["error"]["message"]


def test_mcp_gated_tool_without_consent_is_tool_error():
    server = build_owner_server()  # consent=False
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "echo hi"}},
        }
    )
    result = resp["result"]
    assert result["isError"] is True
    assert "confirmation" in result["content"][0]["text"].lower()


def test_mcp_resources():
    server = build_owner_server()
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 8, "method": "resources/list", "params": {}}
    )
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert "levi://info" in uris and "levi://capabilities" in uris
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "levi://info"},
        }
    )
    info = json.loads(resp["result"]["contents"][0]["text"])
    assert info["name"] == "levi" and info["profile"] == "owner"
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/read",
            "params": {"uri": "levi://bogus"},
        }
    )
    assert resp["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# Security profiles
# ---------------------------------------------------------------------------


def test_mcp_http_profile_is_restricted():
    server = build_http_server()
    assert server.profile == "cloud-safe"
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    names = {t["name"] for t in resp["result"]["tools"]}
    assert len(names) == 12
    for denied in (
        "shell_exec",
        "file_write",
        "file_read",
        "memory_write",
        "delegate",
        "http_request",
        "schedule_add",
    ):
        assert denied not in names
    # tools/call enforces the same boundary server-side
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "echo hi"}},
        }
    )
    assert resp["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# stdio transport over a real subprocess
# ---------------------------------------------------------------------------


def _repo_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parent.parent)


def test_mcp_stdio_subprocess_handshake(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _repo_root() + "/core" + os.pathsep + env.get("PYTHONPATH", "")
    env["HOME"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "levi.cli.main", "mcp", "serve", "--transport", "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )
    try:

        def rpc(msg_id, method, params=None):
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "method": method,
                        "params": params or {},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        init = rpc(1, "initialize")
        assert init["result"]["protocolVersion"] == PROTOCOL_VERSION
        tools = rpc(2, "tools/list")
        assert len(tools["result"]["tools"]) == 24
        call = rpc(
            3,
            "tools/call",
            {
                "name": "lab_footprint",
                "arguments": {"params": "0.6B", "quant": "int4", "ctx": "32k"},
            },
        )
        assert call["result"]["isError"] is False
        bad = rpc(4, "tools/call", {"name": "nope", "arguments": {}})
        assert bad["error"]["code"] == -32602
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


# ---------------------------------------------------------------------------
# HTTP transport over a real localhost socket
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_in_thread(server, token=""):
    _Handler.state = _MCPHTTPState(server, token)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def _post(port, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_mcp_http_enforces_restricted_profile():
    httpd, port = _serve_in_thread(build_http_server())
    try:
        status, body = _post(
            port, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert status == 200
        names = {t["name"] for t in body["result"]["tools"]}
        assert "shell_exec" not in names and len(names) == 12
        status, body = _post(
            port,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "shell_exec", "arguments": {"command": "echo hi"}},
            },
        )
        assert body["error"]["code"] == -32602
    finally:
        httpd.shutdown()


def test_mcp_http_bearer_token():
    httpd, port = _serve_in_thread(build_http_server(), token="tok123")
    try:
        status, _ = _post(
            port, {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        )
        assert status == 401
        status, body = _post(
            port,
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            token="tok123",
        )
        assert status == 200 and body["result"] == {}
    finally:
        httpd.shutdown()


# ---------------------------------------------------------------------------
# Transport hardening: body bounds, Content-Length validation, batch cap
# ---------------------------------------------------------------------------


def _raw_post(port, raw_body: bytes, content_length: str | None):
    """POST /mcp with a hand-set Content-Length header."""
    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if content_length is not None:
        headers["Content-Length"] = content_length
        body = raw_body
    else:
        body = None  # no Content-Length header at all
    conn.request("POST", "/mcp", body=body, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    try:
        return resp.status, json.loads(body)
    except ValueError:
        return resp.status, None


def test_mcp_http_rejects_garbage_content_length():
    from levi.mcp.transports import _MAX_JSON_BODY  # noqa: F401

    httpd, port = _serve_in_thread(build_http_server())
    try:
        status, body = _raw_post(port, b"{}", "not-a-number")
        assert status == 400
        assert "Content-Length" in body["error"]
    finally:
        httpd.shutdown()


def test_mcp_http_rejects_negative_content_length():
    httpd, port = _serve_in_thread(build_http_server())
    try:
        status, body = _raw_post(port, b"{}", "-5")
        assert status == 400
        assert "Content-Length" in body["error"]
    finally:
        httpd.shutdown()


def test_mcp_http_rejects_oversized_body():
    from levi.mcp.transports import _MAX_JSON_BODY

    httpd, port = _serve_in_thread(build_http_server())
    try:
        status, body = _raw_post(port, b"{}", str(_MAX_JSON_BODY + 1))
        assert status == 400
        assert "too large" in body["error"]
    finally:
        httpd.shutdown()


def test_mcp_batch_over_limit_is_rejected():
    from levi.mcp.protocol import _MAX_BATCH_SIZE, build_owner_server

    server = build_owner_server()
    batch = [
        {"jsonrpc": "2.0", "id": i, "method": "ping", "params": {}}
        for i in range(_MAX_BATCH_SIZE + 1)
    ]
    resp = server.handle(batch)
    assert resp["error"]["code"] == -32600
    assert "batch" in resp["error"]["message"]


def test_mcp_batch_within_limit_still_works():
    from levi.mcp.protocol import build_owner_server

    server = build_owner_server()
    batch = [
        {"jsonrpc": "2.0", "id": i, "method": "ping", "params": {}}
        for i in range(3)
    ]
    resp = server.handle(batch)
    assert isinstance(resp, list) and len(resp) == 3
    assert all(r["result"] == {} for r in resp)
