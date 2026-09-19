"""LEVI-native Google node packs — Google Tasks and Google Sheets actions.

Both run through the vendored ``hatch_gws_cli`` (see the ``google_tasks``
and ``google_sheets`` skill contracts). The standing rule is the AUTH
GATE: the first thing any handler does is ``hatch_gws_cli <svc> status``.
If the account is not connected the node returns ``{"ok": False,
"needs_auth": ...}`` with a connect hint — it never fakes data, never
invents task or row ids. The preview line says so too: "gated: needs
Chauncey's Google sign-in".

Subprocess is argv-list only, never ``shell=True``. Stdout is parsed as
JSON; raw command text never leaks into user-facing evidence.

Node kinds registered here: ``google-tasks``, ``google-sheets``.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    # The engine extension adds register_node_kind; until it lands the
    # import fails and registrations are deferred to ensure_registered().
    from .flows import FlowError, register_node_kind
except ImportError:  # pragma: no cover - until the engine extension lands
    from .flows import FlowError

    register_node_kind = None  # type: ignore[assignment]

from .nodes import _cfg, sanitize_secrets

__all__ = [
    "handle_google_tasks",
    "preview_google_tasks",
    "handle_google_sheets",
    "preview_google_sheets",
    "cli_status",
    "ensure_registered",
]

_CLI = "hatch_gws_cli"
_GATED_PREVIEW = "gated: needs Chauncey's Google sign-in"


# ---------------------------------------------------------------------------
# CLI plumbing (argv lists only — never shell=True)
# ---------------------------------------------------------------------------


def _run_cli(argv: List[str], timeout_s: float = 30.0) -> Tuple[int, str, str]:
    """Run the vendored CLI. Tests monkeypatch this — never real Google."""
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, fixed binary
            argv, capture_output=True, text=True, timeout=timeout_s
        )
    except FileNotFoundError:
        return 127, "", f"{_CLI} not installed on this machine"
    except subprocess.TimeoutExpired:
        return 124, "", f"{_CLI} timed out after {timeout_s}s"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def cli_status(service: str) -> Dict[str, Any]:
    """Parse ``hatch_gws_cli <service> status`` into a dict.

    Honest about every failure mode: unparseable output, a missing CLI,
    or a non-zero exit all surface as ``status: "unavailable"`` — never
    as connected.
    """
    code, out, err = _run_cli([_CLI, service, "status"], timeout_s=15.0)
    if code != 0:
        return {
            "status": "unavailable",
            "detail": sanitize_secrets((err or out).strip()[:300] or f"exit {code}"),
        }
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"status": "unavailable", "detail": "status output not JSON"}
    if not isinstance(data, dict):
        return {"status": "unavailable", "detail": "status output not an object"}
    return data


def _is_connected(status_data: Dict[str, Any]) -> bool:
    return str(status_data.get("status", "")).lower() == "connected"


def _auth_gate(service: str, label: str) -> Optional[Dict[str, Any]]:
    """The gate every Google handler walks through first.

    Returns None when connected (proceed), else the honest gated result —
    never fake data, never invented ids.
    """
    data = cli_status(service)
    if _is_connected(data):
        return None
    return {
        "ok": False,
        "needs_auth": label,
        "connect_hint": (
            f"run `{_CLI} {service} status` and follow the connect link "
            "— Chauncey's sign-in required"
        ),
        "output": {},
    }


def _looks_like_auth_failure(code: int, out: str, err: str) -> bool:
    hay = f"{out}\n{err}".lower()
    return code != 0 and any(
        token in hay
        for token in (
            "not_connected",
            "not connected",
            "unauthorized",
            "invalid_grant",
            "auth",
            "401",
            "403",
        )
    )


def _parse_result(
    code: int, out: str, err: str, service: str, label: str, what: str
) -> Dict[str, Any]:
    """Turn one CLI invocation into the handler result dict."""
    if _looks_like_auth_failure(code, out, err):
        # The token died mid-run: re-check status and gate honestly.
        gate = _auth_gate(service, label)
        if gate is not None:
            return gate
    if code != 0:
        detail = sanitize_secrets((err or out).strip()[:500] or f"exit {code}")
        return {
            "ok": False,
            "output": {"error": detail},
            "evidence": f"{what}: failed — {detail}",
        }
    try:
        parsed = json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        parsed = {"raw": sanitize_secrets(out[:2000])}
    if not isinstance(parsed, dict):
        parsed = {"raw": sanitize_secrets(str(parsed)[:2000])}
    return {
        "ok": True,
        "output": parsed,
        "evidence": f"{what}: ok",
    }


# ---------------------------------------------------------------------------
# google-tasks action
# ---------------------------------------------------------------------------

_TASKS_OPS = ("list", "insert", "complete")


def _tasks_argv(cfg: Dict[str, Any]) -> Tuple[List[str], str]:
    """Build the exact argv for one tasks op. Deny-closed on bad config."""
    op = str(cfg.get("op", "list"))
    if op not in _TASKS_OPS:
        raise FlowError(f"google-tasks: unknown op {op!r} (use {_TASKS_OPS})")
    tasklist = cfg.get("tasklist", "@default")
    if not isinstance(tasklist, str) or not tasklist.strip():
        raise FlowError("google-tasks: 'tasklist' must be a non-empty string")
    tasklist = tasklist.strip()

    if op == "list":
        params: Dict[str, Any] = {"tasklist": tasklist}
        if cfg.get("show_completed"):
            params["showCompleted"] = True
            params["showHidden"] = True
        else:
            params["showCompleted"] = False
        argv = [_CLI, "tasks", "tasks", "list", "--params", json.dumps(params)]
        return argv, f"google-tasks list on {tasklist}"

    if op == "insert":
        title = cfg.get("title", "")
        if not isinstance(title, str) or not title.strip():
            raise FlowError("google-tasks insert needs a non-empty 'title'")
        body: Dict[str, Any] = {"title": title.strip()}
        if cfg.get("notes"):
            body["notes"] = str(cfg["notes"])
        if cfg.get("due"):
            body["due"] = str(cfg["due"])
        argv = [
            _CLI,
            "tasks",
            "tasks",
            "insert",
            "--params",
            json.dumps({"tasklist": tasklist}),
            "--json",
            json.dumps(body),
        ]
        return argv, f"google-tasks insert '{title.strip()}' -> {tasklist}"

    # op == "complete"
    task_id = cfg.get("task_id", "")
    if not isinstance(task_id, str) or not task_id.strip():
        raise FlowError("google-tasks complete needs a non-empty 'task_id'")
    argv = [
        _CLI,
        "tasks",
        "tasks",
        "patch",
        "--params",
        json.dumps({"tasklist": tasklist, "task": task_id.strip()}),
        "--json",
        json.dumps({"status": "completed"}),
    ]
    return argv, f"google-tasks complete {task_id.strip()} on {tasklist}"


def handle_google_tasks(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    gate = _auth_gate("tasks", "Google Tasks")
    if gate is not None:
        return gate
    argv, what = _tasks_argv(_cfg(node))
    code, out, err = _run_cli(argv)
    return _parse_result(code, out, err, "tasks", "Google Tasks", what)


def preview_google_tasks(node: Dict[str, Any]) -> str:
    if not _is_connected(cli_status("tasks")):
        return _GATED_PREVIEW
    try:
        _, what = _tasks_argv(_cfg(node))
    except FlowError as exc:
        return f"google-tasks: refused — {exc}"
    return what


# ---------------------------------------------------------------------------
# google-sheets action
# ---------------------------------------------------------------------------

_SHEETS_OPS = ("read_range", "append_row")


def _sheets_argv(cfg: Dict[str, Any]) -> Tuple[List[str], str]:
    """Build the exact argv for one sheets op. Deny-closed on bad config."""
    op = str(cfg.get("op", "read_range"))
    if op not in _SHEETS_OPS:
        raise FlowError(f"google-sheets: unknown op {op!r} (use {_SHEETS_OPS})")
    spreadsheet_id = cfg.get("spreadsheet_id", "")
    if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
        raise FlowError("google-sheets: 'spreadsheet_id' must be a non-empty string")
    spreadsheet_id = spreadsheet_id.strip()
    sheet_range = cfg.get("range", "")
    if not isinstance(sheet_range, str) or not sheet_range.strip():
        raise FlowError(
            "google-sheets: 'range' (A1 notation) must be a non-empty string"
        )
    sheet_range = sheet_range.strip()

    if op == "read_range":
        argv = [
            _CLI,
            "sheets",
            "spreadsheets",
            "values",
            "get",
            "--params",
            json.dumps({"spreadsheetId": spreadsheet_id, "range": sheet_range}),
        ]
        return argv, f"google-sheets read_range {sheet_range} on {spreadsheet_id}"

    # op == "append_row"
    values = cfg.get("values")
    if not isinstance(values, list) or not values:
        raise FlowError("google-sheets append_row needs a non-empty 'values' list")
    rows = values if all(isinstance(r, list) for r in values) else [values]
    argv = [
        _CLI,
        "sheets",
        "spreadsheets",
        "values",
        "append",
        "--params",
        json.dumps(
            {
                "spreadsheetId": spreadsheet_id,
                "range": sheet_range,
                "valueInputOption": "USER_ENTERED",
            }
        ),
        "--json",
        json.dumps({"values": rows}),
    ]
    return argv, f"google-sheets append_row {len(rows)} row(s) -> {sheet_range}"


def handle_google_sheets(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    gate = _auth_gate("sheets", "Google Sheets")
    if gate is not None:
        return gate
    argv, what = _sheets_argv(_cfg(node))
    code, out, err = _run_cli(argv)
    return _parse_result(code, out, err, "sheets", "Google Sheets", what)


def preview_google_sheets(node: Dict[str, Any]) -> str:
    if not _is_connected(cli_status("sheets")):
        return _GATED_PREVIEW
    try:
        _, what = _sheets_argv(_cfg(node))
    except FlowError as exc:
        return f"google-sheets: refused — {exc}"
    return what


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_REGISTRATIONS: List[
    Tuple[
        str,
        Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        Callable[[Dict[str, Any]], str],
    ]
] = [
    ("google-tasks", handle_google_tasks, preview_google_tasks),
    ("google-sheets", handle_google_sheets, preview_google_sheets),
]


def ensure_registered() -> List[str]:
    """Register this module's node kinds with the flow engine. Safe to call
    repeatedly; returns the kinds registered this call."""
    done: List[str] = []
    if register_node_kind is None:
        return done
    for kind, handler, preview_fn in _REGISTRATIONS:
        register_node_kind(kind, handler, preview_fn)
        done.append(kind)
    return done


ensure_registered()
