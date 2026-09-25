"""Tests for levi.methods.concatenative (Stackscript)."""

import pytest

from levi.methods.concatenative import StackError, StackMachine, run


def stack_of(source, **kw):
    stack, _ = run(source, **kw)
    return stack


def test_literals():
    assert stack_of('1 2.5 "hi"') == [1, 2.5, "hi"]


def test_arithmetic():
    assert stack_of("3 4 +") == [7]
    assert stack_of("10 4 -") == [6]
    assert stack_of("3 4 *") == [12]
    assert stack_of("7 2 /") == [3.5]
    assert stack_of("7 3 mod") == [1]
    assert stack_of("5 neg abs") == [5]


def test_stack_ops():
    assert stack_of("1 2 dup") == [1, 2, 2]
    assert stack_of("1 2 drop") == [1]
    assert stack_of("1 2 swap") == [2, 1]
    assert stack_of("1 2 over") == [1, 2, 1]
    assert stack_of("1 2 3 rot") == [2, 3, 1]
    assert stack_of("1 2 nip") == [2]
    assert stack_of("7 depth") == [7, 1]


def test_comparison_and_logic():
    assert stack_of("3 3 =") == [1]
    assert stack_of("3 4 <>") == [1]
    assert stack_of("2 3 < 3 2 > and") == [1]
    assert stack_of("0 not") == [1]
    assert stack_of("9 not") == [0]


def test_word_definition():
    assert stack_of(": sq dup * ; 5 sq") == [25]
    assert stack_of(": double 2 * ; : quad double double ; 3 quad") == [12]


def test_redefine_builtin_refused():
    with pytest.raises(StackError):
        run(": + 1 ;")


def test_if_else_then():
    assert stack_of("1 if 10 else 20 then") == [10]
    assert stack_of("0 if 10 else 20 then") == [20]
    assert stack_of("0 if 10 then 99") == [99]


def test_nested_if():
    assert stack_of("1 if 1 if 7 else 8 then else 9 then") == [7]
    assert stack_of("1 if 0 if 7 else 8 then else 9 then") == [8]


def test_begin_until():
    # countdown 3 -> leaves 0
    assert stack_of("3 begin 1 - dup 0 = until") == [0]


def test_quotation_times():
    assert stack_of("0 5 [ 1 + ] times") == [5]
    assert stack_of('3 [ "x" ] times') == ["x", "x", "x"]


def test_call():
    assert stack_of("[ 2 3 + ] call") == [5]


def test_underflow_is_deny_closed():
    with pytest.raises(StackError):
        run("1 +")


def test_unknown_word():
    with pytest.raises(StackError):
        run("frobnicate")


def test_division_by_zero():
    with pytest.raises(StackError):
        run("1 0 /")
    with pytest.raises(StackError):
        run("1 0 mod")


def test_depth_limit():
    with pytest.raises(StackError):
        run("1 2 3", max_depth=2)


def test_step_limit_halts_infinite_loop():
    with pytest.raises(StackError):
        run("begin 0 until", max_steps=50)


def test_unterminated_string():
    with pytest.raises(StackError):
        run('"oops')


def test_colon_without_semicolon():
    with pytest.raises(StackError):
        run(": foo 1 2")


def test_if_without_then():
    with pytest.raises(StackError):
        run("1 if 2")


def test_receipt_reports_work():
    _, receipt = run(": sq dup * ; 5 sq")
    assert receipt.steps > 0
    assert receipt.max_depth >= 2
    assert receipt.words_defined == ["sq"]
    assert receipt.words_called.get("sq") == 1
    assert receipt.words_called.get("dup") == 1


def test_receipt_serializes():
    _, receipt = run("1 2 +")
    d = receipt.to_dict()
    assert set(d) == {"steps", "max_depth", "words_defined", "words_called"}


def test_string_concatenation_allowed():
    # string + string is well-defined; the deny-closed rule is about
    # violations, and concatenation is useful for recipe building.
    assert stack_of('"a" "b" +') == ["ab"]


def test_type_mismatch_is_deny_closed():
    with pytest.raises(StackError):
        run('"a" 1 +')


def test_machine_bounds_must_be_positive():
    with pytest.raises(ValueError):
        StackMachine(max_steps=0)
    with pytest.raises(ValueError):
        StackMachine(max_depth=-1)


def test_min_max():
    assert stack_of("3 9 min") == [3]
    assert stack_of("3 9 max") == [9]


def test_negative_times_refused():
    with pytest.raises(StackError):
        run("-1 [ 1 ] times")


def test_call_non_quotation_refused():
    with pytest.raises(StackError):
        run("5 call")
