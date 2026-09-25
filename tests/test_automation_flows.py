"""Tests for the node-graph workflow engine (core/levi/automation/flows.py).

Hermetic: dry-run only, LEVI_HOME pinned to tmp, no network.
"""

import pytest

from levi.automation.flows import (
    FlowError,
    build_flow,
    delete_flow,
    evaluate_expr,
    list_flows,
    load_flow,
    manifest,
    run_flow,
    save_flow,
    to_mermaid,
)

M1 = "productivity-email-digest-01"
M2 = "productivity-email-digest-02"


def _flow(**over):
    base = {
        "id": "test-flow",
        "name": "Test Flow",
        "start": "digest",
        "nodes": [
            {"id": "digest", "kind": "minion", "minion_id": M1, "label": "Digest"},
            {"id": "check", "kind": "predicate", "expr": "digest.ok", "label": "ok?"},
            {"id": "ship", "kind": "minion", "minion_id": M2, "label": "Ship"},
            {"id": "memo", "kind": "note", "text": "done", "label": "Memo"},
        ],
        "edges": [
            {"id": "e1", "from": "digest", "to": "check"},
            {"id": "e2", "from": "check", "to": "ship", "when": "check.passed"},
            {"id": "e3", "from": "ship", "to": "memo"},
        ],
    }
    base.update(over)
    return base


# -- expression language ----------------------------------------------------


def test_expr_basics():
    ns = {"a": {"ok": True, "n": 3}, "flag": False}
    assert evaluate_expr("a.ok", ns) is True
    assert evaluate_expr("a.n > 2 and not flag", ns) is True
    assert evaluate_expr("a.n == 3 or flag", ns) is True
    assert evaluate_expr("not (a.n < 2)", ns) is True
    # arithmetic (for emit nodes)
    assert evaluate_expr("2 + 3 * 4", ns) == 14
    assert evaluate_expr("2-3", ns) == -1
    assert evaluate_expr("6 / 2", ns) == 3
    assert evaluate_expr("a.n * 2", ns) == 6
    with pytest.raises(FlowError):
        evaluate_expr("1/0", ns)


def test_expr_deny_closed():
    with pytest.raises(FlowError):
        evaluate_expr("missing.ok", {})
    with pytest.raises(FlowError):
        evaluate_expr("1 and 2", {})  # and needs booleans
    # mixed-type equality is well-defined (not equal), never an error
    assert evaluate_expr("true == 1", {}) is False
    assert evaluate_expr("true != 1", {}) is True
    assert evaluate_expr("true == true", {}) is True
    with pytest.raises(FlowError):
        evaluate_expr("true > 1", {})  # ordering on bools: refused
    with pytest.raises(FlowError):
        evaluate_expr("drop table", {})


# -- validation -------------------------------------------------------------


def test_build_flow_ok():
    f = build_flow(_flow())
    assert f["id"] == "test-flow"
    assert f["start"] == "digest"
    assert len(f["nodes"]) == 4 and len(f["edges"]) == 3


def test_build_flow_refusals():
    bad = _flow()
    bad["nodes"][0]["minion_id"] = "no-such-minion"
    with pytest.raises(FlowError):
        build_flow(bad)
    bad = _flow()
    bad["edges"].append({"id": "ex", "from": "digest", "to": "ghost"})
    with pytest.raises(FlowError):
        build_flow(bad)
    bad = _flow()
    bad["start"] = "ghost"
    with pytest.raises(FlowError):
        build_flow(bad)
    bad = _flow()
    bad["nodes"].append({"id": "digest", "kind": "note", "label": "dup"})
    with pytest.raises(FlowError):
        build_flow(bad)


# -- execution --------------------------------------------------------------


def test_run_flow_dry_run_receipts_every_node():
    receipt = run_flow(_flow())
    assert receipt.flow_id == "test-flow"
    assert receipt.dry_run is True
    assert receipt.ok is True
    kinds = [n.kind for n in receipt.nodes]
    assert kinds == ["minion", "predicate", "minion", "note"]
    minion_nodes = [n for n in receipt.nodes if n.kind == "minion"]
    assert all(n.receipt is not None for n in minion_nodes)
    # every minion node walked the full rail and was receipted
    for n in minion_nodes:
        assert n.receipt["rail"] == [
            "plan",
            "preview",
            "permission",
            "execute",
            "verify",
            "receipt",
        ]
        assert n.receipt["dry_run"] is True
        assert n.receipt["executed"] is False


def test_run_flow_conditional_branching():
    # predicate false -> ship skipped
    flow = _flow()
    flow["nodes"][1]["expr"] = "digest.ok == false"
    receipt = run_flow(flow)
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["digest", "check"]


def test_run_flow_emit_and_context():
    flow = {
        "id": "emit-flow",
        "name": "Emit",
        "start": "boot",
        "nodes": [
            {
                "id": "boot",
                "kind": "emit",
                "set": {"plan.count": "2 + 3", "plan.ready": "true"},
                "label": "Boot",
            },
            {
                "id": "gate",
                "kind": "predicate",
                "expr": "plan.ready and plan.count == 5",
                "label": "Ready?",
            },
            {"id": "memo", "kind": "note", "text": "go", "label": "Memo"},
        ],
        "edges": [
            {"id": "e1", "from": "boot", "to": "gate"},
            {"id": "e2", "from": "gate", "to": "memo", "when": "gate.passed"},
        ],
    }
    receipt = run_flow(flow)
    assert receipt.ok is True
    assert [n.node_id for n in receipt.nodes] == ["boot", "gate", "memo"]


def test_run_flow_loop_refused():
    flow = {
        "id": "loop",
        "name": "Loop",
        "start": "a",
        "nodes": [
            {"id": "a", "kind": "predicate", "expr": "true", "label": "A"},
            {"id": "b", "kind": "predicate", "expr": "true", "label": "B"},
        ],
        "edges": [
            {"id": "e1", "from": "a", "to": "b"},
            {"id": "e2", "from": "b", "to": "a"},
        ],
    }
    with pytest.raises(FlowError):
        run_flow(flow)


def test_run_flow_revalidates():
    with pytest.raises(FlowError):
        run_flow({"id": "bad", "nodes": [], "edges": [], "start": "x"})


def test_flow_receipt_renders():
    receipt = run_flow(_flow())
    text = receipt.render()
    assert "dry-run" in text and "OK" in text
    d = receipt.to_dict()
    assert d["run_id"].startswith("flow-")
    assert len(d["nodes"]) == 4


# -- visualization as data --------------------------------------------------


def test_manifest_positions():
    m = manifest(_flow())
    assert m["flow_id"] == "test-flow"
    pos = {n["id"]: (n["x"], n["y"]) for n in m["nodes"]}
    assert pos["digest"][0] == 0
    assert pos["check"][0] == 1
    assert pos["ship"][0] == 2
    assert all("kind" in n and "label" in n for n in m["nodes"])
    assert any("when" in e for e in m["edges"])


def test_to_mermaid():
    mm = to_mermaid(_flow())
    assert mm.startswith("flowchart TD")
    assert "digest" in mm and "ship" in mm
    assert "check.passed" in mm


# -- persistence ------------------------------------------------------------


def test_save_load_list_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    path = save_flow(_flow())
    assert path.name == "test-flow.json"
    loaded = load_flow("test-flow")
    assert loaded["id"] == "test-flow"
    flows = list_flows()
    assert [f["id"] for f in flows] == ["test-flow"]
    assert flows[0]["nodes"] == 4
    assert delete_flow("test-flow") is True
    assert delete_flow("test-flow") is False
    assert list_flows() == []
    with pytest.raises(FlowError):
        load_flow("test-flow")
