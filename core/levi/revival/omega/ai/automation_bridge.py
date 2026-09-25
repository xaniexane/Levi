"""AI counterpart bridge for omega-automation — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing.

Exposes the SI automation generator (``levi.revival.omega.si.automation_core``)
through two conventional shapes so outside callers that only speak these
protocols can reach it:

- ``tool_schema()`` — an MCP-style tool description (name, description,
  input schema) for ``omega_gen_automation``.
- ``chat_completion_request(spec)`` / ``chat_completion_response(result)``
  — chat-completions-shaped request/response envelopes.

The bridge never reasons on its own: ``run(spec)`` delegates straight to
the SI core. Everything the core refuses, the bridge refuses.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..si import automation_core as _core

BRIDGE_LABEL = (
    "AI counterpart bridge for omega-automation — conventional-protocol "
    "interface; the SI core is authoritative; this bridge claims nothing"
)

TOOL_NAME = "omega_gen_automation"


def tool_schema() -> Dict[str, Any]:
    """MCP-style tool schema for the automation generator."""
    return {
        "name": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "description": (
            "Generate LEVI automation-minion definitions from a declarative "
            "spec. The SI core validates the spec against the Minion schema "
            "and refuses invalid specs. Emits Minion-compatible dicts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "Declarative spec: {'minions': [{'id', 'category', "
                        "'trigger', ...}]}. Required per minion: id, category, "
                        "trigger."
                    ),
                }
            },
            "required": ["spec"],
            "additionalProperties": False,
        },
    }


def run(spec: Dict[str, Any]) -> List[Dict[str, object]]:
    """Delegate to the SI core — the core validates, the bridge just carries."""
    return _core.generate_minions(spec)


def chat_completion_request(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Chat-completions-shaped request envelope for a generation call."""
    return {
        "model": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a protocol bridge, not a reasoner. Forward the "
                    "spec to the SI core via omega_gen_automation and "
                    "return its result verbatim."
                ),
            },
            {
                "role": "user",
                "content": "spec:\n" + json.dumps(spec, indent=2),
            },
        ],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
    }


def chat_completion_response(minions: List[Dict[str, object]]) -> Dict[str, Any]:
    """Chat-completions-shaped response envelope for generated minions."""
    payload = json.dumps({"minions": minions}, indent=2)
    return {
        "id": "bridge-omega-automation",
        "object": "chat.completion",
        "bridge_label": BRIDGE_LABEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": payload},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


__all__ = [
    "BRIDGE_LABEL",
    "TOOL_NAME",
    "tool_schema",
    "run",
    "chat_completion_request",
    "chat_completion_response",
]
