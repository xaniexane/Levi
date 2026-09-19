"""AI counterpart bridge for alpha — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing.

Exposes Alpha's reasoner (``levi.alpha.reason.Reasoner``) through two
conventional shapes so outside callers that only speak these protocols
can reach it:

- ``tool_schema()`` — an MCP-style tool description for ``alpha_reason``.
- ``chat_completion_request(task)`` / ``chat_completion_response(result)``
  — chat-completions-shaped request/response envelopes.

The bridge never reasons on its own: ``run(task)`` delegates straight to
the SI core. The core's verdict — including which substrate reasoned —
is returned verbatim.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ..reason import Reasoner

BRIDGE_LABEL = (
    "AI counterpart bridge for alpha — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

TOOL_NAME = "alpha_reason"

_reasoner: "Reasoner | None" = None


def _core() -> Reasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = Reasoner()
    return _reasoner


def tool_schema() -> Dict[str, Any]:
    """MCP-style tool schema for Alpha's reasoner."""
    return {
        "name": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "description": (
            "Reason over a task with propose -> critique -> verdict "
            "deliberation. Returns answer, substrate (which mind reasoned), "
            "and limits (honest statement of what the reasoning is and "
            "isn't). Refuses empty tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "the task to reason about (non-empty)",
                }
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    }


def run(task: str) -> Dict[str, Any]:
    """Delegate to the SI core — the core reasons, the bridge carries."""
    return _core().reason(task)


def chat_completion_request(task: str) -> Dict[str, Any]:
    """Chat-completions-shaped request envelope for a reasoning call."""
    return {
        "model": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a protocol bridge, not a reasoner. Forward the "
                    "task to the SI core via alpha_reason and return its "
                    "result verbatim, including substrate and limits."
                ),
            },
            {"role": "user", "content": task},
        ],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
    }


def chat_completion_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Chat-completions-shaped response envelope for a verdict."""
    return {
        "id": "bridge-alpha-reason",
        "object": "chat.completion",
        "bridge_label": BRIDGE_LABEL,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(result, indent=2),
                },
                "finish_reason": "stop",
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
