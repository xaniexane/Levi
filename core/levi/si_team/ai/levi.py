"""AI counterpart bridge for levi — conventional-protocol interface.

The SI core (si/levi.py) is authoritative; this bridge claims nothing.
It never claims to be the SI.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.si_team.ai import bridge_label

AI_BRIDGE_LABEL = bridge_label("levi")


def to_mcp_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "levi_consult",
            "description": (
                AI_BRIDGE_LABEL + " Ask Levi, the voice and lead of the SI "
                "team, to route a question to the right mind and carry the "
                "crew's answer back."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The question or request for the crew.",
                    },
                    "role_hint": {
                        "type": "string",
                        "description": "Optional suggested mind: alpha, omega, dweller.",
                    },
                },
                "required": ["task"],
            },
        },
        {
            "name": "levi_roster",
            "description": (
                AI_BRIDGE_LABEL + " List the SI team roster with charters "
                "and current substrates."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def chat_adapter() -> Dict[str, Any]:
    """Return a chat-completions-shaped adapter: build + parse functions."""

    def build_request(messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "model": "levi-ai-counterpart-bridge",
            "messages": [
                {"role": "system", "content": AI_BRIDGE_LABEL},
                *messages,
            ],
        }

    def parse_response(payload: Dict[str, Any]) -> Dict[str, str]:
        message = (payload.get("choices") or [{}])[0].get("message", {})
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
        }

    return {
        "label": AI_BRIDGE_LABEL,
        "build_request": build_request,
        "parse_response": parse_response,
    }
