"""LEVI cross-device bridge: registry + honest outbox dispatch.

A device registry persists at ``<LEVI_HOME>/automation/devices.json``
(``LEVI_HOME``-overridable, same pattern as ``..executor._levi_home``).
Each device knows its kind (``phone`` | ``workstation``), its
capabilities, and whether it runs Termux.

:func:`dispatch_to_device` renders a device-executable dispatch and
writes it to ``<LEVI_HOME>/automation/device_outbox/<device_id>/`` —
a timestamped manifest JSON plus a runnable script (bash for Termux
phones, Python for workstations, following the existing Termux helper
emit convention from ``..browser.emit_termux_helper``).

Honest map: this sandbox cannot reach the real phone, so the outbox dir
IS the handoff point, not a live delivery. The phone side (Termux:
Tasker, a polling loop, or Syncthing + Termux:Tasker "file modified"
profile) picks the files up — documented in the generated scripts.
Never claim live delivery that can't be verified.

Workflow integration: a ``device`` action node handler,
``handle(node, ctx, run) -> {"ok", "output", "evidence"}``, registered
with the engine via :func:`register_device_action`. Node config::

    {"device_id": "my-phone", "action": "send-sms",
     "args": {"to": "+1555...", "text": "..."}}
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "devices_path",
    "outbox_dir",
    "register_device",
    "list_devices",
    "get_device",
    "dispatch_to_device",
    "handle",
    "register_device_action",
]

_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_KINDS = ("phone", "workstation")


# ---------------------------------------------------------------------------
# Home + paths
# ---------------------------------------------------------------------------


def _levi_home(home: Optional[Path] = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def devices_path(home: Optional[Path] = None) -> Path:
    """Registry file: ``<LEVI_HOME>/automation/devices.json``."""
    return _levi_home(home) / "automation" / "devices.json"


def outbox_dir(device_id: str, home: Optional[Path] = None) -> Path:
    """Outbox dir for a device: ``<LEVI_HOME>/automation/device_outbox/<id>/``."""
    _check_device_id(device_id)
    return _levi_home(home) / "automation" / "device_outbox" / device_id


def _utcnow() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _check_device_id(device_id: str) -> str:
    if not isinstance(device_id, str) or not _DEVICE_ID_RE.match(device_id):
        raise ValueError(f"bad device_id {device_id!r}")
    return device_id


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _load_registry(home: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(devices_path(home).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict) or not isinstance(raw.get("devices"), list):
        return {}
    reg: Dict[str, Dict[str, Any]] = {}
    for entry in raw["devices"]:
        if isinstance(entry, dict) and isinstance(entry.get("device_id"), str):
            reg[entry["device_id"]] = entry
    return reg


def _save_registry(reg: Dict[str, Dict[str, Any]], home: Optional[Path] = None) -> None:
    path = devices_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [reg[key] for key in sorted(reg)]
    path.write_text(
        json.dumps({"devices": ordered}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def register_device(
    device_id: str,
    kind: str,
    label: str,
    capabilities: Optional[List[str]] = None,
    termux: bool = False,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Register (or update) a device. Returns the stored record."""
    _check_device_id(device_id)
    if kind not in _KINDS:
        raise ValueError(f"kind must be one of {_KINDS}, got {kind!r}")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label must be a non-empty string")
    caps = list(capabilities or [])
    if not all(isinstance(c, str) for c in caps):
        raise TypeError("capabilities must be a list of strings")

    reg = _load_registry(home)
    record = {
        "device_id": device_id,
        "kind": kind,
        "label": label.strip(),
        "capabilities": caps,
        "termux": bool(termux),
        "registered_at": _utcnow(),
    }
    reg[device_id] = record
    _save_registry(reg, home)
    return dict(record)


def list_devices(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """All registered devices, sorted by device_id."""
    reg = _load_registry(home)
    return [dict(reg[key]) for key in sorted(reg)]


def get_device(device_id: str, home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """One device record, or ``None``."""
    _check_device_id(device_id)
    record = _load_registry(home).get(device_id)
    return dict(record) if record is not None else None


# ---------------------------------------------------------------------------
# Dispatch — render to outbox (the handoff point)
# ---------------------------------------------------------------------------


def _termux_script(
    device_id: str, stamp: str, action: str, args: Dict[str, Any]
) -> str:
    args_json = json.dumps(args, indent=2, ensure_ascii=True)
    return "\n".join(
        [
            "#!/data/data/com.termux/files/usr/bin/bash",
            f"# LEVI device dispatch for '{device_id}' — generated {_utcnow()}",
            f"# Action: {action}",
            "#",
            "# PICKUP: this sandbox cannot reach the phone, so this file lands in",
            "# the device outbox (see dispatch-*.json next to it). Sync the outbox",
            "# to the phone (Syncthing / adb push) and let Termux:Tasker execute",
            "# it, or run it manually inside Termux.",
            "set -e",
            f'INBOX="$HOME/.levi-automation-inbox/{device_id}"',
            'mkdir -p "$INBOX"',
            f"ACTION={json.dumps(action)}",
            f"cat > \"$INBOX/args-{stamp}.json\" <<'LEVI_ARGS_EOF'",
            args_json,
            "LEVI_ARGS_EOF",
            f'echo "[LEVI] action $ACTION staged; args at $INBOX/args-{stamp}.json"',
            "",
        ]
    )


def _workstation_script(
    device_id: str, stamp: str, action: str, args: Dict[str, Any]
) -> str:
    args_json = json.dumps(args, indent=2, ensure_ascii=True)
    return "\n".join(
        [
            "#!/usr/bin/env python3",
            f'"""LEVI device dispatch for {device_id!r} — generated {_utcnow()}."""',
            f'"""Action: {action}."""',
            "",
            "import json, sys",
            "",
            f"ACTION = {action!r}",
            f"ARGS = json.loads({args_json!r})",
            "",
            "def main() -> int:",
            '    print(f"[LEVI] workstation {ACTION} — args:")',
            "    print(json.dumps(ARGS, indent=2))",
            "    # TODO: wire this action to the workstation's real handler.",
            "    return 0",
            "",
            'if __name__ == "__main__":',
            "    sys.exit(main())",
            "",
        ]
    )


def dispatch_to_device(
    device_id: str, command: Dict[str, Any], home: Optional[Path] = None
) -> Dict[str, Any]:
    """Render ``command`` to the device's outbox dir. Returns receipt dict.

    ``command`` = ``{"action": str, "args": dict}``. Raises
    :class:`ValueError` on a bad command and the engine's
    :class:`FlowError` for an unknown device — deny-closed either way.
    """
    try:
        from ..flows import FlowError
    except ImportError:  # pragma: no cover — flows is always importable

        class FlowError(Exception):  # type: ignore[no-redef]
            pass

    _check_device_id(device_id)
    device = get_device(device_id, home)
    if device is None:
        raise FlowError(f"unknown device {device_id!r}")

    if not isinstance(command, dict):
        raise TypeError("command must be a dict")
    action = command.get("action")
    args = command.get("args", {})
    if not isinstance(action, str) or not action.strip():
        raise ValueError("command needs a non-empty 'action' string")
    if not isinstance(args, dict):
        raise TypeError("command 'args' must be a dict")

    stamp = _utcnow().replace(":", "").replace("-", "")
    short = uuid.uuid4().hex[:8]
    record = {
        "dispatch_id": f"{stamp}-{short}",
        "device_id": device_id,
        "action": action,
        "args": dict(args),
        "device": {
            "kind": device["kind"],
            "label": device["label"],
            "termux": device["termux"],
        },
        "dispatched_at": _utcnow(),
        "handoff": "outbox dir (sync to device; see script header for pickup)",
    }

    box = outbox_dir(device_id, home)
    box.mkdir(parents=True, exist_ok=True)
    manifest = box / f"dispatch-{stamp}-{short}.json"
    manifest.write_text(
        json.dumps(record, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    if device["kind"] == "phone" and device["termux"]:
        script_name = f"run-{stamp}-{short}.sh"
        script_text = _termux_script(device_id, f"{stamp}-{short}", action, args)
    else:
        script_name = f"run-{stamp}-{short}.py"
        script_text = _workstation_script(device_id, f"{stamp}-{short}", action, args)
    script_path = box / script_name
    script_path.write_text(script_text, encoding="utf-8")
    script_path.chmod(0o755)

    return {
        "ok": True,
        "dispatch_id": record["dispatch_id"],
        "device_id": device_id,
        "outbox": str(box),
        "files": [manifest.name, script_name],
        "evidence": f"dispatch {record['dispatch_id']} staged in outbox {box}",
    }


# ---------------------------------------------------------------------------
# Workflow integration
# ---------------------------------------------------------------------------


def handle(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    """``device`` action node handler.

    Node config: ``{"device_id": str, "action": str, "args": dict}``.
    Returns ``{"ok", "output", "evidence"}``; raises
    :class:`FlowError` on misconfiguration or unknown devices.
    """
    try:
        from ..flows import FlowError
    except ImportError:  # pragma: no cover — flows is always importable

        class FlowError(Exception):  # type: ignore[no-redef]
            pass

    config = (node or {}).get("config") or {}
    if not isinstance(config, dict):
        raise FlowError("device node: 'config' must be a dict")
    device_id = config.get("device_id")
    action = config.get("action")
    args = config.get("args", {})
    if not device_id:
        raise FlowError("device node: 'device_id' required in config")
    if not action:
        raise FlowError("device node: 'action' required in config")

    receipt = dispatch_to_device(str(device_id), {"action": action, "args": args or {}})
    return {
        "ok": True,
        "output": f"dispatched {action} to {device_id}",
        "evidence": receipt,
    }


def register_device_action() -> bool:
    """Register the ``device`` node kind with the engine.

    Returns ``True`` on success, ``False`` if the engine's registration
    surface isn't available yet — so this module imports cleanly while
    the sibling's ``register_node_kind`` work lands.
    """
    try:
        from ..flows import register_node_kind
    except ImportError:
        return False
    register_node_kind("device", handle)
    return True
