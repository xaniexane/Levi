"""`levi mcp` CLI: serve LEVI's tools over MCP, and manage LEVI's own
outbound MCP server connections (LEVI-original)."""

from __future__ import annotations

import shlex


def cmd_mcp(args) -> None:
    """Serve LEVI as an MCP server, or manage MCP client connections."""
    action = getattr(args, "mcp_action", "serve") or "serve"
    if action in ("add", "remove", "list-servers"):
        _cmd_mcp_client(args, action)
        return
    if action != "serve":
        raise SystemExit(f"unknown mcp action: {action}")
    from levi.mcp.protocol import build_http_server, build_owner_server
    from levi.mcp.transports import serve_http, serve_stdio

    transport = getattr(args, "transport", "stdio") or "stdio"
    if transport == "http":
        server = build_http_server()
        serve_http(
            server,
            host=getattr(args, "host", None) or "127.0.0.1",
            port=int(getattr(args, "port", None) or 8899),
            token=getattr(args, "token", None) or "",
        )
        return
    if transport == "stdio":
        server = build_owner_server(consent=bool(getattr(args, "consent", False)))
        serve_stdio(server)
        return
    raise SystemExit(f"unknown mcp transport: {transport}")


def _cmd_mcp_client(args, action: str) -> None:
    from levi.mcp import client as _mc

    if action == "list-servers":
        servers = _mc.list_servers()
        if not servers:
            print("No MCP servers configured. Add one with:")
            print("  levi mcp add <name> --url http://host:port/mcp")
            print('  levi mcp add <name> --cmd "npx -y some-mcp-server"')
            return
        print("══ MCP servers ══\n")
        for name in sorted(servers):
            cfg = servers[name]
            t = cfg.get("transport", "?")
            where = cfg.get("url") or " ".join(cfg.get("command", []))
            print(f"  {name}  [{t}]  {where}")
        print("\n`levi agent run` attaches these servers' tools automatically.")
        return

    if action == "add":
        name = (getattr(args, "name", None) or "").strip()
        if not name:
            print('Usage: levi mcp add <name> --url <http-url> | --cmd "<cmd...>"')
            raise SystemExit(2)
        url = getattr(args, "url", None) or None
        command_s = getattr(args, "cmd", None) or None
        transport = (getattr(args, "client_transport", None) or "").strip().lower()
        if not transport:
            transport = "http" if url else "stdio"
        headers: dict[str, str] = {}
        for h in getattr(args, "header", None) or []:
            k, sep, v = h.partition("=")
            if sep and k.strip():
                headers[k.strip()] = v.strip()
        command = shlex.split(command_s) if command_s else None
        try:
            cfg = _mc.add_server(
                name,
                transport=transport,
                url=url,
                command=command,
                headers=headers or None,
                timeout=getattr(args, "timeout", None) or None,
            )
        except _mc.MCPClientError as exc:
            print(f"mcp add failed: {exc}")
            raise SystemExit(1) from None
        # Verify the server actually answers before declaring success.
        try:
            probe = _mc.connect_server(name, cfg)
            n = len(probe.list_tools())
            probe.close()
            _mc._OPEN_CLIENTS.pop(name, None)
        except _mc.MCPClientError as exc:
            print(f"Saved {name!r}, but the server did not answer: {exc}")
            print("Fix the URL/command, or `levi mcp remove` it.")
            raise SystemExit(1) from None
        print(f"Added MCP server {name!r} ({transport}) — {n} tool(s) available.")
        return

    if action == "remove":
        name = (getattr(args, "name", None) or "").strip()
        if not name:
            print("Usage: levi mcp remove <name>")
            raise SystemExit(2)
        try:
            _mc.remove_server(name)
        except _mc.MCPClientError as exc:
            print(f"mcp remove failed: {exc}")
            raise SystemExit(1) from None
        print(f"Removed MCP server {name!r}.")
        return
