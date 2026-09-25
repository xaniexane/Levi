"""Phase 3 linda (B9) acceptance battery: T1-T7.

Offline: sockets are blocked for the whole file by the fixture below
(own tiny fixture; never imports the beginning team's offline module).
"""

import json

import pytest

import socket

from levi.phase3.linda import (
    LindaFault,
    LocalSpace,
    PendingTicket,
    TupleSpace,
    match_template,
)


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("network disabled: offline test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _strip_ts(receipts):
    return [{k: v for k, v in r.items() if k != "ts"} for r in receipts]


# ---------------------------------------------------------------------------
# T1 matching: 300 template/tuple cases
# ---------------------------------------------------------------------------


def _t1_cases():
    cases = []  # (template, tag, fields, expect_match)
    tags = ["task", "result", "ping"]
    # 1. literal matches / mismatches
    for i, tag in enumerate(tags):
        cases.append(((tag, i, "x"), tag, [i, "x"], True))
        cases.append(((tag, i, "x"), tag, [i, "y"], False))
        cases.append(((tag, i), "other", [i], False))
        cases.append(((tag, i, "x"), tag, [i], False))  # arity
        cases.append(((tag,), tag, [], True))
    # 2. wildcards bind anything
    values = [0, 1, "s", None, True, 3.5, [1, 2], {"a": 1}]
    for v in values:
        cases.append((("task", "?v"), "task", [v], True))
        cases.append((("task", "?a", "?b"), "task", [v, v], True))
    # 3. multi-bind consistency
    for v in values:
        cases.append((("t", "?x", "?x"), "t", [v, v], True))
    pairs = [(0, 1), ("a", "b"), (None, 0), (True, 1), ([1], [1, 2])]
    for a, b in pairs:
        cases.append((("t", "?x", "?x"), "t", [a, b], a == b and type(a) is type(b)))
    # 4. mixed literal + wildcard
    for i in range(20):
        cases.append((("job", i, "?rest"), "job", [i, "r%d" % i], True))
        cases.append((("job", i, "?rest"), "job", [i + 1, "r%d" % i], False))
    # 5. type strictness: 1 != "1", True != 1
    cases.append((("t", 1), "t", ["1"], False))
    cases.append((("t", True), "t", [1], False))
    cases.append((("t", 1), "t", [True], False))
    cases.append((("t", None), "t", [None], True))
    cases.append((("t", 1.0), "t", [1], False))
    # 6. three-var templates
    for i in range(30):
        cases.append((("m", "?a", i, "?c"), "m", ["A%d" % i, i, "C%d" % i], True))
        cases.append((("m", "?a", i, "?c"), "m", ["A%d" % i, i + 1, "C%d" % i], False))
    # 7. wildcard var names are independent across positions
    for i in range(30):
        cases.append((("w", "?x", "?y"), "w", [i, i + 100], True))
    # 8. same var three times
    for i in range(20):
        cases.append((("z", "?q", "?q", "?q"), "z", [i, i, i], True))
        cases.append((("z", "?q", "?q", "?q"), "z", [i, i, i + 1], False))
    # pad to >= 300 with deterministic generated cases
    n = 0
    while len(cases) < 300:
        n += 1
        cases.append((("pad", n, "?v"), "pad", [n, n * 2], True))
        cases.append((("pad", n, "?v"), "pad", [n + 1, n * 2], False))
    return cases[:300]


def test_t1_matching_300_cases():
    cases = _t1_cases()
    assert len(cases) == 300
    for template, tag, fields, expected in cases:
        got = match_template(tuple(template), tag, fields)
        assert (got is not None) == expected, (template, tag, fields)


# ---------------------------------------------------------------------------
# T2 determinism: same op sequence -> identical state + receipts x30
# ---------------------------------------------------------------------------


def _t2_sequence(space):
    space.declare_tag("work", 2)
    space.declare_tag("done", 1)
    for i in range(10):
        space.out("work", "job-%d" % i, i)
    for _ in range(4):
        space.in_(("work", "?j", "?n"))
    space.rd(("work", "?j", "?n"))
    space.out("done", "ok")
    space.expire(("work", "?j", "?n"))
    space.boundary()


def test_t2_determinism_30_runs():
    baseline = None
    for _ in range(30):
        space = TupleSpace()
        _t2_sequence(space)
        snap = json.dumps(space.snapshot(), sort_keys=True)
        receipts = json.dumps(_strip_ts(space.receipts()), sort_keys=True)
        state = (snap, receipts)
        if baseline is None:
            baseline = state
        assert state == baseline


# ---------------------------------------------------------------------------
# T3 oldest-wins: 50 contention scenarios
# ---------------------------------------------------------------------------


def test_t3_oldest_wins_50_scenarios():
    for scenario in range(50):
        space = TupleSpace()
        space.declare_tag("c", 2)
        n = 3 + (scenario % 5)
        for i in range(n):
            space.out("c", "k%d" % (scenario % 3), i)
        taken = space.in_(("c", "?k", "?n"))
        assert taken["fields"] == ["k%d" % (scenario % 3), 0]
        # rd also sees the oldest remaining
        seen = space.rd(("c", "?k", "?n"))
        assert seen["fields"] == ["k%d" % (scenario % 3), 1]


# ---------------------------------------------------------------------------
# T4 bounded wait: 100 in/rd on empty -> 100 receipted faults, zero hangs
# ---------------------------------------------------------------------------


def test_t4_bounded_wait_100_faults():
    space = TupleSpace()
    space.declare_tag("empty", 1)
    tickets = []
    for i in range(50):
        tickets.append(space.in_(("empty", "?x")))
        tickets.append(space.rd(("empty", i)))
    assert all(isinstance(t, PendingTicket) for t in tickets)
    report = space.boundary()
    assert len(report["faulted"]) == 100
    faults = 0
    for ticket in tickets:
        with pytest.raises(LindaFault) as excinfo:
            ticket.result()
        assert excinfo.value.receipt["op"] == "wait_fault"
        assert excinfo.value.receipt["ok"] is False
        faults += 1
    assert faults == 100
    assert space.cycle == 1  # waits never span cycles


def test_t4_waiter_woken_by_late_out():
    space = TupleSpace()
    space.declare_tag("w", 1)
    ticket = space.in_(("w", "?x"))
    assert isinstance(ticket, PendingTicket)
    space.out("w", "late")
    got = ticket.result()
    assert got["fields"] == ["late"]
    space.boundary()  # no waiters left -> no faults
    assert space.cycle == 1


# ---------------------------------------------------------------------------
# T5 no silent drops: 200 outs -> every one consumed or expired
# ---------------------------------------------------------------------------


def test_t5_no_silent_drops_200():
    space = TupleSpace()
    space.declare_tag("item", 1)
    seqs = [space.out("item", i)["seq"] for i in range(200)]
    assert all(space.lifecycle(s) == "posted" for s in seqs)
    for _ in range(120):
        space.in_(("item", "?v"))
    for _ in range(30):  # reads observe without consuming
        space.rd(("item", "?v"))
    space.expire(("item", "?v"))
    states = [space.lifecycle(s) for s in seqs]
    assert states.count("consumed") == 120
    assert states.count("expired") == 80
    assert all(s in ("consumed", "expired") for s in states)
    # every out is accounted for in the receipt log
    out_seqs = {r["seq"] for r in space.receipts() if r["op"] == "out"}
    assert out_seqs == set(seqs)


# ---------------------------------------------------------------------------
# T6 replay: 20 delegation chains reproduce exactly
# ---------------------------------------------------------------------------


def _t6_chain(space, chain_id):
    space.declare_tag("task", 2)
    space.declare_tag("result", 2)
    space.out("task", "scan", chain_id)
    work = space.in_(("task", "?job", "?c"))
    assert not isinstance(work, PendingTicket)
    space.out("result", work["fields"][1], "done")
    res = space.in_(("result", "?c", "?s"))
    assert res["fields"] == [chain_id, "done"]
    space.boundary()


def test_t6_replay_20_chains():
    for chain in range(20):
        space = TupleSpace()
        _t6_chain(space, chain)
        ops = space.op_log()
        replayed = TupleSpace.replay(ops)
        assert replayed.snapshot() == space.snapshot()
        assert _strip_ts(replayed.receipts()) == _strip_ts(space.receipts())


# ---------------------------------------------------------------------------
# Misc spec behaviors
# ---------------------------------------------------------------------------


def test_undeclared_tag_faults_strict():
    space = TupleSpace()
    with pytest.raises(LindaFault) as excinfo:
        space.out("nope", 1)
    assert excinfo.value.receipt["reason"] == "undeclared tag"


def test_undeclared_tag_warns_non_strict():
    space = TupleSpace(strict_tags=False)
    receipt = space.out("nope", 1)
    assert receipt["ok"] is True
    assert any(r["op"] == "tag_fault" for r in space.receipts())


def test_arity_mismatch_faults():
    space = TupleSpace()
    space.declare_tag("a", 2)
    with pytest.raises(LindaFault):
        space.out("a", 1)


def test_non_json_fields_fault():
    space = TupleSpace()
    space.declare_tag("a", 1)
    with pytest.raises(LindaFault):
        space.out("a", object())


def test_eval_outs_result_at_boundary():
    space = TupleSpace()
    space.declare_tag("r", 1)
    space.eval(lambda: ["v"], "r", task_id="t1")
    assert space._tuples == []
    space.boundary()
    got = space.rd(("r", "?x"))
    assert got["fields"] == ["v"]
    assert got["provenance"] == {"task": "t1"}


def test_eval_failure_receipted():
    space = TupleSpace()
    space.declare_tag("r", 1)

    def boom():
        raise ValueError("nope")

    space.eval(boom, "r", task_id="t9")
    space.boundary()
    assert any(
        r["op"] == "eval_failed" and r["task_id"] == "t9" for r in space.receipts()
    )


def test_blackboard_adapter_protocol():
    space = LocalSpace()
    space.declare_tag("b", 1)
    space.post_tuple("b", "x")
    assert space.read_tuple(("b", "?v"))["fields"] == ["x"]
    assert space.take_tuple(("b", "?v"))["fields"] == ["x"]


def test_t7_offline_socket_blocked():
    with pytest.raises(RuntimeError):
        socket.socket()
