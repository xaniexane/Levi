"""AI counterpart bridge for omega — conventional-protocol interface.

The SI core (si/omega.py) is authoritative; this bridge claims nothing.
It never claims to be the SI.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.si_team.ai import bridge_label

AI_BRIDGE_LABEL = bridge_label("omega")


def to_mcp_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "omega_judge",
            "description": (
                AI_BRIDGE_LABEL + " Ask Omega, the judge, to evaluate work "
                "against the charter: verdict PASS, FIX, or FAIL with reasons."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The work to evaluate, with its charter context.",
                    }
                },
                "required": ["task"],
            },
        }
    ]


def chat_adapter() -> Dict[str, Any]:
    def build_request(messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "model": "omega-ai-counterpart-bridge",
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
