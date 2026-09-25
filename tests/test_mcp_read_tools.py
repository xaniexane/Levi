"""Tests for the read-only LEVI status/inventory tools exposed over MCP.

These tools live in levi.agent.tools (registered in _register_builtins)
and are served by the existing MCP server in levi.mcp.protocol — these
tests prove they list, execute, and refuse correctly, including over a
real stdio JSON-RPC round-trip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "core"

NEW_TOOLS = (
    "levi_status",
    "growth_status",
    "workshop_inventory",
    "workshop_dry_run",
    "academy_status",
    "factory_status",
)

GOOD_BLUEPRINT = {
    "name": "mcp-test",
    "agent": "productivity-email-digest-01",
    "specialist": "supervisor",
    "substrate": "rules",
    "organ": "echoverse",
    "legion_role": "analyst",
}


@pytest.fixture()
def registry():
    from levi.agent.tools import build_default_registry

    return build_default_registry()


def test_new_tools_registered(registry):
    names = {t.name for t in registry.list()}
    for tool_name in NEW_TOOLS:
        assert tool_name in names, f"{tool_name} not registered"
    # read-only: none of them require confirmation
    for tool_name in NEW_TOOLS:
        assert not registry.get(tool_name).requires_confirmation


def test_levi_status_honest_labels(registry):
    res = registry.execute("levi_status", {})
    assert res.ok, res.error
    data = json.loads(res.output)
    assert data["capability"] == "local-only"
    assert data["execution"] == "read-only"
    assert "version" in data


def test_growth_status_reads(registry):
    res = registry.execute("growth_status", {})
    assert res.ok, res.error
    data = json.loads(res.output)
    assert data["capability"] == "local-only"
    assert data["execution"] == "read-only"


def test_workshop_inventory_counts(registry):
    res = registry.execute("workshop_inventory", {})
    assert res.ok, res.error
    data = json.loads(res.output)
    counts = data["counts"]
    assert counts["agents"] == 471
    assert counts["specialists"] == 9
    assert counts["substrates"] == 7
    assert counts["organs"] == 4
    assert counts["legion_roles"] == 7
    assert data["execution"] == "read-only"


def test_workshop_dry_run_happy_path(registry):
    res = registry.execute("workshop_dry_run", dict(GOOD_BLUEPRINT))
    assert res.ok, res.error
    data = json.loads(res.output)
    assert data["capability"] == "local-only"
    assert "simulated" in data["execution"]
    assert "never spawn" in str(data.get("live_effects", ""))


def test_workshop_dry_run_refuses_unknown_agent(registry):
    args = dict(GOOD_BLUEPRINT, agent="not-a-real-agent")
    res = registry.execute("workshop_dry_run", args)
    assert not res.ok
    assert "refused" in res.error


def test_workshop_dry_run_refuses_own_cloud(registry):
    args = dict(GOOD_BLUEPRINT, substrate="own-cloud")
    res = registry.execute("workshop_dry_run", args)
    assert not res.ok
    assert "own-cloud" in res.error


def test_workshop_dry_run_missing_args(registry):
    res = registry.execute("workshop_dry_run", {})
    assert not res.ok
    assert "missing required args" in res.error


def test_academy_and_factory_status(registry):
    for tool_name in ("academy_status", "factory_status"):
        res = registry.execute(tool_name, {})
        assert res.ok, f"{tool_name}: {res.error}"
        data = json.loads(res.output)
        assert data["execution"] == "read-only"


def _run_stdio(messages: list[dict]) -> list[dict]:
    """Drive the real MCP server over stdio pipes: one JSON-RPC line in,
    one line out."""
    server_py = (
        "import json,sys;"
        "sys.path.insert(0, {core!r});"
        "from levi.mcp.protocol import build_owner_server;"
        "from levi.mcp.transports import serve_stdio;"
        "serve_stdio(build_owner_server())"
    ).format(core=str(CORE))
    proc = subprocess.run(
        [sys.executable, "-c", server_py],
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def _rpc(msg_id: int, method: str, params: dict | None = None) -> dict:
    msg: dict = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def test_mcp_stdio_round_trip_lists_and_calls_new_tools():
    responses = _run_stdio(
        [
            _rpc(
                1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}}
            ),
            _rpc(2, "tools/list"),
            _rpc(3, "tools/call", {"name": "levi_status", "arguments": {}}),
            _rpc(
                4,
                "tools/call",
                {"name": "workshop_inventory", "arguments": {}},
            ),
            _rpc(
                5,
                "tools/call",
                {"name": "workshop_dry_run", "arguments": dict(GOOD_BLUEPRINT)},
            ),
        ]
    )
    by_id = {r["id"]: r for r in responses}

    assert by_id[1]["result"]["protocolVersion"] == "2024-11-05"

    listed = {t["name"] for t in by_id[2]["result"]["tools"]}
    for tool_name in NEW_TOOLS:
        assert tool_name in listed, f"{tool_name} missing from tools/list"

    call3 = by_id[3]["result"]
    assert not call3.get("isError")
    text3 = call3["content"][0]["text"]
    assert json.loads(text3)["capability"] == "local-only"

    call4 = by_id[4]["result"]
    assert not call4.get("isError")
    assert json.loads(call4["content"][0]["text"])["counts"]["agents"] == 471

    call5 = by_id[5]["result"]
    assert not call5.get("isError")
    dry = json.loads(call5["content"][0]["text"])
    assert "simulated" in dry["execution"]


def test_mcp_stdio_unknown_tool_is_protocol_error():
    # This server's committed contract: unknown tool -> JSON-RPC -32602
    # (invalid params), per levi.mcp.protocol's module docstring.
    responses = _run_stdio(
        [_rpc(1, "tools/call", {"name": "no_such_tool_xyz", "arguments": {}})]
    )
    err = responses[0]["error"]
    assert err["code"] == -32602
    assert "unknown tool" in err["message"]


def test_mcp_stdio_malformed_input_never_crashes():
    server_py = (
        "import sys;"
        "sys.path.insert(0, {core!r});"
        "from levi.mcp.protocol import build_owner_server;"
        "from levi.mcp.transports import serve_stdio;"
        "serve_stdio(build_owner_server())"
    ).format(core=str(CORE))
    proc = subprocess.run(
        [sys.executable, "-c", server_py],
        input='{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}\n'
        "this is not json\n"
        '{"jsonrpc": "2.0", "id": 2, "method": "nope"}\n'
        '{"id": 3}\n',
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    by_id = {r.get("id"): r for r in lines}
    assert "tools" in by_id[1]["result"]  # good line still served
    assert any(r.get("error", {}).get("code") == -32700 for r in lines), (
        "parse error must yield -32700"
    )
    assert by_id[2]["error"]["code"] == -32601  # method not found
    assert by_id[3]["error"]["code"] in (-32600, -32601)  # invalid request
