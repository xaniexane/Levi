"""AI counterpart bridge for dweller — conventional-protocol interface.

The SI core (si/dweller.py) is authoritative; this bridge claims nothing.
It never claims to be the SI.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.si_team.ai import bridge_label

AI_BRIDGE_LABEL = bridge_label("dweller")


def to_mcp_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "dweller_labor",
            "description": (
                AI_BRIDGE_LABEL
                + " Ask Dweller, the SI that dwells in the depths of the work, to plan "
                "and queue heavy labor: sweeps, batches, grind work — "
                "Plan→Preview→Permission before anything irreversible."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The labor to plan and queue.",
                    }
                },
                "required": ["task"],
            },
        }
    ]


def chat_adapter() -> Dict[str, Any]:
    def build_request(messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "model": "dweller-ai-counterpart-bridge",
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
