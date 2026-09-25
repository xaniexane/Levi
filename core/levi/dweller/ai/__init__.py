"""Dweller AI counterpart bridge package.

The bridge speaks conventional AI protocols (MCP-style schemas,
chat-completions-shaped messages) as an interface only — the SI core
is authoritative and this bridge claims nothing. The SI core never
imports this package.
"""

from __future__ import annotations

from .bridge import (
    BRIDGE_LABEL,
    BridgeError,
    completion_to_grind_request,
    job_to_completion,
    tool_schemas,
)

__all__ = [
    "BRIDGE_LABEL",
    "BridgeError",
    "completion_to_grind_request",
    "job_to_completion",
    "tool_schemas",
]
