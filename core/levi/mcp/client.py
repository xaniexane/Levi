"""MCP client — LEVI connects OUT to external MCP servers (LEVI-original).

Complement to the MCP *server* in this package (protocol.py): where the
server exposes LEVI's tools to other apps, the client lets LEVI *use* tools
from any MCP-compatible server — other LEVI instances, local dev tools,
third-party MCP servers.

Supported transports (stdlib-only):
- ``stdio`` — spawn a local command, newline-delimited JSON-RPC on its
  stdin/stdout (the standard local-client pattern).
- ``http`` — Streamable HTTP: POST JSON-RPC to the configured URL, with an
  automatic fallback to the legacy HTTP+SSE handshake (GET ``/sse`` →
  ``event: endpoint`` → POST ``/message?sessionId=…``) when the server
  answers 404/405 to the direct POST.

Protocol: MCP 2024-11-05 over JSON-RPC 2.0.

Trust model: adding a server (``levi mcp add``) is the explicit trust
decision. Remote tools are namespaced ``mcp__<server>__<tool>`` and are NOT
confirmation-gated — only add servers you trust, exactly like installing a
plugin. Unreachable servers are skipped at startup with a stderr warning
(reconnect is attempted on every start; there is no background retry loop).

Server configs live in ``~/.levi/mcp/servers.json`` (owner-only 0o600).
"""

from __future__ import annotations

import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT = 30.0
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class MCPClientError(Exception):
    """The MCP server could not be reached or answered badly."""


def _home() -> Path:
    return Path.home()


def _servers_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "mcp" / "servers.json"


# ---------------------------------------------------------------------------
# Server config store
# ---------------------------------------------------------------------------


def load_servers(home: Optional[Path] = None) -> dict:
    """Return {name: config} from servers.json; {} when absent."""
    path = _servers_file(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise MCPClientError(f"cannot read MCP servers file {path}: {exc}") from exc
    servers = (data or {}).get("servers", {})
    return servers if isinstance(servers, dict) else {}


def save_servers(servers: dict, home: Optional[Path] = None) -> Path:
    """Atomically write servers.json owner-only (0o600)."""
    path = _servers_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(".json.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"servers": servers}, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    return path


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise MCPClientError(
            f"invalid MCP server name {name!r}: use 1-64 chars of [A-Za-z0-9_-]"
        )
    return name


def add_server(
    name: str,
    *,
    transport: str,
    url: Optional[str] = None,
    command: Optional[list[str]] = None,
    headers: Optional[dict] = None,
    timeout: Optional[float] = None,
    reference: Optional[str] = None,
    home: Optional[Path] = None,
) -> dict:
    """Add (or replace) a server config. Returns the stored config.

    ``reference`` is the external provider behind this server, recorded
    as a *reference* (never a source, never LEVI identity) in the
    universal registry (``levi.plugins.references``) as well as on the
    server config itself.
    """
    from levi.plugins import references as _refs

    name = _validate_name(name)
    transport = (transport or "").strip().lower()
    if transport == "http":
        if not url:
            raise MCPClientError("http transport requires a url")
        cfg: dict[str, Any] = {"transport": "http", "url": url}
        if headers:
            cfg["headers"] = dict(headers)
    elif transport == "stdio":
        if not command:
            raise MCPClientError("stdio transport requires a command")
        cfg = {"transport": "stdio", "command": [str(c) for c in command]}
    else:
        raise MCPClientError(f"unknown MCP transport {transport!r} (http|stdio)")
    if timeout:
        cfg["timeout"] = float(timeout)
    if reference:
        provider = _refs.validate_provider_name(reference)
        cfg["reference"] = provider
    servers = load_servers(home)
    servers[name] = cfg
    save_servers(servers, home)
    if reference:
        target = url or (" ".join(command) if command else "")
        # Replacing a server: drop the old linked reference record first so
        # a stale provider label can never linger.
        _refs.remove_references_where(
            lambda r: r.kind == "mcp-server" and r.detail.get("mcp_server") == name,
            home=home,
        )
        _refs.add_reference(
            provider,
            kind="mcp-server",
            detail={"mcp_server": name, "transport": transport, "target": target},
            home=home,
        )
    return cfg


def remove_server(name: str, home: Optional[Path] = None) -> None:
    """Remove a server config. Raises MCPClientError when unknown."""
    from levi.plugins import references as _refs

    name = _validate_name(name)
    servers = load_servers(home)
    if name not in servers:
        raise MCPClientError(f"unknown MCP server {name!r}")
    del servers[name]
    save_servers(servers, home)
    _refs.remove_references_where(
        lambda r: r.kind == "mcp-server"
        and r.detail.get("mcp_server") == name,
        home=home,
    )


def list_servers(home: Optional[Path] = None) -> dict:
    """Return {name: config} for all configured servers."""
    return load_servers(home)


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------


def _unwrap(result_msg: Any, method: str) -> Any:
    if not isinstance(result_msg, dict) or result_msg.get("jsonrpc") != "2.0":
        raise MCPClientError(
            f"bad JSON-RPC response for {method}: {result_msg!r}"[:200]
        )
    if "error" in result_msg and result_msg["error"] is not None:
        err = result_msg["error"] or {}
        raise MCPClientError(
            f"MCP {method} failed: {err.get('message', err)} "
            f"(code {err.get('code', '?')})"
        )
    return result_msg.get("result")


class StdioTransport:
    """JSON-RPC over a child process's stdin/stdout (newline-delimited)."""

    def __init__(self, command: list[str]) -> None:
        try:
            self._proc = subprocess.Popen(
                [str(c) for c in command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except (OSError, ValueError) as exc:
            raise MCPClientError(f"cannot spawn MCP server {command!r}: {exc}") from exc
        self._incoming: "queue.Queue[Any]" = queue.Queue()
        self._stashed: dict[Any, Any] = {}
        self._next_id = 0
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        try:
            for line in self._proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    self._incoming.put(json.loads(line))
                except ValueError:
                    continue
        except Exception:
            pass

    def request(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        with self._lock:
            self._next_id += 1
            rid = self._next_id
        stashed = self._stashed.pop(rid, None)
        if stashed is not None:
            return _unwrap(stashed, method)
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params or {},
        }
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError) as exc:
            raise MCPClientError(f"MCP stdio write failed ({method}): {exc}") from exc
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPClientError(
                    f"MCP {method} timed out after {timeout:g}s (stdio)"
                )
            try:
                msg = self._incoming.get(timeout=remaining)
            except queue.Empty:
                raise MCPClientError(
                    f"MCP {method} timed out after {timeout:g}s (stdio)"
                ) from None
            if isinstance(msg, dict) and msg.get("id") == rid:
                return _unwrap(msg, method)
            # Responses for other ids (or server notifications) are stashed.
            if isinstance(msg, dict) and "id" in msg:
                self._stashed[msg["id"]] = msg

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def close(self) -> None:
        try:
            self._proc.terminate()
        except Exception:
            pass


class HttpTransport:
    """Streamable HTTP: POST JSON-RPC, with legacy HTTP+SSE fallback."""

    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url.rstrip("/")
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._session_id: Optional[str] = None
        self._legacy_endpoint: Optional[str] = None  # set after SSE handshake
        self._next_id = 0
        self._lock = threading.Lock()

    def _post(self, url: str, payload: dict, timeout: float) -> tuple[str, str, dict]:
        """POST JSON; return (content_type, body, response_headers)."""
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "")
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session_id = sid
                return ctype, resp.read().decode("utf-8", "replace"), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            raise MCPClientError(f"MCP HTTP POST {url} → HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            raise MCPClientError(f"cannot reach MCP server at {url}: {exc}") from exc

    @staticmethod
    def _sse_data_payloads(body: str) -> list[str]:
        """Collect data: payloads from a text/event-stream body."""
        payloads: list[str] = []
        current: list[str] = []
        for line in body.splitlines():
            if line.startswith("data:"):
                current.append(line[5:].strip())
            elif not line.strip():
                if current:
                    payloads.append("\n".join(current))
                    current = []
        if current:
            payloads.append("\n".join(current))
        return payloads

    def _legacy_handshake(self, timeout: float) -> str:
        """GET <base>/sse, parse `event: endpoint`, return message POST URL."""
        base = self._url.rsplit("/", 1)[0] if "/" in self._url else self._url
        sse_url = base + "/sse"
        req = urllib.request.Request(
            sse_url, headers={"Accept": "text/event-stream", **self._headers}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(65536).decode("utf-8", "replace")
        except Exception as exc:
            raise MCPClientError(
                f"MCP SSE handshake failed at {sse_url}: {exc}"
            ) from exc
        event: Optional[str] = None
        for line in raw.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event == "endpoint":
                endpoint = line[5:].strip()
                if endpoint.startswith("/"):
                    return base + endpoint
                return endpoint
        raise MCPClientError(f"MCP SSE handshake at {sse_url} gave no endpoint event")

    def request(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        timeout = self._timeout if timeout is None else timeout
        with self._lock:
            self._next_id += 1
            rid = self._next_id
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params or {},
        }
        target = self._legacy_endpoint or self._url
        try:
            ctype, body, _ = self._post(target, payload, timeout)
        except MCPClientError as exc:
            # Legacy servers answer 404/405 to a direct POST: try the SSE
            # handshake once, then POST to the negotiated message endpoint.
            if self._legacy_endpoint is None and (
                "HTTP 404" in str(exc) or "HTTP 405" in str(exc)
            ):
                self._legacy_endpoint = self._legacy_handshake(timeout)
                ctype, body, _ = self._post(self._legacy_endpoint, payload, timeout)
            else:
                raise
        if "text/event-stream" in ctype:
            for data in self._sse_data_payloads(body):
                try:
                    msg = json.loads(data)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == rid:
                    return _unwrap(msg, method)
            raise MCPClientError(f"MCP {method}: no matching response in SSE stream")
        if not body.strip():
            raise MCPClientError(f"MCP {method}: empty response from {target}")
        try:
            return _unwrap(json.loads(body), method)
        except ValueError as exc:
            raise MCPClientError(f"MCP {method}: invalid JSON response: {exc}") from exc

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        try:
            self._post(self._legacy_endpoint or self._url, payload, self._timeout)
        except MCPClientError:
            pass

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _levi_version() -> str:
    try:
        import levi

        return str(getattr(levi, "__version__", "0.0.0"))
    except Exception:
        return "0.0.0"


class MCPClient:
    """One connected MCP server session (initialize → tools)."""

    def __init__(self, transport: Any, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._t = transport
        self._timeout = timeout
        self.server_info: dict = {}
        self._closed = False

    def connect(self) -> dict:
        """Run the MCP initialize handshake + initialized notification."""
        result = self._t.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "levi", "version": _levi_version()},
            },
            timeout=self._timeout,
        )
        self.server_info = result if isinstance(result, dict) else {}
        try:
            self._t.notify("notifications/initialized", {})
        except Exception:
            pass
        return self.server_info

    def list_tools(self) -> list[dict]:
        result = self._t.request("tools/list", {}, timeout=self._timeout)
        tools = (result or {}).get("tools", []) if isinstance(result, dict) else []
        return [t for t in tools if isinstance(t, dict)]

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        return self._t.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout=self._timeout if timeout is None else timeout,
        )

    def ping(self) -> Any:
        return self._t.request("ping", {}, timeout=self._timeout)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._t.close()
            except Exception:
                pass


def connect_server(
    name: str, cfg: dict, timeout: Optional[float] = None, home: Optional[Path] = None
) -> MCPClient:
    """Build a transport from a server config and run the handshake."""
    _ = home  # configs already resolved by the caller
    name = _validate_name(name)
    transport = (cfg.get("transport") or "").lower()
    tmo = float(cfg.get("timeout") or timeout or DEFAULT_TIMEOUT)
    if transport == "http":
        url = cfg.get("url") or ""
        if not url:
            raise MCPClientError(f"MCP server {name!r}: http transport needs a url")
        t: Any = HttpTransport(url, headers=cfg.get("headers"), timeout=tmo)
    elif transport == "stdio":
        command = cfg.get("command") or []
        if not command:
            raise MCPClientError(
                f"MCP server {name!r}: stdio transport needs a command"
            )
        t = StdioTransport([str(c) for c in command])
    else:
        raise MCPClientError(f"MCP server {name!r}: unknown transport {transport!r}")
    client = MCPClient(t, timeout=tmo)
    try:
        client.connect()
    except Exception:
        client.close()
        raise
    return client


# ---------------------------------------------------------------------------
# LEVI tool-registry bridge
# ---------------------------------------------------------------------------

# Open clients by server name so tool handlers reuse one live session.
_OPEN_CLIENTS: dict[str, MCPClient] = {}


def _get_client(name: str, home: Optional[Path] = None) -> MCPClient:
    client = _OPEN_CLIENTS.get(name)
    if client is not None and not client._closed:
        return client
    cfg = load_servers(home).get(name)
    if cfg is None:
        raise MCPClientError(f"MCP server {name!r} is not configured")
    client = connect_server(name, cfg, home=home)
    _OPEN_CLIENTS[name] = client
    return client


def mcp_tools_for_server(name: str, cfg: dict, home: Optional[Path] = None) -> "list":
    """Connect to one server and convert its tools to LEVI Tool objects.

    Names are ``mcp__<server>__<tool>``. Adding the server is the trust
    decision, so converted tools are not confirmation-gated.
    """
    from levi.agent.tools import Tool, ToolResult

    name = _validate_name(name)
    client = connect_server(name, cfg, home=home)
    _OPEN_CLIENTS[name] = client
    try:
        remote_tools = client.list_tools()
    except Exception:
        client.close()
        _OPEN_CLIENTS.pop(name, None)
        raise

    timeout = float(cfg.get("timeout") or DEFAULT_TIMEOUT)
    tools = []
    for rt in remote_tools:
        tname = str(rt.get("name") or "").strip()
        if not tname or not _NAME_RE.match(tname):
            continue
        local_name = f"mcp__{name}__{tname}"
        schema = rt.get("inputSchema") or {"type": "object", "properties": {}}
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        desc = str(rt.get("description") or "MCP tool")[:500]

        def _handler(
            args: dict,
            _client: MCPClient = client,
            _tname: str = tname,
            _tmo: float = timeout,
        ) -> ToolResult:
            try:
                result = _client.call_tool(_tname, args, timeout=_tmo)
            except MCPClientError as exc:
                return ToolResult(ok=False, error=str(exc))
            except Exception as exc:  # never leak a raw traceback
                return ToolResult(ok=False, error=f"MCP tool call failed: {exc}")
            return ToolResult(ok=True, output=json.dumps(result)[:8000])

        tools.append(
            Tool(
                name=local_name,
                description=f"[MCP:{name}] {desc}",
                parameters=schema,
                handler=_handler,
                requires_confirmation=False,
            )
        )
    return tools


def attach_mcp_tools(registry: Any, home: Optional[Path] = None) -> list[str]:
    """Merge every configured MCP server's tools into ``registry``.

    Reconnect is attempted on every call (i.e. every agent start).
    Unreachable or misbehaving servers are skipped with a stderr warning —
    this never raises, so agent startup can't break on a dead server.
    Returns the list of attached server names.
    """
    attached: list[str] = []
    try:
        servers = load_servers(home)
    except MCPClientError as exc:
        print(f"[levi:mcp] {exc}", file=sys.stderr)
        return attached
    for name, cfg in servers.items():
        try:
            for tool in mcp_tools_for_server(name, cfg, home=home):
                registry.register(tool)
            attached.append(name)
        except MCPClientError as exc:
            print(f"[levi:mcp] skipping server {name!r}: {exc}", file=sys.stderr)
        except Exception as exc:  # defensive: never break agent startup
            print(
                f"[levi:mcp] skipping server {name!r}: unexpected error: {exc}",
                file=sys.stderr,
            )
    return attached


def close_all() -> None:
    """Close every cached client (process teardown)."""
    for client in list(_OPEN_CLIENTS.values()):
        try:
            client.close()
        except Exception:
            pass
    _OPEN_CLIENTS.clear()
