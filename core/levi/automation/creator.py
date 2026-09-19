"""``levi automate`` — IFTTT-style workflow creator.

Guided "when THIS, do THAT" builder that assembles node-graph flows in the
:mod:`levi.automation.flows` format, validates them with
:func:`~levi.automation.flows.build_flow`, and persists them under
``<LEVI_HOME>/automation/flows/``.

Node-kind honesty: :data:`levi.automation.flows.NODE_KINDS` currently admits
``minion``, ``predicate``, ``emit``, and ``note`` only. Actions whose kind is
*not* one of those (``webhook-out``, ``python``, ``macro``, ``google-tasks``,
``google-sheets``) are stored as ``emit`` nodes that write the action request
into the run context as JSON — a real, valid node the runner accepts — so a
created workflow always validates today and can be swapped for a native node
kind when one lands.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import flows
from .minions import MINIONS, find_minion

__all__ = [
    "FlowBuildError",
    "ACTION_KINDS",
    "TRIGGER_TYPES",
    "slugify",
    "build_workflow",
    "save_workflow",
    "render_preview",
    "describe_trigger",
]


class FlowBuildError(ValueError):
    """The workflow could not be built or saved."""


ACTION_KINDS = (
    "minion",
    "webhook-out",
    "python",
    "macro",
    "google-tasks",
    "google-sheets",
)
TRIGGER_TYPES = ("manual", "schedule", "webhook-in")

# Action kinds that have a native flows.py node kind; everything else rides
# on an ``emit`` node carrying the request payload.
_NATIVE_ACTION_KINDS = {"minion"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a workflow name into a flow id. Deny-closed on empty slugs."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise FlowBuildError(f"cannot slugify empty name {name!r}")
    return slug


def describe_trigger(trigger_spec: Dict[str, Any]) -> str:
    """Human-readable trigger description, e.g. 'schedule */5 * * * *'."""
    trigger_type = (trigger_spec or {}).get("trigger_type", "")
    if trigger_type == "manual":
        return "manually run"
    if trigger_type == "schedule":
        return f"schedule {trigger_spec.get('cron', '')}".strip()
    if trigger_type == "webhook-in":
        return f"webhook {trigger_spec.get('path', '')}".strip()
    return f"trigger {trigger_type or '?'}"


def _check_trigger(trigger_spec: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(trigger_spec, dict):
        raise FlowBuildError("trigger_spec must be a dict")
    trigger_type = trigger_spec.get("trigger_type", "")
    if trigger_type not in TRIGGER_TYPES:
        raise FlowBuildError(
            f"unknown trigger_type {trigger_type!r} (use {TRIGGER_TYPES})"
        )
    if trigger_type == "schedule" and not trigger_spec.get("cron"):
        raise FlowBuildError("schedule trigger needs a 'cron' value")
    if trigger_type == "webhook-in" and not trigger_spec.get("path"):
        raise FlowBuildError("webhook-in trigger needs a 'path' value")
    return trigger_spec


def _action_nodes(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(actions, list) or not actions:
        raise FlowBuildError("a workflow needs at least one action")
    nodes: List[Dict[str, Any]] = []
    for i, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise FlowBuildError(f"action {i}: must be a dict")
        kind = action.get("kind", "")
        if kind not in ACTION_KINDS:
            raise FlowBuildError(f"action {i}: unknown kind {kind!r}")
        label = str(action.get("label", "")).strip()
        if not label:
            raise FlowBuildError(f"action {i}: needs a label")
        config = action.get("config") or {}
        if not isinstance(config, dict):
            raise FlowBuildError(f"action {i}: config must be a dict")
        node_id = f"a{i}"
        if kind in _NATIVE_ACTION_KINDS:
            minion_id = str(config.get("minion_id", "")).strip()
            if not minion_id:
                raise FlowBuildError(f"action {i} (minion): config needs 'minion_id'")
            if find_minion(MINIONS, minion_id) is None:
                raise FlowBuildError(
                    f"action {i}: unknown minion {minion_id!r} — "
                    "minion actions must reference the catalog"
                )
            nodes.append(
                {
                    "id": node_id,
                    "kind": "minion",
                    "label": label,
                    "minion_id": minion_id,
                }
            )
        else:
            # No native node kind for this action yet: carry the request as
            # an emit so the flow still validates and runs (dry or live).
            payload = json.dumps(
                {"kind": kind, "label": label, "config": config}, sort_keys=True
            )
            nodes.append(
                {
                    "id": node_id,
                    "kind": "emit",
                    "label": f"{kind}: {label}",
                    # The expr language has no object literals, so the action
                    # request rides as a JSON string literal (double-decoded).
                    "set": {f"action_{node_id}": json.dumps(payload)},
                }
            )
    return nodes


def build_workflow(
    name: str,
    trigger_spec: Dict[str, Any],
    actions: List[Dict[str, Any]],
    condition: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble a valid flow JSON from an IFTTT-style description.

    ``trigger_spec`` is ``{"trigger_type": "manual"|"schedule"|"webhook-in",
    "cron": ..., "path": ...}``. ``actions`` is a list of
    ``{"kind": ..., "label": ..., "config": {...}}``. An optional
    ``condition`` becomes a predicate node between the trigger and the
    actions. Node ids are deterministic: ``trigger``, ``cond``, ``a1``...
    Raises :class:`FlowBuildError` if the flow fails validation.
    """
    flow_id = slugify(name)
    _check_trigger(trigger_spec)
    action_nodes = _action_nodes(actions)

    nodes: List[Dict[str, Any]] = [
        {
            "id": "trigger",
            "kind": "note",
            "label": f"WHEN {describe_trigger(trigger_spec)}",
            "text": json.dumps(trigger_spec, sort_keys=True),
        }
    ]
    chain = ["trigger"]
    if condition:
        nodes.append(
            {
                "id": "cond",
                "kind": "predicate",
                "label": "condition?",
                "expr": str(condition),
            }
        )
        chain.append("cond")
    for node in action_nodes:
        nodes.append(node)
        chain.append(node["id"])

    edges = [
        {"id": f"e{i}", "from": src, "to": dst}
        for i, (src, dst) in enumerate(zip(chain, chain[1:], strict=False), start=1)
    ]

    flow = {
        "id": flow_id,
        "name": name,
        "description": describe_trigger(trigger_spec),
        "start": "trigger",
        "nodes": nodes,
        "edges": edges,
    }
    try:
        return flows.build_flow(flow)
    except flows.FlowError as exc:
        raise FlowBuildError(f"built flow failed validation: {exc}") from exc


def save_workflow(
    flow: Dict[str, Any],
    home: "str | Path | None" = None,
    overwrite: bool = False,
) -> Path:
    """Persist a built flow under ``<LEVI_HOME>/automation/flows/<id>.json``.

    Refuses to overwrite an existing id unless ``overwrite=True``.
    Returns the written path.
    """
    flow_id = str(flow.get("id", ""))
    target = flows.flows_home(home) / f"{flow_id}.json"
    if target.exists() and not overwrite:
        raise FlowBuildError(
            f"workflow id {flow_id!r} already exists — pass overwrite=True to replace"
        )
    try:
        return flows.save_flow(flow, home=home)
    except flows.FlowError as exc:
        raise FlowBuildError(f"cannot save workflow: {exc}") from exc


def render_preview(flow: Dict[str, Any]) -> str:
    """Mermaid flowchart plus a human-readable WHEN/THEN step list."""
    mermaid = flows.to_mermaid(flow)
    by_id = {n["id"]: n for n in flow["nodes"]}
    trigger = by_id.get(flow["start"], {})
    trigger_label = trigger.get("label", flow["start"])
    if trigger_label.startswith("WHEN "):
        trigger_label = trigger_label[len("WHEN ") :]
    labels = [n["label"] for n in flow["nodes"] if n["id"] != flow["start"]]
    step_line = f"WHEN {trigger_label} THEN " + " → ".join(labels)
    return f"{mermaid}\n\n{step_line}"
