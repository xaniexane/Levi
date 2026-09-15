"""`levi mcp` CLI: serve LEVI's tools over MCP (LEVI-original)."""

from __future__ import annotations


def cmd_mcp(args) -> None:
    """Serve LEVI as an MCP server (stdio or HTTP)."""
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
