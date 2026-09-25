"""Phase 3 dataflow (B11) acceptance battery: T1-T7.

Offline: sockets are blocked for the whole file by the fixture below
(own tiny fixture; never imports the beginning team's offline module).
"""

import pytest

import socket

from levi.phase3.dataflow import (
    DataflowFault,
    PlanList,
    TestDoubleDispatch,
    build_graph,
    execute,
    replay,
    validate,
)


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("network disabled: offline test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _arith_dispatch():
    def _prod(values):
        result = 1
        for v in values:
            result *= v
        return result

    d = TestDoubleDispatch(namespace="dataflow-test")
    d.register("const", lambda ins, outs: {outs[0]: next(iter(ins.values()))})
    d.register("add", lambda ins, outs: {outs[0]: sum(ins.values())})
    d.register("mul", lambda ins, outs: {outs[0]: _prod(ins.values())})
    d.register("neg", lambda ins, outs: {outs[0]: -next(iter(ins.values()))})
    d.register(
        "dup",
        lambda ins, outs: {o: next(iter(ins.values())) for o in outs},
    )
    return d


def _chain_plan(length):
    """Linear chain c0 -> c1 -> ... with out-of-order node ids."""
    plan = PlanList()
    plan.add("n-%02d" % (length - 1), "neg", ["v%d" % (length - 2)], ["out"], budget=1)
    for i in range(length - 2, -1, -1):
        prev = "seed" if i == 0 else "v%d" % (i - 1)
        plan.add("n-%02d" % i, "add", [prev, "seed"], ["v%d" % i], budget=1)
    return plan


def test_t1_determinism_100_graphs_x20_runs():
    dispatch = _arith_dispatch()
    for g in range(100):
        plan = _chain_plan(3 + (g % 4))
        graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
        baseline = None
        for _ in range(20):
            trace = execute(graph, {"seed": g}, dispatch)
            state = (tuple(trace.fire_order), trace.outputs)
            if baseline is None:
                baseline = state
            assert state == baseline


def _malformed_plans():
    d = _arith_dispatch()
    known = d.known_ops
    plans = []
    # cycles
    for _ in range(20):
        p = PlanList()
        p.add("a", "add", ["x", "s"], ["y"])
        p.add("b", "add", ["y", "s"], ["x"])
        plans.append((p, ["s"]))
    # missing producers
    for _ in range(20):
        p = PlanList()
        p.add("a", "add", ["ghost", "s"], ["y"])
        plans.append((p, ["s"]))
    # unknown ops
    for _ in range(20):
        p = PlanList()
        p.add("a", "frobnicator", ["s"], ["y"])
        plans.append((p, ["s"]))
    return plans, known


def test_t2_build_time_rejection_60():
    plans, known = _malformed_plans()
    assert len(plans) == 60
    for plan, external in plans:
        with pytest.raises(DataflowFault) as excinfo:
            plan.build(known, external_inputs=external)
        assert excinfo.value.receipt["op"] == "build"


def test_t2_duplicate_producer_rejected():
    d = _arith_dispatch()
    p = PlanList()
    p.add("a", "const", ["k"], ["v"])
    p.add("b", "const", ["k"], ["v"])
    with pytest.raises(DataflowFault):
        p.build(d.known_ops, external_inputs=["k"])


def test_t3_no_mid_execution_deadlock_200():
    dispatch = _arith_dispatch()
    for g in range(200):
        plan = PlanList()
        # diamond: seed -> dup -> (add, mul) -> add
        plan.add("n-dup", "dup", ["seed"], ["x", "y"])
        plan.add("n-add", "add", ["x", "seed"], ["s"])
        plan.add("n-mul", "mul", ["y", "seed"], ["p"])
        plan.add("n-sum", "add", ["s", "p"], ["total"])
        graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
        trace = execute(graph, {"seed": g % 7}, dispatch)
        assert len(trace.fire_order) == 4
        assert trace.outputs["total"] == (g % 7) * 2 + (g % 7) ** 2


def test_t4_replay_50_executions():
    dispatch = _arith_dispatch()
    for g in range(50):
        plan = _chain_plan(4)
        graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
        trace = execute(graph, {"seed": g}, dispatch)
        again = replay(graph, trace, {"seed": g}, dispatch)
        assert again.fire_order == trace.fire_order
        assert again.outputs == trace.outputs


def test_t5_tie_break_40_graphs():
    dispatch = _arith_dispatch()
    for g in range(40):
        plan = PlanList()
        # three independent nodes, all ready at once; ids out of order
        plan.add("z-last", "neg", ["seed"], ["n1"])
        plan.add("a-first", "neg", ["seed"], ["n2"])
        plan.add("m-mid", "neg", ["seed"], ["n3"])
        graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
        trace = execute(graph, {"seed": g}, dispatch)
        assert trace.fire_order == ["a-first", "m-mid", "z-last"]


def test_t6_audit_uniformity_200_firings():
    dispatch = TestDoubleDispatch(namespace="audit-check")
    dispatch.register("step", lambda ins, outs: {outs[0]: ins["seed"]})
    plan = PlanList()
    plan.add("n1", "step", ["seed"], ["o"])
    graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
    for _ in range(200):
        execute(graph, {"seed": 1}, dispatch)
    assert len(dispatch.audit) == 200
    for entry in dispatch.audit:
        assert set(entry) >= {"namespace", "verb", "target", "args"}
        assert entry["namespace"] == "audit-check"
        assert entry["verb"] == "run"
        assert entry["target"] == "/tools/step"


def test_validate_ok():
    dispatch = _arith_dispatch()
    plan = _chain_plan(3)
    graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
    receipt = validate(graph)
    assert receipt["ok"] is True


def test_execute_missing_external_input_faults():
    dispatch = _arith_dispatch()
    plan = _chain_plan(3)
    graph = plan.build(dispatch.known_ops, external_inputs=["seed"])
    with pytest.raises(DataflowFault):
        execute(graph, {}, dispatch)


def test_build_graph_accepts_raw_rows():
    dispatch = _arith_dispatch()
    graph = build_graph(
        [("a", "neg", ["seed"], ["n"]), ("b", "neg", ["n"], ["o"])],
        dispatch.known_ops,
        external_inputs=["seed"],
    )
    trace = execute(graph, {"seed": 5}, dispatch)
    assert trace.fire_order == ["a", "b"]
    assert trace.outputs["o"] == 5  # neg(neg(5))


def test_t7_offline_socket_blocked():
    with pytest.raises(RuntimeError):
        socket.socket()
