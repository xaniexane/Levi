"""MCP protocol dispatch over JSON-RPC 2.0 (LEVI-original, stdlib-only).

Implements the MCP 2024-11-05 surface LEVI serves:

* ``initialize`` → protocol version, capabilities, server info
* ``notifications/initialized`` → notification (no response)
* ``ping`` → ``{}``
* ``tools/list`` → every tool in the bound registry as
  ``{name, description, inputSchema}``
* ``tools/call`` → executes one tool, returns MCP content blocks
* ``resources/list`` / ``resources/read`` → two read-only resources:
  ``levi://info`` (server info) and ``levi://capabilities`` (capability
  atlas summary)

JSON-RPC errors follow the standard codes: -32700 parse error, -32600
invalid request, -32601 method not found, -32602 invalid params
(unknown tool / unknown resource), -32603 internal error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from levi.agent.tools import (
    ConfirmationRequired,
    ExecContext,
    ToolRegistry,
    build_default_registry,
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "levi"

#: Upper bound on a JSON-RPC batch: a batch is a convenience, not a
#: bulk-upload channel.
_MAX_BATCH_SIZE = 256


def _version() -> str:
    try:
        from levi import __version__

        return __version__
    except Exception:
        return "0.0.0"


def ok_response(msg_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def error_response(msg_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    }


def _normalize_schema(parameters: Any) -> dict:
    """Coerce a tool's parameter spec into a valid JSON Schema object.

    Every built-in tool already ships ``{"type": "object", "properties",
    "required"}``; this is a safety net so a future or third-party tool
    with a non-conforming spec still serializes as a legal MCP
    ``inputSchema`` instead of breaking ``tools/list``.
    """
    if isinstance(parameters, dict) and parameters.get("type") == "object":
        schema = dict(parameters)
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
        return schema
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _atlas_summary() -> str:
    """One-paragraph summary of the capability atlas for levi://capabilities."""
    path = (
        Path(__file__).resolve().parent.parent
        / "knowledge"
        / "capabilities"
        / "atlas.json"
    )
    try:
        atlas = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "LEVI capability atlas is not available in this installation."
    domains = atlas.get("domains", [])
    names = [d.get("name", "?") for d in domains if isinstance(d, dict)]
    lines = [
        "LEVI capability atlas — %d domains:" % len(names),
        ", ".join(names) if names else "(no domains listed)",
    ]
    note = atlas.get("note") or atlas.get("honesty_rule")
    if note:
        lines.append(str(note))
    return "\n".join(lines)


class MCPServer:
    """Transport-agnostic MCP dispatcher bound to one tool registry.

    ``profile`` is a human label for the security posture (``"owner"``
    or ``"cloud-safe"``); the actual enforcement is which registry was
    passed in — the caller decides, once, at construction.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        profile: str = "owner",
        consent: bool = False,
    ) -> None:
        self.registry = registry
        self.profile = profile
        self.consent = consent
        self._initialized = False

    # -- entry point ----------------------------------------------------

    def handle(self, message: Any) -> Any:
        """Handle one decoded JSON-RPC message (or a batch list).

        Returns a response dict, a list of them for batches, or ``None``
        when the message was a notification.
        """
        if isinstance(message, list):
            if len(message) > _MAX_BATCH_SIZE:
                return error_response(
                    None,
                    -32600,
                    f"invalid request: batch of {len(message)} exceeds the "
                    f"limit of {_MAX_BATCH_SIZE}",
                )
            responses = [self.handle(m) for m in message]
            responses = [r for r in responses if r is not None]
            return responses or None
        if not isinstance(message, dict):
            return error_response(None, -32600, "invalid request: not an object")
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        if not isinstance(method, str):
            return error_response(msg_id, -32600, "invalid request: missing method")

        handler = {
            "initialize": self._initialize,
            "notifications/initialized": self._initialized_notification,
            "ping": self._ping,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "resources/list": self._resources_list,
            "resources/read": self._resources_read,
        }.get(method)
        if handler is None:
            if msg_id is None:
                return None  # unknown notification: ignore quietly
            return error_response(msg_id, -32601, f"method not found: {method}")
        try:
            result = handler(params if isinstance(params, dict) else {})
        except _InvalidParams as exc:
            if msg_id is None:
                return None
            return error_response(msg_id, -32602, str(exc))
        except Exception as exc:  # never leak a traceback over the wire
            if msg_id is None:
                return None
            return error_response(msg_id, -32603, f"internal error: {exc}")
        if msg_id is None:
            return None  # notification: no response
        return ok_response(msg_id, result)

    # -- MCP methods -----------------------------------------------------

    def _initialize(self, params: dict) -> dict:
        self._initialized = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": _version()},
        }

    def _initialized_notification(self, params: dict) -> None:
        self._initialized = True
        return None

    def _ping(self, params: dict) -> dict:
        return {}

    def _tools_list(self, params: dict) -> dict:
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": _normalize_schema(tool.parameters),
            }
            for tool in self.registry.list()
        ]
        return {"tools": tools}

    def _tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            raise _InvalidParams("tools/call requires a 'name' string")
        if not isinstance(arguments, dict):
            raise _InvalidParams("tools/call 'arguments' must be an object")
        if self.registry.get(name) is None:
            raise _InvalidParams(f"unknown tool: {name}")
        ctx = ExecContext(consent=self.consent)
        try:
            result = self.registry.execute(name, arguments, ctx)
        except ConfirmationRequired:
            return _tool_error(
                "confirmation required: this tool changes state and the MCP "
                "server was started without --consent; re-run "
                "'levi mcp serve' with --consent to pre-authorize (owner "
                "stdio mode only)"
            )
        if result.ok:
            return {
                "content": [{"type": "text", "text": result.output}],
                "isError": False,
            }
        return _tool_error(result.error or f"tool {name} failed")

    def _resources_list(self, params: dict) -> dict:
        return {
            "resources": [
                {
                    "uri": "levi://info",
                    "name": "LEVI server info",
                    "mimeType": "application/json",
                },
                {
                    "uri": "levi://capabilities",
                    "name": "LEVI capability atlas summary",
                    "mimeType": "text/plain",
                },
            ]
        }

    def _resources_read(self, params: dict) -> dict:
        uri = params.get("uri")
        if uri == "levi://info":
            info = {
                "name": SERVER_NAME,
                "version": _version(),
                "protocolVersion": PROTOCOL_VERSION,
                "profile": self.profile,
                "tools": [t.name for t in self.registry.list()],
            }
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(info, indent=2),
                    }
                ]
            }
        if uri == "levi://capabilities":
            return {
                "contents": [
                    {"uri": uri, "mimeType": "text/plain", "text": _atlas_summary()}
                ]
            }
        raise _InvalidParams(f"unknown resource: {uri}")


class _InvalidParams(Exception):
    """Internal: maps to JSON-RPC -32602."""


def _tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def build_owner_server(*, consent: bool = False) -> MCPServer:
    """MCP server with the full tool registry (stdio transport)."""
    return MCPServer(build_default_registry(), profile="owner", consent=consent)


def build_http_server() -> MCPServer:
    """MCP server with the restricted cloud-safe profile (HTTP transport).

    Reuses :mod:`levi.cloud.profile` — the allowlist is defined once,
    there, and never forked.
    """
    from levi.cloud.profile import build_cloud_registry

    return MCPServer(build_cloud_registry(), profile="cloud-safe", consent=False)
