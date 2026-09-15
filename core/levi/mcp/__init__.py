"""LEVI as an MCP (Model Context Protocol) server provider (LEVI-original).

Other apps and MCP clients consume LEVI's tool registry over JSON-RPC 2.0:

* ``MCPServer`` — protocol dispatch (initialize, ping, tools/list,
  tools/call, resources/list, resources/read). Transport-agnostic: it
  takes one JSON-RPC message dict and returns a response dict (or
  ``None`` for notifications).
* :mod:`levi.mcp.transports` — stdio and HTTP/SSE transports.

Security model (enforced server-side, never by client claim):

* stdio transport → the owner: the full tool registry.
* HTTP transport → the restricted cloud-safe profile
  (:mod:`levi.cloud.profile` ``CLOUD_SAFE_TOOLS``), reused — never forked.

MCP calls run with ``consent=False`` unless the server was started with
explicit consent, so confirmation-gated tools (shell_exec, file_write,
…) return a tool-level error over MCP instead of executing blindly.
There is no MCP-native confirmation flow in protocol version 2024-11-05.
"""

from __future__ import annotations
from levi.mcp.protocol import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    MCPServer,
    build_owner_server,
    build_http_server,
)

__all__ = [
    "PROTOCOL_VERSION",
    "SERVER_NAME",
    "MCPServer",
    "build_owner_server",
    "build_http_server",
]
