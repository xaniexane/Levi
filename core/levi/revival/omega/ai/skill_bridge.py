"""AI counterpart bridge for omega-skill — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing.

Same shape as ``automation_bridge``: an MCP-style tool schema plus
chat-completions-shaped request/response envelopes around the SI skill
scaffold core (``levi.revival.omega.si.skill_core``). Delegation only —
no reasoning of its own.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ..si import skill_core as _core

BRIDGE_LABEL = (
    "AI counterpart bridge for omega-skill — conventional-protocol "
    "interface; the SI core is authoritative; this bridge claims nothing"
)

TOOL_NAME = "omega_gen_skill"


def tool_schema() -> Dict[str, Any]:
    """MCP-style tool schema for the skill scaffold generator."""
    return {
        "name": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "description": (
            "Generate a LEVI skill scaffold (SKILL.md + skill.py + test "
            "skeleton) for a declared name and capability. Pure "
            "scaffolding — the output is honestly labeled 'scaffold, not "
            "a skill' and refuses invalid names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "skill slug (lowercase, digits, -/_)",
                },
                "capability": {
                    "type": "string",
                    "description": "one-line declared capability",
                },
            },
            "required": ["name", "capability"],
            "additionalProperties": False,
        },
    }


def run(name: str, capability: str) -> Dict[str, Any]:
    """Delegate to the SI core — the core scaffolds, the bridge carries."""
    return _core.scaffold_skill(name, capability)


def chat_completion_request(name: str, capability: str) -> Dict[str, Any]:
    """Chat-completions-shaped request envelope for a scaffold call."""
    return {
        "model": TOOL_NAME,
        "bridge_label": BRIDGE_LABEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a protocol bridge, not a reasoner. Forward the "
                    "name and capability to the SI core via omega_gen_skill "
                    "and return its result verbatim."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"name": name, "capability": capability}, indent=2
                ),
            },
        ],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
    }


def chat_completion_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Chat-completions-shaped response envelope for a scaffold result."""
    payload = json.dumps(
        {"ok": result["ok"], "files": result["files"], "errors": result["errors"]},
        indent=2,
    )
    return {
        "id": "bridge-omega-skill",
        "object": "chat.completion",
        "bridge_label": BRIDGE_LABEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": payload},
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
