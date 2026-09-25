"""Phase 3 plan9 (B10) acceptance battery: T1-T7.

Offline: sockets are blocked for the whole file by the fixture below
(own tiny fixture; never imports the beginning team's offline module).
"""

import pytest

import socket

from levi.phase3.plan9 import (
    VERBS,
    DirectDispatch,
    Plan9Fault,
    audit_log,
    clear_audit_log,
    compose_namespace,
    operate,
)


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("network disabled: offline test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def _clean_audit():
    clear_audit_log()
    yield
    clear_audit_log()


def _full_dispatch():
    """Every registered tool expressible in all five verbs (T1)."""
    dispatch = DirectDispatch()
    tools = ["calc", "echo", "kv"]

    def read(target, args):
        return {"verb": "read", "target": target, "args": args}

    def write(target, args):
        return {"verb": "write", "target": target, "args": args}

    def list_(target, args):
        return ["a", "b"]

    def run(target, args):
        return "ran"

    def watch(target, args):
        return "watching"

    for verb, fn in [
        ("read", read),
        ("write", write),
        ("list", list_),
        ("run", run),
        ("watch", watch),
    ]:
        dispatch.register(verb, fn)
    return dispatch, tools


def _grants(tools, verbs=VERBS):
    return [
        {"mount": "/tools/%s" % t, "prefix": "/tools/%s" % t, "verbs": list(verbs)}
        for t in tools
    ] + [
        {"mount": "/memory", "prefix": "/memory", "verbs": ["read", "write"]},
        {"mount": "/cards", "prefix": "/cards", "verbs": ["read", "list"]},
        {"mount": "/state", "prefix": "/state", "verbs": ["read", "watch"]},
    ]


def test_t1_verb_coverage_all_tools():
    dispatch, tools = _full_dispatch()
    ns, _ = compose_namespace("t1", _grants(tools))
    covered = 0
    for tool in tools:
        for verb in VERBS:
            result = operate(ns, verb, "/tools/%s/op" % tool, {"x": 1}, dispatch)
            assert result.receipt["ok"] is True
            covered += 1
    assert covered == len(tools) * len(VERBS) == 15
    # memory / cards / state surfaces too
    operate(ns, "write", "/memory/scope", "v", dispatch)
    operate(ns, "list", "/cards/stack", None, dispatch)
    operate(ns, "watch", "/state/mod", None, dispatch)


def test_t2_isolation_100_probes():
    dispatch, tools = _full_dispatch()
    ns, _ = compose_namespace("t2", _grants(tools))
    faults = 0
    # 50 unnamed targets (outside every mount)
    for i in range(50):
        with pytest.raises(Plan9Fault) as excinfo:
            operate(ns, "read", "/secret/thing-%d" % i, None, dispatch)
        assert excinfo.value.receipt["reason"] == "unnamed target"
        faults += 1
    # 50 denied verbs (write on a read-only mount, etc.)
    denied = [
        ("write", "/cards/stack"),
        ("run", "/memory/scope"),
        ("write", "/state/mod"),
        ("run", "/cards/stack"),
    ]
    for i in range(50):
        verb, target = denied[i % len(denied)]
        with pytest.raises(Plan9Fault) as excinfo:
            operate(ns, verb, target, None, dispatch)
        assert excinfo.value.receipt["reason"] == "denied verb"
        faults += 1
    assert faults == 100
    # zero successes: nothing got through
    assert all(not e["ok"] for e in audit_log())


def test_t3_uniform_audit_500_ops():
    dispatch, tools = _full_dispatch()
    ns, _ = compose_namespace("t3", _grants(tools))
    for i in range(500):
        tool = tools[i % len(tools)]
        verb = VERBS[i % len(VERBS)]
        operate(ns, verb, "/tools/%s/op-%d" % (tool, i), {"i": i}, dispatch)
    entries = audit_log()
    assert len(entries) == 500
    for entry in entries:
        assert set(entry) >= {"namespace", "verb", "target", "args"}
        assert entry["namespace"] == "t3"
        assert entry["verb"] in VERBS
        assert entry["ok"] is True


def test_t4_lifecycle_50_tasks():
    dispatch, tools = _full_dispatch()
    for i in range(50):
        ns, _ = compose_namespace("task-%d" % i, _grants(tools))
        operate(ns, "read", "/tools/calc/x", None, dispatch)
        ns.close()
        with pytest.raises(Plan9Fault) as excinfo:
            operate(ns, "read", "/tools/calc/x", None, dispatch)
        assert excinfo.value.receipt["reason"] == "namespace destroyed"


def test_t5_rung0_revocation_30():
    dispatch, tools = _full_dispatch()
    for i in range(30):
        ns, _ = compose_namespace("rev-%d" % i, _grants(tools))
        operate(ns, "run", "/tools/calc/op", None, dispatch)  # in-flight, succeeds
        ns.revoke("/tools/calc")
        with pytest.raises(Plan9Fault) as excinfo:
            operate(ns, "run", "/tools/calc/op", None, dispatch)
        # unnamed now: the revoked mount no longer matches
        assert excinfo.value.receipt["reason"] == "unnamed target"
        # sibling mounts still work
        operate(ns, "run", "/tools/echo/op", None, dispatch)


def test_t6_composition_receipt_50():
    for i in range(50):
        grants = [
            {"mount": "/tools", "prefix": "/tools", "verbs": ["run"]},
            {"mount": "/mem", "prefix": "/memory/x", "verbs": ["read"], "budget": 3},
        ]
        _, receipt = compose_namespace("comp-%d" % i, grants)
        assert receipt["op"] == "compose"
        assert receipt["namespace"] == "comp-%d" % i
        assert len(receipt["grants"]) == 2
        assert receipt["grants"][0]["mount"] == "/mem"
        assert receipt["grants"][0]["budget"] == 3


def test_longest_prefix_match():
    dispatch = DirectDispatch()
    dispatch.register("read", lambda target, args: target)
    ns, _ = compose_namespace(
        "lp",
        [
            {"mount": "/tools", "prefix": "/tools", "verbs": ["read"]},
            {"mount": "/tools/special", "prefix": "/tools/special", "verbs": ["read"]},
        ],
    )
    result = operate(ns, "read", "/tools/special/deep", None, dispatch)
    assert result.value == "/tools/special/deep"
    assert result.receipt["real_target"] == "/tools/special/deep"


def test_budget_exhaustion_faults():
    dispatch = DirectDispatch()
    dispatch.register("read", lambda target, args: "v")
    ns, _ = compose_namespace(
        "b", [{"mount": "/m", "prefix": "/m", "verbs": ["read"], "budget": 2}]
    )
    operate(ns, "read", "/m/a", None, dispatch)
    operate(ns, "read", "/m/b", None, dispatch)
    with pytest.raises(Plan9Fault) as excinfo:
        operate(ns, "read", "/m/c", None, dispatch)
    assert excinfo.value.receipt["reason"] == "budget exhausted"


def test_unknown_verb_in_grant_rejected():
    with pytest.raises(Plan9Fault):
        compose_namespace("x", [{"mount": "/m", "verbs": ["frob"]}])


def test_dispatch_error_receipted():
    dispatch = DirectDispatch()  # no handlers registered
    ns, _ = compose_namespace("d", [{"mount": "/m", "prefix": "/m", "verbs": ["run"]}])
    with pytest.raises(Plan9Fault) as excinfo:
        operate(ns, "run", "/m/x", None, dispatch)
    assert "dispatch failed" in excinfo.value.receipt["reason"]


def test_t7_offline_socket_blocked():
    with pytest.raises(RuntimeError):
        socket.socket()
