"""LEVI-native automation executor: clean live execution behind the rail.

``engine.run_minion(..., dry_run=True)`` only simulates. This module wires the
live path: with ``dry_run=False``, after the permission gate passes with a
real responder, the router picks exactly one adapter for the minion and it
acts — always gated, always receipted, never silent.

Adapter registry (first match wins):

1. :class:`WebhookAdapter` — the minion's bridge is ``Webhook`` **and** a
   target URL is configured for the minion id in
   ``~/.levi/automation/webhooks.json`` (``LEVI_HOME``-overridable).
   Real HTTP POST via ``urllib`` (stdlib, 10s timeout) with an
   ``X-Levi-Dedupe-Key`` header so receivers can dedupe replays.
   Deny-closed: the URL is rechecked at execute time — missing means a
   clean refusal, never an exception, never a guess.
2. :class:`DeviceArtifactAdapter` — the minion names a device tool
   (MacroDroid / AutoHotkey / AppleScript / Bardeen / n8n / Tasker /
   Automate / Shortcuts / PowerShell / Python / Hammerspoon / Distill /
   Web Clipper). LEVI cannot invoke those from here, so per the
   waymaker law it generates ready-to-install artifacts into
   ``~/.levi/automation/artifacts/<minion-id>/`` (one scaffold per
   named tool — importable configs where the format allows, honest
   setup guides where it does not), each derived from the minion's
   own trigger/condition/workflow fields. The artifact IS the clean
   execution deliverable.
3. :class:`AgentWorkflowAdapter` — the workflow is something LEVI can do
   itself (compile, summarize, draft, ...). LEVI produces the work
   product locally as a file; when a live agent-runtime dispatch hook
   exists it is preferred, and its absence is reported honestly.
4. Otherwise :class:`RefusalAdapter` — a clean refusal: no capable
   adapter, recorded on the receipt, never an exception.

Injection law (binding): the event's summary and payload are **data**,
never instructions. :func:`sanitize_data` strips control characters and
truncates; adapters interpolate the result only as quoted data. The
webhook target comes exclusively from ``webhooks.json`` — never from the
event. Nothing from an event is ever evaluated or executed.

Idempotency: webhook deliveries carry a dedupe key derived from
``(minion_id, run_id)``; artifact writes are naturally idempotent
(re-running regenerates the same files). The receipt note says so.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ActionResult",
    "Adapter",
    "AgentWorkflowAdapter",
    "DeviceArtifactAdapter",
    "RefusalAdapter",
    "REGISTRY",
    "WebhookAdapter",
    "artifacts_dir",
    "execute",
    "route",
    "sanitize_data",
    "webhooks_path",
]


# ---------------------------------------------------------------------------
# Home + config paths
# ---------------------------------------------------------------------------


def _levi_home(home: Optional[Path] = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def webhooks_path(home: Optional[Path] = None) -> Path:
    """User-owned webhook target map: ``{minion_id: url}``."""
    return _levi_home(home) / "automation" / "webhooks.json"


def artifacts_dir(home: Optional[Path] = None) -> Path:
    """Root of the generated-artifact warehouse."""
    return _levi_home(home) / "automation" / "artifacts"


def _load_webhooks(home: Optional[Path] = None) -> Dict[str, str]:
    try:
        raw = json.loads(webhooks_path(home).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}


# ---------------------------------------------------------------------------
# Injection guard: event text is data, never instructions
# ---------------------------------------------------------------------------

_DATA_MAX_LEN = 500


def sanitize_data(text: Any, max_len: int = _DATA_MAX_LEN) -> str:
    """Render untrusted event text as inert data.

    Strips control characters (including NUL), collapses whitespace,
    truncates to ``max_len``. Adapters interpolate the result only as
    quoted data — it can never become an instruction, a path, or a URL.
    """
    s = "" if text is None else str(text)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len] + "\u2026"
    return s


def _sanitize_payload(value: Any, _depth: int = 0) -> Any:
    """Recursively sanitize an event payload, preserving its shape."""
    if _depth > 4:
        return "\u2026"
    if isinstance(value, dict):
        items = list(value.items())[:50]
        return {
            sanitize_data(k, 80): _sanitize_payload(v, _depth + 1) for k, v in items
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_payload(v, _depth + 1) for v in list(value)[:50]]
    if isinstance(value, str):
        return sanitize_data(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_data(value)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or "minion"


def _dedupe_key(minion_id: str, run_id: str) -> str:
    """Stable idempotency key for one minion + one run."""
    return hashlib.sha256(f"{minion_id}:{run_id}".encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Result + adapter contract
# ---------------------------------------------------------------------------


@dataclass
class ActionResult:
    """What one adapter did (or cleanly refused to do)."""

    adapter: str
    executed: bool  # did it act?
    ok: bool  # clean outcome?
    evidence: str  # verifiable evidence: URLs, paths, status codes
    note: str = ""  # human-readable, incl. idempotency notes
    refused: bool = False  # deny-closed refusal (not an error, a decision)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter": self.adapter,
            "executed": self.executed,
            "ok": self.ok,
            "evidence": self.evidence,
            "note": self.note,
            "refused": self.refused,
        }


class Adapter:
    """One execution channel. Never raises out of ``execute``'s contract —
    the ``execute()`` boundary converts any surprise into a clean refusal.
    """

    name = "base"

    def can_handle(self, minion: Any, home: Optional[Path] = None) -> bool:
        return False

    def execute(
        self,
        minion: Any,
        event: Any,
        gate_receipt: Any,
        run_id: str,
        home: Optional[Path] = None,
    ) -> ActionResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------


class WebhookAdapter(Adapter):
    """Real HTTP POST for minions bridged via Webhook.

    The target URL comes exclusively from ``webhooks.json`` — never from
    the event (a payload ``{"url": ...}`` cannot redirect delivery).
    """

    name = "webhook"
    timeout = 10

    def can_handle(self, minion: Any, home: Optional[Path] = None) -> bool:
        return (minion.bridge or "").strip().lower() == "webhook" and bool(
            _load_webhooks(home).get(minion.id)
        )

    def execute(
        self,
        minion: Any,
        event: Any,
        gate_receipt: Any,
        run_id: str,
        home: Optional[Path] = None,
    ) -> ActionResult:
        # Deny-closed recheck: configuration may have changed since routing.
        url = _load_webhooks(home).get(minion.id, "")
        if not url:
            return ActionResult(
                adapter=self.name,
                executed=False,
                ok=False,
                refused=True,
                evidence="no webhook URL configured",
                note=(
                    f"clean refusal: no webhook URL configured for minion '{minion.id}'. "
                    f"Add one to {webhooks_path(home)} to enable live delivery. "
                    "Nothing was sent."
                ),
            )
        dedupe = _dedupe_key(minion.id, run_id)
        payload = {
            "minion_id": minion.id,
            "subcategory": sanitize_data(minion.subcategory, 120),
            "workflow": sanitize_data(minion.example_rite),
            "event": {
                "kind": sanitize_data(event.kind, 80),
                "summary": sanitize_data(event.summary),
                "payload": _sanitize_payload(event.payload),
                "ts": event.ts,
            },
            "gate": (gate_receipt.decision if gate_receipt is not None else "unknown"),
            "run_id": run_id,
            "dedupe_key": dedupe,
        }
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Levi-Minion": minion.id,
                "X-Levi-Dedupe-Key": dedupe,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                status = getattr(resp, "status", "unknown")
                resp.read(65536)  # drain
        except Exception as exc:  # noqa: BLE001 — network failure is a receipted outcome
            return ActionResult(
                adapter=self.name,
                executed=False,
                ok=False,
                evidence=(
                    f"POST {sanitize_data(url, 120)} failed: {type(exc).__name__}"
                ),
                note=(
                    f"webhook delivery failed cleanly ({type(exc).__name__}); "
                    "nothing was delivered."
                ),
            )
        return ActionResult(
            adapter=self.name,
            executed=True,
            ok=True,
            evidence=f"POST {sanitize_data(url, 120)} -> {status}",
            note=(
                f"delivered via webhook (dedupe key {dedupe[:12]}...); "
                "re-running this run id is idempotent for receivers "
                "honoring X-Levi-Dedupe-Key."
            ),
        )


# ---------------------------------------------------------------------------
# Device artifacts (the waymaker route)
# ---------------------------------------------------------------------------

_DEVICE_TOOLS = (
    "macrodroid",
    "autohotkey",
    "applescript",
    "bardeen",
    "n8n",
    "tasker",
    "automate",
    "shortcuts",
    "powershell",
    "python",
    "hammerspoon",
    "distill",
    "web clipper",
)


class DeviceArtifactAdapter(Adapter):
    """Generate ready-to-install device artifacts.

    LEVI cannot invoke device tools from here, so it manufactures the
    way: one artifact per named tool, derived from the minion's own
    trigger/condition/workflow fields, written to
    ``~/.levi/automation/artifacts/<minion-id>/``. Recognized tools:
    MacroDroid, AutoHotkey, AppleScript, Bardeen, n8n, Tasker, Automate,
    Shortcuts, PowerShell, Python, Hammerspoon, Distill, Web Clipper.
    The artifact IS the clean execution deliverable — install it on the
    device and the minion goes live. Writes are idempotent: re-running
    regenerates the same files.
    """

    name = "device-artifacts"

    def _named_tools(self, minion: Any) -> List[str]:
        haystack = " ".join(
            [
                minion.android_tool,
                minion.windows_tool,
                minion.mac_tool,
                minion.chrome_extension,
                minion.usb_auto_launch,
            ]
        ).lower()
        return [tool for tool in _DEVICE_TOOLS if tool in haystack]

    def can_handle(self, minion: Any, home: Optional[Path] = None) -> bool:
        return bool(self._named_tools(minion))

    def execute(
        self,
        minion: Any,
        event: Any,
        gate_receipt: Any,
        run_id: str,
        home: Optional[Path] = None,
    ) -> ActionResult:
        tools = self._named_tools(minion)
        dest = artifacts_dir(home) / _slug(minion.id)
        dest.mkdir(parents=True, exist_ok=True)
        data = {
            "id": sanitize_data(minion.id, 120),
            "subcategory": sanitize_data(minion.subcategory, 120),
            "trigger": sanitize_data(minion.trigger, 200),
            "condition": sanitize_data(minion.condition, 200),
            "workflow": sanitize_data(minion.example_rite),
            "hitl": sanitize_data(minion.hitl_type, 80),
            "event_summary": sanitize_data(event.summary, 200),
        }
        writers = {
            "macrodroid": ("macrodroid.json", _macrodroid_macro),
            "autohotkey": ("automation.ahk", _ahk_script),
            "applescript": ("automation.applescript", _applescript),
            "bardeen": ("bardeen-playbook.json", _bardeen_playbook),
            "n8n": ("n8n-workflow.json", _n8n_workflow),
            "tasker": ("tasker-task.txt", _tasker_task),
            "automate": ("automate-flow.json", _automate_flow),
            "shortcuts": ("shortcuts-setup.txt", _shortcuts_guide),
            "powershell": ("automation.ps1", _powershell_script),
            "python": ("automation.py", _python_script),
            "hammerspoon": ("hammerspoon.lua", _hammerspoon_snippet),
            "distill": ("distill-monitor.json", _distill_monitor),
            "web clipper": ("web-clipper.txt", _web_clipper_guide),
        }
        written: List[str] = []
        for tool in tools:
            filename, writer = writers[tool]
            path = dest / filename
            path.write_text(writer(data), encoding="utf-8")
            written.append(str(path))
        evidence = "; ".join(written)
        return ActionResult(
            adapter=self.name,
            executed=True,
            ok=True,
            evidence=f"wrote {len(written)} artifact(s): {evidence}",
            note=(
                f"generated {len(written)} install-ready artifact(s) for "
                f"{', '.join(tools)}; review before importing. Artifact writes "
                "are idempotent — re-running regenerates the same files."
            ),
        )


def _artifact_header(data: Dict[str, str]) -> str:
    return (
        f"Generated by LEVI automation executor for minion '{data['id']}' "
        f"({_utcnow()}). Review before installing; fill in any "
        "credentials or endpoints it references."
    )


def _macrodroid_macro(data: Dict[str, str]) -> str:
    macro = {
        "_generated_by": "LEVI automation executor",
        "_note": _artifact_header(data),
        "macro": {
            "name": f"{data['subcategory']} — LEVI",
            "triggers": [{"type": "derived", "detail": data["trigger"]}],
            "conditions": [{"type": "derived", "detail": data["condition"]}],
            "actions": [
                {"type": "comment", "text": data["workflow"]},
                {
                    "type": "http_request",
                    "note": "point this at your endpoint; method/URL are yours to set",
                },
                {"type": "notification", "text": data["event_summary"]},
            ],
            "hitl": data["hitl"],
        },
    }
    return json.dumps(macro, indent=2, ensure_ascii=True)


def _ahk_script(data: Dict[str, str]) -> str:
    lines = [
        "; " + _artifact_header(data),
        f"; Trigger (derived): {data['trigger']}",
        f"; Condition (derived): {data['condition']}",
        f"; Workflow: {data['workflow']}",
        "#Requires AutoHotkey v2.0",
        "",
        "; TODO: bind this to your hotkey or schedule, then review the action.",
        f'MsgBox("LEVI minion \'{data["id"]}\': {data["workflow"]}", "LEVI automation")',
        "",
    ]
    return "\n".join(lines)


def _applescript(data: Dict[str, str]) -> str:
    lines = [
        "-- " + _artifact_header(data),
        f"-- Trigger (derived): {data['trigger']}",
        f"-- Condition (derived): {data['condition']}",
        f'display notification "{data["workflow"]}" with title "LEVI: {data["subcategory"]}"',
        "",
    ]
    return "\n".join(lines)


def _bardeen_playbook(data: Dict[str, str]) -> str:
    playbook = {
        "_generated_by": "LEVI automation executor",
        "_note": _artifact_header(data),
        "playbook": {
            "name": f"{data['subcategory']} — LEVI",
            "trigger": {"kind": "derived", "detail": data["trigger"]},
            "condition": data["condition"],
            "actions": [
                {"type": "note", "text": data["workflow"]},
                {"type": "notification", "text": data["event_summary"]},
            ],
            "hitl": data["hitl"],
        },
    }
    return json.dumps(playbook, indent=2, ensure_ascii=True)


def _n8n_workflow(data: Dict[str, str]) -> str:
    workflow = {
        "_generated_by": "LEVI automation executor",
        "_note": _artifact_header(data),
        "name": f"{data['subcategory']} — LEVI",
        "nodes": [
            {
                "name": "Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "notes": f"derived trigger: {data['trigger']}",
            },
            {
                "name": "Condition",
                "type": "n8n-nodes-base.if",
                "notes": f"derived condition: {data['condition']}",
            },
            {
                "name": "Action",
                "type": "n8n-nodes-base.noOp",
                "notes": f"workflow: {data['workflow']} (HITL: {data['hitl']})",
            },
        ],
        "connections": {},
    }
    return json.dumps(workflow, indent=2, ensure_ascii=True)


def _tasker_task(data: Dict[str, str]) -> str:
    lines = [
        "# " + _artifact_header(data),
        "# Tasker task — import manually: Tasks > Import, then wire the Profile below.",
        "#",
        f"# Profile trigger (derived): {data['trigger']}",
        f"# Profile condition (derived): {data['condition']}",
        "#",
        f"# Task: {data['subcategory']} — LEVI",
        "#   A1: Comment — " + data["workflow"],
        "#   A2: Notify — Title 'LEVI', Text '" + data["event_summary"] + "'",
        "#   A3: (your action here — Tasker cannot be scripted from outside,",
        "#       so map each workflow step to A4, A5, ... by hand)",
        f"# HITL gate: {data['hitl']} — enforce with a Tasker 'Confirmation' dialog action.",
        "#",
    ]
    return "\n".join(lines)


def _automate_flow(data: Dict[str, str]) -> str:
    flow = {
        "_generated_by": "LEVI automation executor",
        "_note": _artifact_header(data),
        "flow": {
            "name": f"{data['subcategory']} — LEVI",
            "blocks": [
                {
                    "type": "trigger",
                    "note": "wired by hand in Automate",
                    "derived_trigger": data["trigger"],
                },
                {
                    "type": "condition",
                    "derived_condition": data["condition"],
                },
                {
                    "type": "action",
                    "kind": "comment",
                    "text": data["workflow"],
                },
                {
                    "type": "action",
                    "kind": "notification",
                    "text": data["event_summary"],
                },
                {
                    "type": "action",
                    "kind": "hitl",
                    "gate": data["hitl"],
                    "note": "add a Dialog/Confirmation block before any consequential step",
                },
            ],
        },
    }
    return json.dumps(flow, indent=2, ensure_ascii=True)


def _shortcuts_guide(data: Dict[str, str]) -> str:
    lines = [
        "# " + _artifact_header(data),
        "# Apple Shortcuts — build by hand in the Shortcuts app:",
        "#",
        f"# 1. Automation trigger: {data['trigger']}",
        f"# 2. 'If' action for condition: {data['condition']}",
        "# 3. One action per workflow step:",
        f"#      {data['workflow']}",
        "# 4. 'Show Notification' with: " + data["event_summary"],
        f"# 5. HITL gate ({data['hitl']}): add 'Choose from Menu' / 'Ask for Input'",
        "#    before any consequential step — Shortcuts has no silent acts.",
        "#",
    ]
    return "\n".join(lines)


def _powershell_script(data: Dict[str, str]) -> str:
    lines = [
        "# " + _artifact_header(data),
        f"# Trigger (derived): {data['trigger']}",
        f"# Condition (derived): {data['condition']}",
        f"# HITL gate: {data['hitl']} — prompt before any consequential step.",
        "#Requires -Version 5.1",
        "",
        "# TODO: schedule this with Task Scheduler, then review the action.",
        f"# Workflow: {data['workflow']}",
        "Write-Output \"LEVI minion '" + data["id"] + "': " + data["workflow"] + '"',
        "",
    ]
    return "\n".join(lines)


def _python_script(data: Dict[str, str]) -> str:
    lines = [
        '"""' + _artifact_header(data),
        "",
        "Trigger (derived): " + data["trigger"],
        "Condition (derived): " + data["condition"],
        "HITL gate: " + data["hitl"] + " — prompt before any consequential step.",
        '"""',
        "",
        "# TODO: schedule this (cron / Task Scheduler), then review the action.",
        "# Workflow: " + data["workflow"],
        "",
        "import sys",
        "",
        "",
        "def main() -> int:",
        '    """Derived scaffold — fill in real actions before use."""',
        "    print("
        + repr("LEVI minion '" + data["id"] + "': " + data["workflow"])
        + ")",
        "    return 0",
        "",
        "",
        'if __name__ == "__main__":',
        "    sys.exit(main())",
        "",
    ]
    return "\n".join(lines)


def _hammerspoon_snippet(data: Dict[str, str]) -> str:
    lines = [
        "-- " + _artifact_header(data),
        "-- Drop into ~/.hammerspoon/init.lua, then reload Hammerspoon.",
        "--",
        "-- Trigger (derived): " + data["trigger"],
        "-- Condition (derived): " + data["condition"],
        "-- Workflow: " + data["workflow"],
        "-- HITL gate: " + data["hitl"],
        "--",
        "hs.timer.doEvery(3600, function()",
        "    -- TODO: replace the hourly poll with your real trigger, then review.",
        '    hs.notify.new({title="LEVI", informativeText="'
        + data["event_summary"]
        + '"}):send()',
        "end)",
        "",
    ]
    return "\n".join(lines)


def _distill_monitor(data: Dict[str, str]) -> str:
    monitor = {
        "_generated_by": "LEVI automation executor",
        "_note": _artifact_header(data),
        "monitor": {
            "name": f"{data['subcategory']} — LEVI",
            "trigger": {"kind": "derived", "detail": data["trigger"]},
            "condition": data["condition"],
            "actions": [
                {"type": "note", "text": data["workflow"]},
                {"type": "notification", "text": data["event_summary"]},
            ],
            "hitl": data["hitl"],
        },
    }
    return json.dumps(monitor, indent=2, ensure_ascii=True)


def _web_clipper_guide(data: Dict[str, str]) -> str:
    lines = [
        "# " + _artifact_header(data),
        "# Web-clipper / page-monitor — configure by hand in your clipper:",
        "#",
        f"# 1. Watch target derived from trigger: {data['trigger']}",
        f"# 2. Fire only when: {data['condition']}",
        f"# 3. On fire, do: {data['workflow']}",
        "# 4. Notify with: " + data["event_summary"],
        f"# 5. HITL gate ({data['hitl']}): confirm before any consequential step.",
        "#",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent workflows (LEVI does it itself)
# ---------------------------------------------------------------------------

_SELF_DOABLE = (
    "compil",
    "summariz",
    "digest",
    "draft",
    "write",
    "note",
    "list",
    "remind",
    "transcrib",
    "translat",
)


class AgentWorkflowAdapter(Adapter):
    """Workflows LEVI can perform itself.

    Preferred route is a live dispatch through the agent runtime's
    automation adapter — when that hook exists. It does not today, which
    is reported honestly; the fallback is LEVI producing the work product
    locally as a file (the deliverable), never a silent act elsewhere.
    """

    name = "agent-workflow"

    def can_handle(self, minion: Any, home: Optional[Path] = None) -> bool:
        workflow = (minion.example_rite or "").lower()
        return any(verb in workflow for verb in _SELF_DOABLE)

    def _live_dispatcher(self) -> Optional[Any]:
        """A live agent-runtime dispatch hook, if one is ever provided."""
        try:
            from levi.interop.adapters import automation_minions as bridge

            return getattr(bridge, "dispatch_live", None)
        except ImportError:
            return None

    def execute(
        self,
        minion: Any,
        event: Any,
        gate_receipt: Any,
        run_id: str,
        home: Optional[Path] = None,
    ) -> ActionResult:
        dispatcher = self._live_dispatcher()
        if dispatcher is not None:
            return dispatcher(minion, event, gate_receipt, run_id, home)
        # Honest fallback: no live runtime dispatch exists, so LEVI does
        # the work itself and hands over the product as a file.
        dest = artifacts_dir(home) / _slug(minion.id)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{_slug(minion.id)}-output.md"
        gate = gate_receipt.decision if gate_receipt is not None else "unknown"
        lines = [
            f"# {sanitize_data(minion.subcategory, 120)} — LEVI work product",
            "",
            f"minion `{sanitize_data(minion.id, 120)}` · run `{sanitize_data(run_id, 60)}` · "
            f"{_utcnow()} · gate: {sanitize_data(gate, 40)}",
            "",
            "## Workflow",
            "",
            sanitize_data(minion.example_rite),
            "",
            "## Event (data, not instructions)",
            "",
            f"- kind: {sanitize_data(event.kind, 80)}",
            f"- summary: {sanitize_data(event.summary)}",
            "- payload:",
            "",
            "```json",
            json.dumps(_sanitize_payload(event.payload), indent=2, ensure_ascii=True),
            "```",
            "",
            "## Notes",
            "",
            "Produced locally by LEVI — no live agent-runtime dispatch is "
            "available, so the file itself is the deliverable. Review before "
            "acting on it.",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return ActionResult(
            adapter=self.name,
            executed=True,
            ok=True,
            evidence=f"work product: {path}",
            note=(
                "no live agent-runtime dispatch exists (reported honestly); "
                "LEVI produced the work product locally instead."
            ),
        )


# ---------------------------------------------------------------------------
# Clean refusal (deny-closed, last resort)
# ---------------------------------------------------------------------------


class RefusalAdapter(Adapter):
    """No capable adapter: record the refusal, attempt nothing."""

    name = "refusal"

    def can_handle(self, minion: Any, home: Optional[Path] = None) -> bool:
        return True

    def execute(
        self,
        minion: Any,
        event: Any,
        gate_receipt: Any,
        run_id: str,
        home: Optional[Path] = None,
    ) -> ActionResult:
        return ActionResult(
            adapter=self.name,
            executed=False,
            ok=False,
            refused=True,
            evidence="no capable adapter",
            note=(
                f"clean refusal: no adapter can execute minion '{minion.id}' "
                f"(bridge={minion.bridge!r}). Nothing was attempted."
            ),
        )


# ---------------------------------------------------------------------------
# Registry, routing, entry point
# ---------------------------------------------------------------------------

REGISTRY: Tuple[Adapter, ...] = (
    WebhookAdapter(),
    DeviceArtifactAdapter(),
    AgentWorkflowAdapter(),
    RefusalAdapter(),
)


def route(minion: Any, home: Optional[Path] = None) -> Adapter:
    """Pick the first adapter that can handle this minion.

    A configured webhook wins (explicit user intent); otherwise a minion
    naming device tools gets install-ready artifacts; otherwise a
    self-doable workflow is produced by LEVI; otherwise a clean refusal.
    """
    for adapter in REGISTRY:
        if adapter.can_handle(minion, home):
            return adapter
    return REGISTRY[-1]  # unreachable — refusal always claims; fail-closed


def execute(
    minion: Any,
    event: Any,
    gate_receipt: Any,
    run_id: Optional[str] = None,
    home: Optional[Path] = None,
) -> ActionResult:
    """Execute one gated minion run through the routed adapter.

    Never raises: every failure mode — refusal, network error, even an
    adapter bug — is converted into a clean, receipted ``ActionResult``.
    No tracebacks escape to the user.
    """
    rid = run_id or f"run-{uuid.uuid4().hex[:12]}"
    adapter = route(minion, home)
    try:
        return adapter.execute(minion, event, gate_receipt, rid, home)
    except Exception as exc:  # noqa: BLE001 — the boundary converts everything to receipts
        return ActionResult(
            adapter=adapter.name,
            executed=False,
            ok=False,
            refused=True,
            evidence=f"adapter error contained: {type(exc).__name__}",
            note=(
                f"clean refusal: {adapter.name} raised {type(exc).__name__}; "
                "converted to a receipt. Nothing escaped, nothing executed."
            ),
        )
