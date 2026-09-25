"""Acceptance tests for phase3/prover (A5 salvage formal spec, T1-T6).

Hermetic: no network, no daemons, no HOME writes. Sockets are blocked
in the T6 offline test by a local fixture (no import of the beginning
team's synthesis/offline.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from levi.phase3.prover import (
    Atom,
    Budget,
    Compound,
    DictFactSource,
    DictRuleSource,
    Fact,
    Rule,
    Var,
    explain,
    prove,
    unify,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_sockets(monkeypatch):
    """Block all socket use: the offline test must not touch the network."""
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network access is disabled in this test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    return True


# ---------------------------------------------------------------- T1
def _unify_battery():
    """Yield (t1, t2, expected_subst_or_None); exactly 500 cases."""
    cases = []
    for i in range(60):  # atom == atom
        cases.append((Atom(f"a{i}"), Atom(f"a{i}"), {}))
    for i in range(60):  # atom != atom
        cases.append((Atom(f"a{i}"), Atom(f"b{i}"), None))
    for i in range(60):  # atom vs var
        cases.append((Atom(f"a{i}"), Var(f"X{i}"), {f"X{i}": Atom(f"a{i}")}))
    for i in range(40):  # var vs var
        cases.append((Var(f"X{i}"), Var(f"Y{i}"), {f"X{i}": Var(f"Y{i}")}))
    for i in range(60):  # compound, same functor/arity
        cases.append(
            (
                Compound("f", (Var("X"), Atom(f"a{i}"))),
                Compound("f", (Atom(f"b{i}"), Var("Y"))),
                {"X": Atom(f"b{i}"), "Y": Atom(f"a{i}")},
            )
        )
    for _ in range(40):  # functor mismatch
        cases.append((Compound("f", (Var("X"),)), Compound("g", (Var("X"),)), None))
    for _ in range(40):  # arity mismatch
        cases.append(
            (
                Compound("f", (Var("X"), Var("Y"))),
                Compound("f", (Var("X"),)),
                None,
            )
        )
    for i in range(40):  # nested compounds
        cases.append(
            (
                Compound("g", (Compound("f", (Var("X"),)),)),
                Compound("g", (Compound("f", (Atom(f"z{i}"),)),)),
                {"X": Atom(f"z{i}")},
            )
        )
    for i in range(40):  # occurs check
        if i % 2 == 0:
            cases.append((Var("X"), Compound("f", (Var("X"),)), None))
        else:
            cases.append((Var("X"), Compound("f", (Atom(f"a{i}"), Var("X"))), None))
    for i in range(30):  # chained bindings
        cases.append(
            (
                Compound("f", (Var("X"), Var("Y"))),
                Compound("f", (Var("Y"), Atom(f"a{i}"))),
                {"X": Atom(f"a{i}"), "Y": Atom(f"a{i}")},
            )
        )
    for i in range(30):  # pre-existing substitution is extended
        cases.append(
            (
                Compound("f", (Var("X"),)),
                Compound("f", (Atom(f"a{i}"),)),
                {"X": Var("Z"), "Z": Atom(f"a{i}")},
                {"X": Var("Z")},
            )
        )
    assert len(cases) == 500, len(cases)
    return cases


def test_t1_unification_battery_500_cases():
    fails = []
    for idx, case in enumerate(_unify_battery()):
        t1, t2 = case[0], case[1]
        expected = case[2]
        seed = case[3] if len(case) == 4 else None
        got = unify(t1, t2, seed)
        if got != expected:
            fails.append((idx, t1, t2, expected, got))
    assert not fails, "unification mismatches: %r" % (fails[:5],)


# ---------------------------------------------------------------- T2
def _family_base(n_people=12):
    """Chain family: parent(p0,p1), parent(p1,p2), ... plus grandparent
    and transitive ancestor rules."""
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    rules = DictRuleSource(
        [
            Rule(
                id="gp1",
                head=Compound("grandparent", (X, Z)),
                body=[Compound("parent", (X, Y)), Compound("parent", (Y, Z))],
                provenance="test",
            ),
            Rule(
                id="anc1",
                head=Compound("ancestor", (X, Y)),
                body=[Compound("parent", (X, Y))],
                provenance="test",
            ),
            Rule(
                id="anc2",
                head=Compound("ancestor", (X, Z)),
                body=[Compound("parent", (X, Y)), Compound("ancestor", (Y, Z))],
                provenance="test",
            ),
        ]
    )
    facts = DictFactSource(
        [
            Fact(
                id=f"f{i}",
                term=Compound("parent", (Atom(f"p{i}"), Atom(f"p{i + 1}"))),
                witness=f"r-{i}",
            )
            for i in range(n_people - 1)
        ]
    )
    return rules, facts


def _prove_grandparent():
    rules, facts = _family_base()
    goal = Compound("grandparent", (Atom("p0"), Atom("p2")))
    return prove(goal, rules, facts, Budget(max_depth=8, max_ms=5000))


def test_t2_determinism_50_runs_byte_identical():
    first = _prove_grandparent().tree.to_json()
    for _ in range(49):
        assert _prove_grandparent().tree.to_json() == first


def test_t2_determinism_across_processes():
    code = (
        "import json,sys; sys.path.insert(0, %r); "
        "from levi.phase3.prover import Atom,Compound,Budget,prove; "
        "from tests.test_phase3_prover import _family_base; "
        "rules,facts=_family_base(); "
        "o=prove(Compound('grandparent',(Atom('p0'),Atom('p2'))),rules,facts,Budget(max_depth=8,max_ms=5000)); "
        "print(o.tree.to_json())" % str(REPO_ROOT / "core")
    )
    outs = set()
    for _ in range(2):
        p = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert p.returncode == 0, p.stderr[-2000:]
        outs.add(p.stdout.strip())
    assert len(outs) == 1
    assert outs.pop() == _prove_grandparent().tree.to_json()


# ---------------------------------------------------------------- T3
def _exploding_rules():
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    return DictRuleSource(
        [
            Rule(
                id="b1",
                head=Compound("p", (X,)),
                body=[Compound("p", (Y,)), Compound("p", (Z,))],
                provenance="test: adversarial branching",
            )
        ]
    )


def test_t3_budget_depth_fault_is_receipted():
    outcome = prove(
        Compound("p", (Atom("q"),)),
        _exploding_rules(),
        DictFactSource([]),
        Budget(max_depth=16, max_branches=10**9, max_ms=60_000),
    )
    assert not outcome.proved
    assert outcome.fault is not None
    assert outcome.fault.reason == "budget-exhausted"
    assert outcome.fault.receipt_id.startswith("prf-fault-")
    assert "depth 17" in outcome.fault.detail


def test_t3_budget_branch_fault_is_receipted():
    outcome = prove(
        Compound("p", (Atom("q"),)),
        _exploding_rules(),
        DictFactSource([]),
        Budget(max_depth=10**6, max_branches=500, max_ms=60_000),
    )
    assert not outcome.proved
    assert outcome.fault is not None
    assert outcome.fault.reason == "budget-exhausted"
    assert "branch" in outcome.fault.detail


def test_t3_budget_time_no_hang():
    import time

    start = time.monotonic()
    outcome = prove(
        Compound("p", (Atom("q"),)),
        _exploding_rules(),
        DictFactSource([]),
        Budget(max_depth=10**6, max_branches=10**9, max_ms=400),
    )
    elapsed = time.monotonic() - start
    assert not outcome.proved
    assert outcome.fault is not None
    assert outcome.fault.reason == "budget-exhausted"
    assert elapsed < 30, "search hung: %.1fs" % elapsed


# ---------------------------------------------------------------- T4
def test_t4_explanation_completeness_100_claims():
    rules, facts = _family_base(n_people=20)
    goals = []
    for i in range(20):
        for j in range(i + 1, 20):
            goals.append(Compound("ancestor", (Atom(f"p{i}"), Atom(f"p{j}"))))
    goals = goals[:100]
    assert len(goals) == 100
    checked = 0
    for goal in goals:
        outcome = prove(goal, rules, facts, Budget(max_depth=40, max_ms=5000))
        assert outcome.proved, "expected provable: %r" % (goal,)
        assert set(outcome.audit) == outcome.tree.premises(), (
            "premise mismatch for %r: audit=%r tree=%r"
            % (goal, outcome.audit, outcome.tree.premises())
        )
        checked += 1
    assert checked == 100


# ---------------------------------------------------------------- T5
def test_t5_witnessed_leaves_200_proofs():
    rules, facts = _family_base(n_people=210)
    goals = []
    for i in range(100):
        goals.append(Compound("parent", (Atom(f"p{i}"), Atom(f"p{i + 1}"))))
        goals.append(Compound("ancestor", (Atom(f"p{i}"), Atom(f"p{i + 5}"))))
    assert len(goals) == 200
    done = 0
    for goal in goals:
        outcome = prove(goal, rules, facts, Budget(max_depth=40, max_ms=5000))
        assert outcome.proved, "expected provable: %r" % (goal,)
        leaves = outcome.tree.leaves()
        assert leaves, "proof without leaves for %r" % (goal,)
        for leaf in leaves:
            assert leaf.witness and leaf.witness.strip(), (
                "unwitnessed leaf in proof of %r" % (goal,)
            )
        done += 1
    assert done == 200


def test_t5_unwitnessed_fact_impossible_by_construction():
    with pytest.raises(ValueError):
        Fact(id="bad", term=Atom("x"), witness="  ")
    with pytest.raises(ValueError):
        Fact(id="bad", term=Atom("x"), witness="")


# ---------------------------------------------------------------- T6
def test_t6_offline_prove_and_explain(no_sockets):
    assert no_sockets
    outcome = _prove_grandparent()
    assert outcome.proved
    text = explain(outcome)
    assert "grandparent" in text
    assert "r-0" in text or "r-1" in text
    # The canonical JSON of the tree round-trips through dict form.
    data = json.loads(outcome.tree.to_json())
    assert data["claim"]["f"] == "grandparent"
