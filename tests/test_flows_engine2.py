"""Tests for the flows engine extension: node-kind registry, strict
validation, trigger/branch/approval nodes, the trigger dispatcher, the
dry-run planner, and the gated action rail.

Hermetic: dry-run only unless a test explicitly goes live with a stub
responder and stub handler; LEVI_HOME pinned to tmp; no network.
"""

import importlib

import pytest

from levi.automation import flows
from levi.automation.flows import (
    FlowError,
    build_flow,
    dispatch_trigger,
    ensure_builtin_nodes,
    plan_flow,
    register_node_kind,
    run_flow,
    save_flow,
    validate_flow,
)
from levi.automation.hitl import auto_approve, auto_deny

M1 = "productivity-email-digest-01"

CALLS = []


def _stub_handler(node, ctx, run):
    CALLS.append(
        {
            "node": node["id"],
            "run_keys": sorted(run.keys()),
            "dry_run": run["dry_run"],
            "ctx_keys": sorted(ctx.keys()),
        }
    )
    return {
        "ok": True,
        "output": {"did": node["id"]},
        "evidence": f"stub ran {node['id']}",
    }


def _stub_preview(node):
    cfg = node.get("config", {}) or {}
    return f"stub action: {cfg.get('what', node['id'])}"


# Registered once for the whole module: the node-pack contract, in-test.
# A dedicated kind (not "python") so the tests never depend on the real
# node-pack modules' in-flight implementations.
register_node_kind("test-action", _stub_handler, _stub_preview, action=True)


def _trigger(ttype, **cfg):
    return {
        "id": "entry",
        "kind": "trigger",
        "label": "Entry",
        "config": {"trigger_type": ttype, **cfg},
    }


def _flow_with(nodes, edges, start="entry", **over):
    base = {
        "id": "t2",
        "name": "T2",
        "start": start,
        "nodes": nodes,
        "edges": edges,
    }
    base.update(over)
    return base


# -- registry -----------------------------------------------------------------


def test_registry_rejects_bad_registration():
    with pytest.raises(FlowError):
        register_node_kind("nope-handler", None, _stub_preview)
    with pytest.raises(FlowError):
        register_node_kind("nope-preview", _stub_handler, None)
    with pytest.raises(FlowError):
        register_node_kind("bad kind!", _stub_handler, _stub_preview)
    # the in-test stub landed
    assert "test-action" in flows.NODE_KINDS
    assert flows._NODE_REGISTRY["test-action"]["action"] is True


def test_ensure_builtin_nodes_missing_pack():
    flows._builtin_nodes_loaded = False
    real_import = importlib.import_module

    def fake_import(name, *a, **k):
        raise ImportError(f"No module named {name!r}", name=name)

    importlib.import_module = fake_import
    try:
        with pytest.raises(FlowError, match="node pack missing: nodes"):
            ensure_builtin_nodes()
    finally:
        importlib.import_module = real_import
        flows._builtin_nodes_loaded = False


def test_ensure_builtin_nodes_inner_import_error_propagates():
    flows._builtin_nodes_loaded = False
    real_import = importlib.import_module

    def fake_import(name, *a, **k):
        raise ImportError("broken dep inside pack", name="some_dependency")

    importlib.import_module = fake_import
    try:
        with pytest.raises(ImportError, match="broken dep inside pack"):
            ensure_builtin_nodes()
    finally:
        importlib.import_module = real_import
        flows._builtin_nodes_loaded = False


def test_ensure_builtin_nodes_loads_real_packs_as_action_kinds():
    # Integration with the sibling-built node packs: the five pack kinds
    # register through the plain 3-arg contract and must still walk the
    # gated action rail.
    flows._builtin_nodes_loaded = False
    try:
        ensure_builtin_nodes()
    finally:
        flows._builtin_nodes_loaded = False
    for kind in ("webhook-out", "python", "macro", "google-tasks", "google-sheets"):
        assert kind in flows._NODE_REGISTRY, kind
        assert flows._NODE_REGISTRY[kind]["action"] is True, kind
        assert callable(flows._NODE_REGISTRY[kind]["preview_fn"])


# -- strict validation ----------------------------------------------------------


def test_validate_flow_ok_trigger_start():
    flow = _flow_with(
        [_trigger("manual"), {"id": "m", "kind": "note", "text": "hi"}],
        [{"id": "e1", "from": "entry", "to": "m"}],
    )
    out = validate_flow(flow)
    assert out["start"] == "entry"


def test_validate_flow_refusals():
    base_nodes = [
        {"id": "b", "kind": "predicate", "expr": "true"},
        {"id": "m", "kind": "note", "text": "hi"},
    ]
    base_edges = [{"id": "e1", "from": "b", "to": "m"}]

    # start must be trigger/minion under strict validation
    with pytest.raises(FlowError, match="trigger or minion"):
        validate_flow(_flow_with(base_nodes, base_edges, start="b"))
    # name required
    bad = _flow_with([_trigger("manual")], [], start="entry")
    del bad["name"]
    with pytest.raises(FlowError, match="name"):
        validate_flow(bad)
    # unknown kind
    bad = _flow_with(
        [_trigger("manual"), {"id": "x", "kind": "teleport"}],
        [{"id": "e1", "from": "entry", "to": "x"}],
    )
    with pytest.raises(FlowError, match="unknown kind"):
        validate_flow(bad)
    # duplicate ids
    bad = _flow_with(
        [_trigger("manual"), {"id": "entry", "kind": "note", "text": "dup"}],
        [],
    )
    with pytest.raises(FlowError, match="duplicate"):
        validate_flow(bad)
    # dangling edge
    bad = _flow_with(
        [_trigger("manual")], [{"id": "e1", "from": "entry", "to": "ghost"}]
    )
    with pytest.raises(FlowError, match="unknown target"):
        validate_flow(bad)
    # bad trigger configs
    bad = _flow_with(
        [{"id": "entry", "kind": "trigger", "config": {"trigger_type": "webhook-in"}}],
        [],
        start="entry",
    )
    with pytest.raises(FlowError, match="path"):
        validate_flow(bad)
    bad = _flow_with(
        [
            {
                "id": "entry",
                "kind": "trigger",
                "config": {"trigger_type": "schedule", "cron": "not a cron"},
            }
        ],
        [],
        start="entry",
    )
    with pytest.raises(FlowError, match="cron"):
        validate_flow(bad)
    # bad branch expr
    bad = _flow_with(
        [_trigger("manual"), {"id": "br", "kind": "branch", "expr": "@@"}],
        [{"id": "e1", "from": "entry", "to": "br"}],
    )
    with pytest.raises(FlowError, match="branch expr"):
        validate_flow(bad)
    # approval without prompt
    bad = _flow_with(
        [_trigger("manual"), {"id": "ap", "kind": "approval", "config": {}}],
        [{"id": "e1", "from": "entry", "to": "ap"}],
    )
    with pytest.raises(FlowError, match="prompt"):
        validate_flow(bad)


def test_build_flow_stays_permissive_on_start():
    # Legacy contract: any kind may start (existing graphs keep running).
    flow = {
        "id": "legacy",
        "name": "Legacy",
        "start": "n",
        "nodes": [{"id": "n", "kind": "note", "text": "hi"}],
        "edges": [],
    }
    assert build_flow(flow)["start"] == "n"


# -- branch routing -------------------------------------------------------------


def _branch_flow(expr):
    return _flow_with(
        [
            _trigger("manual"),
            {"id": "br", "kind": "branch", "expr": expr, "label": "Branch"},
            {"id": "yes", "kind": "note", "text": "yes-branch", "label": "Yes"},
            {"id": "no", "kind": "note", "text": "no-branch", "label": "No"},
        ],
        [
            {"id": "e0", "from": "entry", "to": "br"},
            {"id": "e1", "from": "br", "to": "yes", "when": "true"},
            {"id": "e2", "from": "br", "to": "no", "when": "false"},
        ],
    )


def test_branch_true_routes_true_edge():
    receipt = run_flow(_branch_flow("true"))
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["entry", "br", "yes"]


def test_branch_false_routes_false_edge():
    receipt = run_flow(_branch_flow("false"))
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["entry", "br", "no"]


def test_branch_when_expr_still_works():
    flow = _flow_with(
        [
            _trigger("manual"),
            {"id": "br", "kind": "branch", "expr": "2 > 1", "label": "Branch"},
            {"id": "m", "kind": "note", "text": "went", "label": "M"},
        ],
        [
            {"id": "e0", "from": "entry", "to": "br"},
            {"id": "e1", "from": "br", "to": "m", "when": "br.passed"},
        ],
    )
    receipt = run_flow(flow)
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["entry", "br", "m"]


def test_branch_non_bool_refused():
    flow = _flow_with(
        [
            _trigger("manual"),
            {"id": "br", "kind": "branch", "expr": "1 + 1", "label": "Branch"},
        ],
        [{"id": "e0", "from": "entry", "to": "br"}],
    )
    receipt = run_flow(flow)
    assert receipt.ok is False
    assert "boolean" in receipt.nodes[-1].detail


# -- approval gate ----------------------------------------------------------------


def _approval_flow():
    return _flow_with(
        [
            _trigger("manual"),
            {
                "id": "ap",
                "kind": "approval",
                "label": "Approve",
                "config": {"prompt": "ship it?", "gate_kind": "approval"},
            },
            {"id": "m", "kind": "note", "text": "shipped", "label": "M"},
        ],
        [
            {"id": "e0", "from": "entry", "to": "ap"},
            {"id": "e1", "from": "ap", "to": "m"},
        ],
    )


def test_approval_allow_continues():
    receipt = run_flow(_approval_flow(), responder=auto_approve)
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["entry", "ap", "m"]
    ap = receipt.nodes[1]
    assert ap.ok is True
    assert "approved" in ap.detail


def test_approval_deny_stops_with_denied_receipt():
    receipt = run_flow(_approval_flow(), responder=auto_deny)
    assert receipt.ok is False
    assert [n.node_id for n in receipt.nodes] == ["entry", "ap"]
    denied = receipt.nodes[-1]
    assert "denied" in denied.detail
    assert denied.receipt["gate_decision"]["decision"] == "denied"


def test_approval_live_never_auto_approves():
    receipt = run_flow(_approval_flow(), dry_run=False)  # default auto_approve
    assert receipt.ok is False
    assert "auto_approve" in receipt.nodes[-1].detail


# -- dry-run planner --------------------------------------------------------------


def test_plan_flow_renders_every_node_in_order():
    plan = plan_flow(_branch_flow("true"))
    assert [p["node_id"] for p in plan] == ["entry", "br", "yes", "no"]
    assert [p["order"] for p in plan] == [0, 1, 2, 3]
    assert all(p["preview"] for p in plan)
    by_id = {p["node_id"]: p for p in plan}
    assert "trigger" in by_id["entry"]["preview"]
    assert "true" in by_id["br"]["preview"] and "false" in by_id["br"]["preview"]


def test_every_run_logs_the_plan_first():
    receipt = run_flow(_branch_flow("true"))  # dry-run default
    assert len(receipt.plan) == 4
    assert receipt.to_dict()["plan"][0]["node_id"] == "entry"
    live = run_flow(
        _branch_flow("false"),
        dry_run=False,
        responder=lambda req: {"decision": "approved"},
    )
    assert len(live.plan) == 4


# -- action rail ------------------------------------------------------------------


def _action_flow():
    return _flow_with(
        [
            _trigger("manual"),
            {
                "id": "act",
                "kind": "test-action",
                "label": "Run code",
                "config": {"what": "hello.py"},
            },
            {"id": "m", "kind": "note", "text": "done", "label": "M"},
        ],
        [
            {"id": "e0", "from": "entry", "to": "act"},
            {"id": "e1", "from": "act", "to": "m"},
        ],
    )


def test_action_node_dry_run_receipt_entries():
    receipt = run_flow(_action_flow())
    assert receipt.ok is True
    act = receipt.nodes[1]
    assert act.kind == "test-action" and act.ok is True
    r = act.receipt
    assert r["node_id"] == "act"
    assert "stub action: hello.py" in r["preview"]
    assert r["gate_decision"]["decision"] == "approved"
    assert "dry-run: would" in r["evidence"]
    assert r["executed"] is False
    assert r["rail"] == [
        "plan",
        "preview",
        "permission",
        "execute",
        "verify",
        "receipt",
    ]
    assert (
        "rail: plan -> preview -> permission -> execute -> verify -> receipt"
        in act.detail
    )


def test_action_node_live_executes_with_real_responder():
    CALLS.clear()
    receipt = run_flow(
        _action_flow(),
        dry_run=False,
        responder=lambda req: {"decision": "approved", "note": "human ok"},
    )
    assert receipt.ok is True
    assert len(CALLS) == 1
    call = CALLS[0]
    assert call["node"] == "act"
    assert call["dry_run"] is False
    assert {"run_id", "flow_id", "flow_name", "dry_run", "responder"} <= set(
        call["run_keys"]
    )
    act = receipt.nodes[1]
    assert act.receipt["executed"] is True
    assert act.receipt["evidence"] == "stub ran act"


def test_action_node_live_refuses_auto_approve():
    CALLS.clear()
    receipt = run_flow(_action_flow(), dry_run=False)  # default auto_approve
    assert receipt.ok is False
    assert "auto_approve" in receipt.nodes[-1].detail
    assert CALLS == []  # handler never runs


def test_action_node_denied_gate_stops_flow():
    receipt = run_flow(_action_flow(), responder=auto_deny)
    assert receipt.ok is False
    assert [n.node_id for n in receipt.nodes] == ["entry", "act"]
    assert "denied" in receipt.nodes[-1].detail


# -- trigger dispatcher -------------------------------------------------------------


def _save_dispatch_flows(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))

    def _mk(fid, trigger_cfg, tail):
        return {
            "id": fid,
            "name": fid,
            "start": "entry",
            "nodes": [
                {"id": "entry", "kind": "trigger", "config": trigger_cfg},
                tail,
            ],
            "edges": [{"id": "e1", "from": "entry", "to": tail["id"]}],
        }

    save_flow(
        _mk(
            "wh-flow",
            {"trigger_type": "webhook-in", "path": "/hooks/x"},
            {"id": "act", "kind": "test-action", "config": {"what": "webhook"}},
        )
    )
    save_flow(
        _mk(
            "cron-flow",
            {"trigger_type": "schedule", "cron": "0 9 * * *"},
            {"id": "n", "kind": "note", "text": "morning"},
        )
    )
    save_flow(
        _mk(
            "manual-flow",
            {"trigger_type": "manual"},
            {"id": "n", "kind": "note", "text": "by hand"},
        )
    )
    save_flow(
        _mk(
            "event-flow",
            {"trigger_type": "event", "event_kind": "email"},
            {"id": "n", "kind": "note", "text": "mail"},
        )
    )
    save_flow(
        _mk(
            "quiet-flow",
            {"trigger_type": "webhook-in", "path": "/hooks/never"},
            {"id": "n", "kind": "note", "text": "silent"},
        )
    )


def test_dispatch_webhook_path_match(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    out = dispatch_trigger(
        {"kind": "webhook", "source": "test", "payload": {"path": "/hooks/x"}}
    )
    assert [s["flow_id"] for s in out] == ["wh-flow"]
    s = out[0]
    assert s["ok"] is True and s["run_id"].startswith("flow-")
    assert s["trigger_node"] == "entry" and s["dry_run"] is True


def test_dispatch_schedule_cron_match(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    out = dispatch_trigger(
        {
            "kind": "schedule",
            "source": "test",
            "payload": {},
            "ts": "2026-09-18T09:00:00+00:00",
        }
    )
    assert [s["flow_id"] for s in out] == ["cron-flow"]
    assert out[0]["ok"] is True


def test_dispatch_schedule_cron_no_match(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    out = dispatch_trigger(
        {
            "kind": "schedule",
            "source": "test",
            "payload": {},
            "ts": "2026-09-18T10:00:00+00:00",
        }
    )
    assert out == []


def test_dispatch_manual_and_event_kind(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    out = dispatch_trigger({"kind": "manual", "source": "test", "payload": {}})
    assert [s["flow_id"] for s in out] == ["manual-flow"]
    out = dispatch_trigger(
        {"kind": "email", "source": "test", "payload": {"event_kind": "email"}}
    )
    assert [s["flow_id"] for s in out] == ["event-flow"]


def test_dispatch_no_match_returns_empty(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    out = dispatch_trigger(
        {"kind": "webhook", "source": "t", "payload": {"path": "/nope2"}}
    )
    assert out == []


def test_dispatch_bad_flow_reports_error_not_crash(tmp_path, monkeypatch):
    _save_dispatch_flows(tmp_path, monkeypatch)
    save_flow(
        {
            "id": "boom-flow",
            "name": "boom",
            "start": "entry",
            "nodes": [
                {
                    "id": "entry",
                    "kind": "trigger",
                    "config": {"trigger_type": "manual"},
                },
                {"id": "n", "kind": "note", "text": "x"},
            ],
            "edges": [
                {"id": "e1", "from": "entry", "to": "n", "when": "1/0"},
            ],
        }
    )
    out = dispatch_trigger({"kind": "manual", "source": "t", "payload": {}})
    ids = [s["flow_id"] for s in out]
    assert "manual-flow" in ids and "boom-flow" in ids
    boom = next(s for s in out if s["flow_id"] == "boom-flow")
    assert boom["ok"] is False and "error" in boom
    manual = next(s for s in out if s["flow_id"] == "manual-flow")
    assert manual["ok"] is True


def test_dispatch_rejects_non_dict_event():
    with pytest.raises(FlowError):
        dispatch_trigger("not-a-dict")
