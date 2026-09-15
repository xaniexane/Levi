"""MCP client tests — hermetic stub MCP servers (HTTP + stdio).

Never touches the real ~/.levi: every config function takes a home param.
"""
import json
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from levi.mcp import client as mc
from levi.agent.tools import ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# HTTP stub
# ---------------------------------------------------------------------------


class _StubHandler(BaseHTTPRequestHandler):
    mode = "ok"  # "ok" | "slow" | "legacy"

    def _dispatch(self, msg):
        method = msg.get("method")
        params = msg.get("params") or {}
        if method == "initialize":
            return {"protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "stub", "version": "0"}}
        if method == "tools/list":
            return {"tools": [
                {"name": "echo", "description": "echoes args",
                 "inputSchema": {"type": "object",
                                "properties": {"text": {"type": "string"}}}},
                {"name": "slow", "description": "sleeps then answers",
                 "inputSchema": {"type": "object", "properties": {}}},
            ]}
        if method == "tools/call":
            if params.get("name") == "slow":
                time.sleep(2)
            return {"content": [{"type": "text",
                                 "text": "echo:" + json.dumps(params.get("arguments", {}))}]}
        if method == "ping":
            return {}
        return None

    def _send_json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.mode == "legacy" and not self.path.startswith("/message"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            msg = json.loads(body)
        except ValueError:
            self._send_json({"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "parse error"}},
                            code=400)
            return
        if "id" not in msg:  # notification
            self.send_response(202)
            self.end_headers()
            return
        result = self._dispatch(msg)
        if result is None:
            self._send_json({"jsonrpc": "2.0", "id": msg.get("id"),
                             "error": {"code": -32601, "message": "unknown method"}})
        else:
            self._send_json({"jsonrpc": "2.0", "id": msg.get("id"), "result": result})

    def do_GET(self):
        if self.mode == "legacy" and self.path == "/sse":
            payload = b"event: endpoint\ndata: /message?sessionId=abc123\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture()
def http_stub():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    _StubHandler.mode = "ok"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _url(http_stub, path="/mcp"):
    host, port = http_stub.server_address
    return f"http://{host}:{port}{path}"


# ---------------------------------------------------------------------------
# stdio stub
# ---------------------------------------------------------------------------

STDIO_STUB = r"""
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        res = {"protocolVersion": "2024-11-05",
               "serverInfo": {"name": "stdio-stub", "version": "0"}}
    elif method == "tools/list":
        res = {"tools": [{"name": "shout", "description": "uppercases",
                          "inputSchema": {"type": "object",
                                          "properties": {"text": {"type": "string"}}}}]}
    elif method == "tools/call":
        res = {"content": [{"type": "text",
                            "text": str(params.get("arguments", {}).get("text", "")).upper()}]}
    elif method == "ping":
        res = {}
    else:
        res = None
    if mid is not None:
        if res is None:
            out = {"jsonrpc": "2.0", "id": mid,
                   "error": {"code": -32601, "message": "unknown method"}}
        else:
            out = {"jsonrpc": "2.0", "id": mid, "result": res}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
"""


# ---------------------------------------------------------------------------
# HTTP transport tests
# ---------------------------------------------------------------------------


def test_http_roundtrip(http_stub):
    t = mc.HttpTransport(_url(http_stub), timeout=5)
    c = mc.MCPClient(t, timeout=5)
    try:
        info = c.connect()
        assert info["serverInfo"]["name"] == "stub"
        tools = c.list_tools()
        assert {t_["name"] for t_ in tools} == {"echo", "slow"}
        out = c.call_tool("echo", {"text": "hi"})
        assert "hi" in json.dumps(out)
        assert c.ping() == {}
    finally:
        c.close()


def test_http_unknown_tool_is_clean_error(http_stub):
    t = mc.HttpTransport(_url(http_stub), timeout=5)
    c = mc.MCPClient(t, timeout=5)
    try:
        c.connect()
        # stub answers unknown method with -32601; tools/call with a bad name
        # still dispatches (stub echoes) — so call a truly unknown method.
        with pytest.raises(mc.MCPClientError):
            t.request("nope/not-a-method", {}, timeout=5)
    finally:
        c.close()


def test_http_timeout(http_stub):
    t = mc.HttpTransport(_url(http_stub), timeout=5)
    c = mc.MCPClient(t, timeout=5)
    try:
        c.connect()
        with pytest.raises(mc.MCPClientError, match="timed out"):
            c.call_tool("slow", {}, timeout=0.3)
    finally:
        c.close()


def test_http_unreachable_is_clean_error():
    t = mc.HttpTransport("http://127.0.0.1:1/mcp", timeout=2)
    c = mc.MCPClient(t, timeout=2)
    with pytest.raises(mc.MCPClientError, match="cannot reach"):
        c.connect()


def test_http_legacy_sse_fallback(http_stub):
    _StubHandler.mode = "legacy"
    try:
        t = mc.HttpTransport(_url(http_stub, "/mcp"), timeout=5)
        c = mc.MCPClient(t, timeout=5)
        try:
            c.connect()  # POST /mcp → 404 → SSE handshake → POST /message
            tools = c.list_tools()
            assert any(t_["name"] == "echo" for t_ in tools)
        finally:
            c.close()
    finally:
        _StubHandler.mode = "ok"


# ---------------------------------------------------------------------------
# stdio transport tests
# ---------------------------------------------------------------------------


def test_stdio_roundtrip():
    t = mc.StdioTransport([sys.executable, "-c", STDIO_STUB])
    c = mc.MCPClient(t, timeout=5)
    try:
        info = c.connect()
        assert info["serverInfo"]["name"] == "stdio-stub"
        tools = c.list_tools()
        assert [t_["name"] for t_ in tools] == ["shout"]
        out = c.call_tool("shout", {"text": "hello"})
        assert "HELLO" in json.dumps(out)
    finally:
        c.close()


def test_stdio_bad_command_is_clean_error():
    with pytest.raises(mc.MCPClientError, match="cannot spawn"):
        mc.StdioTransport(["/nonexistent/mcp-server-binary-xyz"])


# ---------------------------------------------------------------------------
# Config store
# ---------------------------------------------------------------------------


def test_config_add_list_remove_roundtrip(tmp_path):
    home = tmp_path / "home"
    mc.add_server("s1", transport="http", url="http://x/mcp", home=home)
    mc.add_server("s2", transport="stdio", command=["npx", "-y", "s"], home=home)
    servers = mc.list_servers(home)
    assert set(servers) == {"s1", "s2"}
    assert servers["s1"]["url"] == "http://x/mcp"
    assert servers["s2"]["command"] == ["npx", "-y", "s"]
    path = home / ".levi" / "mcp" / "servers.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    mc.remove_server("s1", home=home)
    assert set(mc.list_servers(home)) == {"s2"}
    with pytest.raises(mc.MCPClientError):
        mc.remove_server("nope", home=home)


def test_config_rejects_bad_names_and_configs(tmp_path):
    home = tmp_path / "home"
    with pytest.raises(mc.MCPClientError):
        mc.add_server("../evil", transport="http", url="http://x", home=home)
    with pytest.raises(mc.MCPClientError):
        mc.add_server("s", transport="http", home=home)  # no url
    with pytest.raises(mc.MCPClientError):
        mc.add_server("s", transport=" CarrierPigeon ", home=home)


# ---------------------------------------------------------------------------
# Tool bridge
# ---------------------------------------------------------------------------


def test_tool_conversion_naming_and_handler(http_stub, tmp_path):
    home = tmp_path / "home"
    cfg = {"transport": "http", "url": _url(http_stub), "timeout": 5}
    tools = mc.mcp_tools_for_server("stub", cfg, home=home)
    try:
        names = sorted(t.name for t in tools)
        assert names == ["mcp__stub__echo", "mcp__stub__slow"]
        echo = next(t for t in tools if t.name == "mcp__stub__echo")
        assert echo.description.startswith("[MCP:stub]")
        assert echo.parameters["type"] == "object"
        result = echo.handler({"text": "yo"})
        assert isinstance(result, ToolResult) and result.ok
        assert "yo" in result.output
    finally:
        mc.close_all()


def test_attach_skips_bad_server(http_stub, tmp_path, capsys):
    home = tmp_path / "home"
    mc.add_server("good", transport="http", url=_url(http_stub), home=home)
    mc.add_server("bad", transport="http", url="http://127.0.0.1:1/mcp", home=home)
    try:
        registry = ToolRegistry()
        attached = mc.attach_mcp_tools(registry, home=home)
        assert attached == ["good"]
        assert registry.get("mcp__good__echo") is not None
        assert registry.get("mcp__bad__echo") is None
        err = capsys.readouterr().err
        assert "bad" in err  # warning emitted, no raise
    finally:
        mc.close_all()


def test_attach_with_no_servers_is_noop(tmp_path):
    registry = ToolRegistry()
    assert mc.attach_mcp_tools(registry, home=tmp_path / "empty") == []


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------


def _ns(**kw):
    return SimpleNamespace(**kw)


def test_cli_add_probes_and_lists(http_stub, tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    from levi.mcp import cli as mcli

    mcli.cmd_mcp(_ns(mcp_action="add", name="web", url=_url(http_stub),
                     cmd=None, client_transport="", header=[], timeout=5))
    out = capsys.readouterr().out
    assert "Added MCP server 'web'" in out and "2 tool(s)" in out

    mcli.cmd_mcp(_ns(mcp_action="list-servers"))
    out = capsys.readouterr().out
    assert "web" in out and "[http]" in out

    mcli.cmd_mcp(_ns(mcp_action="remove", name="web"))
    assert "Removed" in capsys.readouterr().out
    assert mc.list_servers() == {}
    mc.close_all()
