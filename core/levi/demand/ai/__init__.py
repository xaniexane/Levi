"""AI counterpart bridge for demandpulse — conventional-protocol interface.

BRIDGE_LABEL = "AI counterpart bridge for demandpulse — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing."

This package lets conventional tooling (MCP-style tool callers, chat
front-ends) consume the DemandPulse feed without touching the SI core.
It exposes:

  - ``TOOLS``: MCP-style tool schemas (name / description / inputSchema).
  - ``execute_tool(name, arguments, home=None)``: dispatches to the SI core
    and returns a labeled result envelope.
  - ``as_chat_completion(result, model=...)``: shapes a result like a
    chat-completions response for conventional chat plumbing.

The bridge claims nothing of its own: every answer is served from stored
digests or produced by the SI core's ``curate()`` — same honesty law
(basis-less items are quarantined, nothing is fabricated). Dependency is
one-way: this bridge imports the SI core; the SI core never imports us.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from levi.demand import si

BRIDGE_LABEL = (
    "AI counterpart bridge for demandpulse — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

__all__ = [
    "BRIDGE_LABEL",
    "TOOLS",
    "as_chat_completion",
    "bridge_notice",
    "execute_tool",
]


def bridge_notice() -> str:
    """The label every bridge response carries."""
    return BRIDGE_LABEL


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "demandpulse_get_latest_digest",
        "description": (
            "Return the most recent DemandPulse digest (ranked, tiered "
            "opportunities with basis notes), served from the SI core's "
            "stored digests. " + BRIDGE_LABEL
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "demandpulse_build_digest",
        "description": (
            "Curate validated score cards and raw candidates into a dated "
            "digest via the SI core: ranked, tiered, deduped, stored as "
            "JSONL. Basis-less candidates are quarantined, not published. "
            + BRIDGE_LABEL
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cards": {
                    "type": "array",
                    "description": "Stored-card dicts (ScoreCard.to_dict form).",
                    "items": {"type": "object"},
                },
                "raw": {
                    "type": "array",
                    "description": "Analyst candidate dicts "
                    "(opportunity_id/title/factors with basis notes).",
                    "items": {"type": "object"},
                },
                "digest_id": {
                    "type": "string",
                    "description": "Optional explicit digest id.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "demandpulse_watch_item",
        "description": (
            "Mark an opportunity id as watched in the SI core's watchlist. "
            + BRIDGE_LABEL
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "opportunity_id to watch",
                }
            },
            "required": ["item_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "demandpulse_explain_item",
        "description": (
            "Return the full basis-note breakdown for one published digest "
            "item (latest digest unless digest_id is given). The item must "
            "exist — the bridge never invents one. " + BRIDGE_LABEL
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "opportunity_id to explain",
                },
                "digest_id": {
                    "type": "string",
                    "description": "Optional digest id (default: latest).",
                },
            },
            "required": ["item_id"],
            "additionalProperties": False,
        },
    },
]

_TOOL_NAMES = {t["name"] for t in TOOLS}


def _envelope(
    ok: bool, result: Any = None, error: Optional[str] = None
) -> Dict[str, Any]:
    env: Dict[str, Any] = {"ok": ok, "bridge": BRIDGE_LABEL}
    if ok:
        env["result"] = result
    else:
        env["error"] = error
    return env


def _tool_get_latest(_args: Mapping[str, Any], home: Optional[Path]) -> Dict[str, Any]:
    digest = si.load_latest(home=home)
    return {"digest": digest.to_record() if digest else None}


def _tool_build_digest(args: Mapping[str, Any], home: Optional[Path]) -> Dict[str, Any]:
    # ``cards`` (stored-card form) and ``raw`` (analyst candidates) both
    # funnel through one honesty-checked intake: stored cards are already
    # validated at construction; raw candidates may land in quarantine.
    stored, stored_quarantined = si.coerce_candidates(list(args.get("cards") or []))
    digest = si.curate(
        cards=stored,
        raw=list(args.get("raw") or []),
        digest_id=args.get("digest_id"),
        home=home,
    )
    digest.quarantined.extend(stored_quarantined)
    digest.summary["quarantined"] = len(digest.quarantined)
    path = si.store_digest(digest, home=home)
    return {
        "digest_id": digest.digest_id,
        "path": str(path),
        "summary": digest.summary,
        "rendered": si.render_digest(digest),
    }


def _tool_watch_item(args: Mapping[str, Any], home: Optional[Path]) -> Dict[str, Any]:
    item_id = args.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("item_id must be a non-empty string")
    added = si.watch_item(item_id, home=home)
    return {"item_id": item_id.strip(), "watched": True, "newly_added": added}


def _tool_explain_item(args: Mapping[str, Any], home: Optional[Path]) -> Dict[str, Any]:
    item_id = args.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("item_id must be a non-empty string")
    item_id = item_id.strip()
    digest_id = args.get("digest_id")
    digest = (
        si.load_digest(digest_id, home=home) if digest_id else si.load_latest(home=home)
    )
    if digest is None:
        return {"found": False, "item_id": item_id}
    for item in digest.items:
        if item.get("opportunity_id") == item_id:
            lines = [
                f"[{item.get('opportunity_id')}] {item.get('title')}",
                f"composite={item.get('composite'):.2f}  "
                f"tier={item.get('tier')}  "
                f"alert={'YES' if item.get('alert') else 'no'}",
                "",
            ]
            for f in item.get("factors", []) or []:
                lines.append(
                    f"  {f.get('name')}: {f.get('value')} — basis: {f.get('basis')}"
                )
            if item.get("notes"):
                lines.append("")
                lines.append(f"notes: {item['notes']}")
            lines.append("")
            lines.append(
                "Scores are analyst judgments with stated bases — not measured data."
            )
            return {"found": True, "item_id": item_id, "explanation": "\n".join(lines)}
    return {"found": False, "item_id": item_id}


def execute_tool(
    name: str,
    arguments: Optional[Mapping[str, Any]] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run one bridge tool against the SI core; never fabricates.

    Returns a labeled envelope: {"ok", "bridge", "result"|"error"}.
    Raises ValueError for unknown tool names.
    """
    if name not in _TOOL_NAMES:
        raise ValueError(f"unknown bridge tool {name!r}; known: {sorted(_TOOL_NAMES)}")
    args = dict(arguments or {})
    try:
        if name == "demandpulse_get_latest_digest":
            result = _tool_get_latest(args, home)
        elif name == "demandpulse_build_digest":
            result = _tool_build_digest(args, home)
        elif name == "demandpulse_watch_item":
            result = _tool_watch_item(args, home)
        else:
            result = _tool_explain_item(args, home)
    except (ValueError, TypeError) as exc:
        return _envelope(False, error=str(exc))
    return _envelope(True, result=result)


def as_chat_completion(
    result: Mapping[str, Any], model: str = "demandpulse-bridge"
) -> Dict[str, Any]:
    """Shape a bridge result like a chat-completions response.

    Deterministic: the id derives from the content hash; usage is labeled
    honestly (no model call happened — this is local bridge plumbing).
    """
    content = json.dumps(dict(result), indent=2, sort_keys=True)
    digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return {
        "id": f"dpc-{digest}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": max(1, len(content) // 4),
            "note": "local bridge payload — no model call; SI core is authoritative",
        },
    }
