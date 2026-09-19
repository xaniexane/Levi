"""Tests for levi.automation.google_nodes.

Never hits real Google: the module's ``_run_cli`` is monkeypatched to
simulate the vendored CLI. The auth-gate path must return needs_auth
with no fake data; the connected path must build the exact argv the
skill contracts specify.
"""

import json

import pytest

from levi.automation import google_nodes
from levi.automation.google_nodes import FlowError

_CONNECTED = json.dumps({"status": "connected"})
_NOT_CONNECTED = json.dumps(
    {"status": "not_connected", "connect_url": "https://accounts.example/connect"}
)


def _fake_run_factory(script):
    """script: list of (match_substring, (code, stdout, stderr)) tuples."""
    calls = []

    def fake(argv, timeout_s=30.0):
        calls.append(argv)
        joined = " ".join(argv)
        for needle, result in script:
            if needle in joined:
                return result
        raise AssertionError(f"unexpected CLI call: {argv}")

    fake.calls = calls
    return fake


def _patch(monkeypatch, fake):
    monkeypatch.setattr(google_nodes, "_run_cli", fake)


# ---------------------------------------------------------------------------
# auth gate — never fake data
# ---------------------------------------------------------------------------


def test_tasks_auth_gate_not_connected(monkeypatch):
    fake = _fake_run_factory([("tasks status", (0, _NOT_CONNECTED, ""))])
    _patch(monkeypatch, fake)
    node = {"id": "t", "kind": "google-tasks", "config": {"op": "list"}}
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is False
    assert result["needs_auth"] == "Google Tasks"
    assert "hatch_gws_cli tasks status" in result["connect_hint"]
    assert "Chauncey's sign-in required" in result["connect_hint"]
    assert result["output"] == {}
    # Only the status check ran — no task command was attempted.
    assert fake.calls == [["hatch_gws_cli", "tasks", "status"]]


def test_tasks_auth_gate_unavailable_cli(monkeypatch):
    fake = _fake_run_factory([("tasks status", (127, "", "not installed"))])
    _patch(monkeypatch, fake)
    node = {"id": "t", "kind": "google-tasks", "config": {"op": "list"}}
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is False
    assert result["needs_auth"] == "Google Tasks"


def test_sheets_auth_gate_not_connected(monkeypatch):
    fake = _fake_run_factory([("sheets status", (0, _NOT_CONNECTED, ""))])
    _patch(monkeypatch, fake)
    node = {
        "id": "s",
        "kind": "google-sheets",
        "config": {"op": "read_range", "spreadsheet_id": "SID", "range": "A1"},
    }
    result = google_nodes.handle_google_sheets(node, {}, {})
    assert result["ok"] is False
    assert result["needs_auth"] == "Google Sheets"
    assert "hatch_gws_cli sheets status" in result["connect_hint"]
    assert result["output"] == {}
    assert fake.calls == [["hatch_gws_cli", "sheets", "status"]]


def test_preview_gated_when_unauthenticated(monkeypatch):
    fake = _fake_run_factory(
        [
            ("tasks status", (0, _NOT_CONNECTED, "")),
            ("sheets status", (0, _NOT_CONNECTED, "")),
        ]
    )
    _patch(monkeypatch, fake)
    assert (
        google_nodes.preview_google_tasks({"config": {"op": "list"}})
        == "gated: needs Chauncey's Google sign-in"
    )
    assert (
        google_nodes.preview_google_sheets({"config": {"op": "read_range"}})
        == "gated: needs Chauncey's Google sign-in"
    )


def test_mid_run_auth_failure_regates(monkeypatch):
    statuses = iter(
        [(0, _CONNECTED, ""), (0, _NOT_CONNECTED, "")]  # first gate, then re-check
    )
    calls = []

    def fake(argv, timeout_s=30.0):
        calls.append(argv)
        if "status" in argv:
            return next(statuses)
        return (1, "", "Error: 401 unauthorized")

    _patch(monkeypatch, fake)
    node = {"id": "t", "kind": "google-tasks", "config": {"op": "list"}}
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is False
    assert result["needs_auth"] == "Google Tasks"


# ---------------------------------------------------------------------------
# command construction — exact argv per the skill contracts
# ---------------------------------------------------------------------------


def _connected_fake(monkeypatch, command_result):
    """Status -> connected; any other call -> command_result, capturing argv."""
    captured = []

    def fake(argv, timeout_s=30.0):
        if argv[:3] == ["hatch_gws_cli", argv[1], "status"]:
            return (0, _CONNECTED, "")
        captured.append(argv)
        return command_result

    _patch(monkeypatch, fake)
    return captured


def test_tasks_insert_builds_exact_argv(monkeypatch):
    captured = _connected_fake(
        monkeypatch,
        (0, json.dumps({"id": "abc123", "title": "Buy milk"}), ""),
    )
    node = {
        "id": "t",
        "kind": "google-tasks",
        "config": {
            "op": "insert",
            "tasklist": "@default",
            "title": "Buy milk",
            "notes": "2%",
            "due": "2026-09-19T00:00:00Z",
        },
    }
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is True
    assert result["output"]["id"] == "abc123"
    assert result["evidence"].startswith("google-tasks insert")
    (argv,) = captured
    assert argv == [
        "hatch_gws_cli",
        "tasks",
        "tasks",
        "insert",
        "--params",
        json.dumps({"tasklist": "@default"}),
        "--json",
        json.dumps(
            {
                "title": "Buy milk",
                "notes": "2%",
                "due": "2026-09-19T00:00:00Z",
            }
        ),
    ]


def test_tasks_insert_minimal_body(monkeypatch):
    captured = _connected_fake(monkeypatch, (0, json.dumps({"id": "x"}), ""))
    node = {"id": "t", "config": {"op": "insert", "title": "T"}}
    google_nodes.handle_google_tasks(node, {}, {})
    body = json.loads(captured[0][captured[0].index("--json") + 1])
    assert body == {"title": "T"}


def test_tasks_list_builds_exact_argv(monkeypatch):
    captured = _connected_fake(monkeypatch, (0, json.dumps({"items": []}), ""))
    node = {"id": "t", "config": {"op": "list", "tasklist": "@default"}}
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is True
    assert captured[0] == [
        "hatch_gws_cli",
        "tasks",
        "tasks",
        "list",
        "--params",
        json.dumps({"tasklist": "@default", "showCompleted": False}),
    ]


def test_tasks_complete_builds_exact_argv(monkeypatch):
    captured = _connected_fake(
        monkeypatch, (0, json.dumps({"status": "completed"}), "")
    )
    node = {
        "id": "t",
        "config": {"op": "complete", "tasklist": "@default", "task_id": "abc123"},
    }
    result = google_nodes.handle_google_tasks(node, {}, {})
    assert result["ok"] is True
    assert captured[0] == [
        "hatch_gws_cli",
        "tasks",
        "tasks",
        "patch",
        "--params",
        json.dumps({"tasklist": "@default", "task": "abc123"}),
        "--json",
        json.dumps({"status": "completed"}),
    ]


def test_tasks_bad_config_refused(monkeypatch):
    _connected_fake(monkeypatch, (0, "{}", ""))
    with pytest.raises(FlowError):
        google_nodes.handle_google_tasks({"id": "t", "config": {"op": "nuke"}}, {}, {})
    with pytest.raises(FlowError):
        google_nodes.handle_google_tasks(
            {"id": "t", "config": {"op": "insert"}}, {}, {}
        )
    with pytest.raises(FlowError):
        google_nodes.handle_google_tasks(
            {"id": "t", "config": {"op": "complete"}}, {}, {}
        )


def test_sheets_read_range_builds_exact_argv(monkeypatch):
    captured = _connected_fake(
        monkeypatch, (0, json.dumps({"values": [["a", "b"]]}), "")
    )
    node = {
        "id": "s",
        "config": {
            "op": "read_range",
            "spreadsheet_id": "SID1",
            "range": "Sheet1!A1:D10",
        },
    }
    result = google_nodes.handle_google_sheets(node, {}, {})
    assert result["ok"] is True
    assert result["output"]["values"] == [["a", "b"]]
    assert captured[0] == [
        "hatch_gws_cli",
        "sheets",
        "spreadsheets",
        "values",
        "get",
        "--params",
        json.dumps({"spreadsheetId": "SID1", "range": "Sheet1!A1:D10"}),
    ]


def test_sheets_append_row_builds_exact_argv(monkeypatch):
    captured = _connected_fake(monkeypatch, (0, json.dumps({"updates": {}}), ""))
    node = {
        "id": "s",
        "config": {
            "op": "append_row",
            "spreadsheet_id": "SID1",
            "range": "Sheet1!A:D",
            "values": ["a", "b"],
        },
    }
    result = google_nodes.handle_google_sheets(node, {}, {})
    assert result["ok"] is True
    assert captured[0] == [
        "hatch_gws_cli",
        "sheets",
        "spreadsheets",
        "values",
        "append",
        "--params",
        json.dumps(
            {
                "spreadsheetId": "SID1",
                "range": "Sheet1!A:D",
                "valueInputOption": "USER_ENTERED",
            }
        ),
        "--json",
        json.dumps({"values": [["a", "b"]]}),
    ]


def test_sheets_bad_config_refused(monkeypatch):
    _connected_fake(monkeypatch, (0, "{}", ""))
    with pytest.raises(FlowError):
        google_nodes.handle_google_sheets(
            {"id": "s", "config": {"op": "read_range"}}, {}, {}
        )
    with pytest.raises(FlowError):
        google_nodes.handle_google_sheets(
            {
                "id": "s",
                "config": {
                    "op": "append_row",
                    "spreadsheet_id": "x",
                    "range": "A1",
                    "values": [],
                },
            },
            {},
            {},
        )


def test_preview_connected_describes_op(monkeypatch):
    _connected_fake(monkeypatch, (0, "{}", ""))
    assert google_nodes.preview_google_tasks(
        {"config": {"op": "insert", "title": "Buy milk"}}
    ) == ("google-tasks insert 'Buy milk' -> @default")
    assert google_nodes.preview_google_sheets(
        {
            "config": {
                "op": "read_range",
                "spreadsheet_id": "SID1",
                "range": "Sheet1!A1:D10",
            }
        }
    ) == ("google-sheets read_range Sheet1!A1:D10 on SID1")
    # Bad config previews as a refusal, never a guess.
    line = google_nodes.preview_google_tasks({"config": {"op": "insert"}})
    assert "refused" in line
