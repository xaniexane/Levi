"""AI counterpart bridge package.

Conventional-protocol interface to the NEXUS bus. The SI core
(``levi.nexus.si``) is authoritative; this bridge claims nothing.
"""

from .bridge import (
    BRIDGE_LABEL,
    adapt_chat_request,
    adapt_chat_response,
    execute_tool,
    tool_schemas,
)

__all__ = [
    "BRIDGE_LABEL",
    "adapt_chat_request",
    "adapt_chat_response",
    "execute_tool",
    "tool_schemas",
]
