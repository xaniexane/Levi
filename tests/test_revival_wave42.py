"""Tests for revival wave 42: language mechanisms & verification discipline."""

import pytest

from core.levi.revival import forth_words as forth
from core.levi.revival import hypertalk as ht
from core.levi.revival import prolog_clauses as pl
from core.levi.revival import apl_arrays as apl
from core.levi.revival import casting_nines as cn
from core.levi.revival import independent_dup as dup
from core.levi.revival import independent_recompute as rec
from core.levi.revival import receipt_product as rp


# ---------------------------------------------------------------------------
# forth_words
# ---------------------------------------------------------------------------


def test_forth_arithmetic_and_stack():
    m = forth.new_machine()
    forth.run(m, "2 3 + 4 *")
    assert m.data == [20]
    forth.run(m, "dup *")
    assert m.data == [400]


def test_forth_colon_word_and_branch():
    out = forth.evaluate(
        ": square dup * ; 5 square . : abs dup 0< if negate then ; -7 abs ."
    )
    assert out == "25 7 "


def test_forth_do_loop_and_output():
    out = forth.evaluate(': count 5 0 do i . loop ; count cr ."done"')
    assert out == "0 1 2 3 4 \ndone"


def test_forth_errors_are_typed():
    m = forth.new_machine()
    with pytest.raises(forth.StackUnderflow):
        forth.run(m, "drop")
    with pytest.raises(forth.UnknownWord):
        forth.run(m, "frobnicate")
    with pytest.raises(forth.CompileError):
        forth.run(m, ": broken 1 2 ; extra ;")


# ---------------------------------------------------------------------------
# hypertalk
# ---------------------------------------------------------------------------


def _demo_stack():
    stack = ht.Stack("demo")
    card = stack.add_card("first")
    card.add_field("greeting", "hello")
    card.add_field("name")
    return stack


def test_hypertalk_put_get_answer():
    stack = _demo_stack()
    ht.run_script(
        stack,
        [
            'get field "greeting"',
            'put it & ", world" into field "name"',
            'answer field "name"',
        ],
    )
    assert stack.card().get_field("name").text == "hello, world"
    assert stack.answer_log == ["hello, world"]


def test_hypertalk_navigation_and_if():
    stack = _demo_stack()
    stack.add_card("second").add_field("note", "x")
    ht.run_script(
        stack,
        [
            "go to card 2",
            'if field "note" is "x" then',
            'put "seen" into field "note"',
            "end if",
        ],
    )
    assert stack.current == 1
    assert stack.card().get_field("note").text == "seen"


def test_hypertalk_handler_and_ask():
    stack = _demo_stack()
    ht.install_handler(
        stack.card(), 'on mouseUp\nput "clicked" into field "name"\nend mouseUp'
    )
    ht.send(stack, "mouseUp")
    assert stack.card().get_field("name").text == "clicked"
    stack.answers = ["Chauncey"]
    ht.run_script(stack, ['ask "your name?"'])
    assert stack.it == "Chauncey"


def test_hypertalk_inspectable_and_errors():
    stack = _demo_stack()
    view = stack.inspect()
    assert view["cards"][0]["fields"]["greeting"]["text"] == "hello"
    with pytest.raises(ht.NoSuchField):
        ht.run_script(stack, ['get field "missing"'])
    with pytest.raises(ht.ScriptError):
        ht.run_script(stack, ["wiggle the wobble"])


# ---------------------------------------------------------------------------
# prolog_clauses
# ---------------------------------------------------------------------------


_FAMILY = """
parent(tom, bob).
parent(bob, ann).
parent(tom, liz).
male(tom).
male(bob).
grandparent(X, Z) :- parent(X, Y), parent(Y, Z).
ancestor(X, Y) :- parent(X, Y).
ancestor(X, Z) :- parent(X, Y), ancestor(Y, Z).
"""


def test_prolog_facts_and_rule():
    kb = pl.KnowledgeBase()
    kb.assert_program(_FAMILY)
    assert kb.ask("parent(tom, bob)") == [{}]
    assert kb.ask("parent(tom, ann)") == []


def test_prolog_backtracking_bindings():
    kb = pl.KnowledgeBase()
    kb.assert_program(_FAMILY)
    kids = kb.ask("parent(tom, X)")
    assert {str(b["X"]) for b in kids} == {"bob", "liz"}
    gps = kb.ask("grandparent(tom, Z)")
    assert [str(b["Z"]) for b in gps] == ["ann"]


def test_prolog_recursive_rule_and_unify():
    kb = pl.KnowledgeBase()
    kb.assert_program(_FAMILY)
    ancs = {str(b["Y"]) for b in kb.ask("ancestor(tom, Y)")}
    assert ancs == {"bob", "liz", "ann"}
    # unification unit checks
    assert pl.unify(pl.Atom("a"), pl.Atom("a"), {}) == {}
    assert pl.unify(pl.Atom("a"), pl.Atom("b"), {}) is None
    # occurs check: X = f(X) must fail
    s = pl.unify(pl.Var("X"), pl.Compound("f", (pl.Var("X"),)), {})
    assert s is None


def test_prolog_parse_errors():
    kb = pl.KnowledgeBase()
    with pytest.raises(pl.ParseError):
        kb.assert_clause("not a clause")
    with pytest.raises(pl.ParseError):
        kb.assert_clause("parent(tom, bob)")  # missing closing dot


# ---------------------------------------------------------------------------
# apl_arrays
# ---------------------------------------------------------------------------


def test_apl_elementwise_and_scalar_broadcast():
    v = apl.Array.vector([1, 2, 3])
    assert (v + v).to_list() == [2, 4, 6]
    assert (v * 10).to_list() == [10, 20, 30]
    assert (v - 1).to_list() == [0, 1, 2]
    with pytest.raises(ValueError):
        v + apl.Array.vector([1, 2])


def test_apl_reduce_scan_iota():
    v = apl.Array.iota(5)
    assert v.to_list() == [1, 2, 3, 4, 5]
    assert v.sum() == 15
    assert v.product() == 120
    assert v.scan(lambda a, b: a + b).to_list() == [1, 3, 6, 10, 15]
    assert v.maximum() == 5
    assert v.minimum() == 1


def test_apl_outer_inner_transpose():
    a = apl.Array.vector([1, 2])
    b = apl.Array.vector([10, 20, 30])
    assert a.outer(b).shape == (2, 3)
    assert a.outer(b).to_list() == [[10, 20, 30], [20, 40, 60]]
    m = apl.Array.matrix([[1, 2], [3, 4]])
    assert (m.inner(m)).to_list() == [[7, 10], [15, 22]]  # matrix multiply
    assert m.transpose().to_list() == [[1, 3], [2, 4]]


def test_apl_selection_verbs():
    v = apl.Array.vector([5, 1, 4, 2, 3])
    assert v.compress([1, 0, 1, 0, 1]).to_list() == [5, 4, 3]
    assert v.grade_up().to_list() == [2, 4, 5, 3, 1]
    assert v.rotate(2).to_list() == [4, 2, 3, 5, 1]
    assert v.reshape((5, 1)).shape == (5, 1)
    assert (v.catenate(apl.Array.vector([9]))).to_list() == [5, 1, 4, 2, 3, 9]


# ---------------------------------------------------------------------------
# casting_nines
# ---------------------------------------------------------------------------


def test_casting_nines_catches_wrong_product():
    good = cn.check("mul", 1234, 5678, 1234 * 5678)
    assert good.agrees
    bad = cn.check("mul", 1234, 5678, 7006652 + 7)  # off by 7
    assert not bad.agrees
    assert "DISAGREES" in bad.explain()


def test_casting_elevens_catches_transposition():
    correct = 7006652
    swapped = 7006562  # adjacent digits swapped
    assert cn.check("mul", 1234, 5678, correct, modulus=9).agrees
    # mod 9 cannot see the swap; mod 11 can
    assert cn.check("mul", 1234, 5678, swapped, modulus=9).agrees
    assert not cn.check("mul", 1234, 5678, swapped, modulus=11).agrees
    both = cn.check_both("mul", 1234, 5678, swapped)
    assert both[9].agrees and not both[11].agrees


def test_casting_digit_sums():
    assert cn.cast_out(9875) == (9 + 8 + 7 + 5) % 9
    assert cn.digital_root(9875) == 2
    assert cn.cast_out(0) == 0
    with pytest.raises(cn.CheckError):
        cn.cast_out(10, modulus=7)
    with pytest.raises(cn.CheckError):
        cn.check("div", 1, 2, 0)


# ---------------------------------------------------------------------------
# independent_dup
# ---------------------------------------------------------------------------


def _checker():
    c = dup.DuplicateCheck()
    c.register(
        dup.Method("iterative", "team-alpha", lambda n: sum(range(n + 1)), "loop sum")
    )
    c.register(
        dup.Method("formula", "team-beta", lambda n: n * (n + 1) // 2, "closed form")
    )
    return c


def test_dup_agreement():
    report = _checker().verify("iterative", "formula", 100)
    assert report.agreed
    assert len(report.attempts) == 2


def test_dup_same_team_refused_and_mismatch_flagged():
    c = _checker()
    c.register(dup.Method("iterative2", "team-alpha", lambda n: n, "same team"))
    with pytest.raises(dup.SameTeamError):
        c.verify("iterative", "iterative2", 10)
    c.register(dup.Method("wrong", "team-gamma", lambda n: n * n, "deliberately wrong"))
    report = c.verify("iterative", "wrong", 10)
    assert not report.agreed
    assert any("mismatch" in n for n in report.notes)


def test_dup_tolerance_and_failure_capture():
    c = dup.DuplicateCheck()
    c.register(dup.Method("a", "t1", lambda: 1.0 / 3))
    c.register(dup.Method("b", "t2", lambda: 0.333))
    assert c.verify("a", "b", tolerance=0.001).agreed
    assert not c.verify("a", "b").agreed  # exact equality fails
    c.register(dup.Method("boom", "t3", lambda: 1 / 0))
    report = c.verify("a", "boom")
    assert not report.agreed
    assert any(not a.ok for a in report.attempts)


# ---------------------------------------------------------------------------
# independent_recompute
# ---------------------------------------------------------------------------


def _recompute(label, inputs):
    if label == "sum":
        return sum(inputs["items"])
    raise KeyError(label)


def test_recompute_receipts():
    r = rec.Receipt.issue("total", 7006652)
    assert r.matches(7006652)
    assert not r.matches(7006653)
    # mod 9 is blind to the swap, but the receipt's mod-11 half catches it
    assert rec._residues(7006652)[9] == rec._residues(7006562)[9]
    assert rec._residues(7006652)[11] != rec._residues(7006562)[11]
    assert not r.matches(7006562)


def test_recompute_trial_balance():
    tb = rec.TrialBalance()
    tb.post("sale", debit=100.0)
    tb.post("sale", credit=100.0)
    assert tb.is_balanced()
    assert tb.close() == {"debit": 100.0, "credit": 100.0}
    tb.post("orphan", debit=5.0)
    with pytest.raises(rec.UnbalancedBooks):
        tb.close()
    with pytest.raises(rec.UnbalancedBooks):
        tb.post("bad", debit=1.0, credit=1.0)


def test_recompute_audit_log_clean_and_tampered():
    log = rec.AuditLog(_recompute)
    log.record("sum", {"items": [1, 2, 3]}, 6)
    log.record("sum", {"items": [10, 20]}, 30)
    report = log.audit()
    assert report.clean
    assert report.entries_checked == 2
    # tamper with a result: chain breaks
    log.entries[0] = rec.LogEntry(
        seq=log.entries[0].seq,
        label=log.entries[0].label,
        inputs=log.entries[0].inputs,
        result=999,
        receipt=log.entries[0].receipt,
        prev_hash=log.entries[0].prev_hash,
        entry_hash=log.entries[0].entry_hash,
    )
    bad = log.audit()
    assert not bad.clean
    assert not bad.chain_ok


# ---------------------------------------------------------------------------
# receipt_product
# ---------------------------------------------------------------------------


def test_receipt_tape_lines():
    calc = rp.ReceiptingCalculator()
    assert calc.add(12, 30) == 42
    assert calc.mul(6, 7) == 42
    line = calc.tape.receipts[0].tape_line()
    assert line.startswith("0000  add    12 30 = 42")
    assert "[levi-arithmetic]" in line


def test_receipt_verify_and_tamper():
    calc = rp.ReceiptingCalculator()
    calc.add(1, 2)
    receipt = calc.tape.receipts[0]
    assert receipt.verify()
    tampered = rp.Receipt(
        seq=receipt.seq,
        operation=receipt.operation,
        inputs=receipt.inputs,
        output=999,
        method=receipt.method,
        digest=receipt.digest,
    )
    assert not tampered.verify()
    calc.tape.receipts[0] = tampered
    assert calc.tape.verify() != []


def test_receipt_seal_and_audit():
    calc = rp.ReceiptingCalculator()
    calc.sub(10, 4)
    calc.div(20, 5)
    seal = calc.tape.seal()
    assert calc.tape.sealed and len(seal) == 64
    audit = calc.audit()
    assert audit["clean"] and audit["entries"] == 2
    with pytest.raises(rp.ReceiptError):
        calc.add(1, 1)  # sealed tape refuses new entries
    print_out = calc.tape.print_tape()
    assert "SEAL" in print_out and "0001" in print_out
