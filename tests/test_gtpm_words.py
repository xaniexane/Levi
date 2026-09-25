"""Acceptance tests for levi.gtpm.words (the dictionary).

Hermetic: no network, no daemons, no HOME writes. Deterministic: no
randomness anywhere in this file — every battery is generated from fixed
arithmetic sequences.

Honest coverage notes (see words.py docstring):
- T2 (dictionary economy over 6 months) is longitudinal — not testable in
  one run; not claimed.
- T3 (gloss accuracy) gates on Chauncey or his delegate auditing a
  100-word sample; not claimed.
"""

import ast
import contextlib
import socket
from pathlib import Path
from unittest import mock

import pytest

from levi.gtpm import words
from levi.gtpm.words import (
    PRIMITIVE_EFFECTS,
    PRIMITIVE_GLOSS,
    EffectError,
    StackError,
    UndefinedWordError,
    WordError,
    deprecate,
    define,
    execute,
    extend_vocabulary,
    gloss,
    new_dictionary,
    replay,
    retire,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _net_effect(tokens):
    """Static net stack change of a token list (literals push one)."""
    depth = 0
    for t in tokens:
        if t in PRIMITIVE_EFFECTS:
            i, o = PRIMITIVE_EFFECTS[t]
            depth += o - i
        else:
            depth += 1
    return depth


@contextlib.contextmanager
def _no_sockets():
    def boom(*a, **k):
        raise OSError("sockets disabled for this test")

    with (
        mock.patch.object(socket, "socket", boom),
        mock.patch.object(socket, "create_connection", boom),
    ):
        yield


def _battery_specs():
    specs = []
    for i in range(10):
        specs.append(
            (
                f"arith{i:02d}",
                [str(7 + i), "3", "mul", str(2 + i), "add"],
                0,
                [],
                [23 + 4 * i],
            )
        )
        specs.append((f"dbl{i:02d}", ["dup", "add"], 1, [i], [2 * i]))
        specs.append(
            (
                f"lst{i:02d}",
                ["[]", str(i), "append", str(i + 1), "append", "len"],
                0,
                [],
                [2],
            )
        )
        specs.append(
            (f"dct{i:02d}", ["{}", "k", str(i), "put", "k", "get"], 0, [], [i])
        )
        specs.append(
            (f"div{i:02d}", [str(100 + 7 * i), "7", "divmod", "add"], 0, [], [16 + i])
        )
    return specs  # 50 behaviors


# ---------------------------------------------------------------------------
# shape + primitive contract
# ---------------------------------------------------------------------------


def test_new_dictionary_shape():
    d = new_dictionary()
    assert d == {
        "words": [],
        "by_name": {},
        "history": {},
        "version": 1,
        "warnings": [],
        "receipts": [],
    }


def test_primitive_effects_and_gloss_cover_closed_set():
    expected = {
        "dup",
        "drop",
        "swap",
        "over",
        "rot",
        "depth",
        "add",
        "sub",
        "mul",
        "divmod",
        "neg",
        "eq",
        "neq",
        "gt",
        "lt",
        "gte",
        "lte",
        "and",
        "or",
        "not",
        "len",
        "cons",
        "uncons",
        "append",
        "get",
        "put",
        "del",
        "keys",
    }
    assert set(PRIMITIVE_EFFECTS) == expected
    assert set(PRIMITIVE_GLOSS) == expected
    for name, (n_in, n_out) in PRIMITIVE_EFFECTS.items():
        assert isinstance(n_in, int) and isinstance(n_out, int)
        assert n_in >= 0 and n_out >= 0
        assert PRIMITIVE_GLOSS[name].strip()


def test_define_receipt_shape():
    d = new_dictionary()
    r = define(d, "inc", ["1", "add"], ("1", "1"))
    assert r["kind"] == "define"
    assert r["word"] == "inc"
    assert r["definition"] == ["1", "add"]
    assert r["stack_check"] is True
    assert r["gloss"].strip()
    assert r["t"].startswith("r")
    assert r["shadowed"] is False
    assert d["receipts"][-1] == r
    w = d["by_name"]["inc"]
    assert w["stack_effect"] == ("1", "1")
    assert w["status"] == "active"
    assert w["provenance"] == []
    assert w["fired_count"] == 0


def test_define_primitive_name_rejected():
    d = new_dictionary()
    for prim in ("add", "dup", "get", "depth"):
        with pytest.raises(WordError):
            define(d, prim, ["1"], ("0", "1"))


# ---------------------------------------------------------------------------
# T1 — replay fidelity: 50 behaviors × 20 replays, 100% identical
# ---------------------------------------------------------------------------


def test_t1_replay_fidelity():
    d = new_dictionary()
    specs = _battery_specs()
    assert len(specs) == 50
    for name, tokens, n_in, _, _ in specs:
        n_out = n_in + _net_effect(tokens)
        define(d, name, tokens, (str(n_in), str(n_out)))
    total = 0
    for name, _, _, inputs, expected in specs:
        first = replay(d, name, inputs)
        assert first == expected, f"{name}: wrong value {first}"
        for _ in range(19):
            assert replay(d, name, inputs) == first, f"{name}: replay drift"
            total += 1
        total += 1
        # execute must not mutate the caller's stack
        probe = list(inputs)
        execute(d, name, probe)
        assert probe == inputs
    assert total == 50 * 20


# ---------------------------------------------------------------------------
# T4 — hygiene: 50 shadow/deprecate/retire scenarios
# ---------------------------------------------------------------------------


def test_t4_hygiene_shadowing_deprecation_retirement():
    d = new_dictionary()
    for i in range(50):
        name = f"w{i:02d}"
        r1 = define(d, name, ["1"], ("0", "1"))
        assert r1["shadowed"] is False
        r2 = define(d, name, ["2"], ("0", "1"))
        assert r2["shadowed"] is True
        assert r2["gloss"] != r1["gloss"]  # gloss regenerates on redefine
        # zero silent overwrites: old definition retained verbatim
        assert len(d["history"][name]) == 1
        assert d["history"][name][0]["definition"] == ["1"]
        assert d["by_name"][name]["definition"] == ["2"]
        assert d["by_name"][name]["status"] == "active"
        # deprecate: keeps working, warns
        dep = deprecate(d, name)
        assert dep["kind"] == "deprecate"
        before = len(d["warnings"])
        assert execute(d, name, []) == [2]
        assert len(d["warnings"]) == before + 1
        assert d["warnings"][-1]["word"] == name
        # a NEW definition using the deprecated word warns at define time
        before = len(d["warnings"])
        define(d, f"use_{name}", [name], ("0", "1"))
        assert len(d["warnings"]) == before + 1
        # retire requires a migration note
        with pytest.raises(ValueError):
            retire(d, name, "")
        with pytest.raises(ValueError):
            retire(d, name, "   ")
        rec = retire(d, name, f"replaced by v2 in scenario {i}")
        assert rec["kind"] == "retire"
        assert rec["migration"] == f"replaced by v2 in scenario {i}"
        with pytest.raises(WordError):
            execute(d, name, [])
    # every shadow retained exactly once; every lifecycle step receipted
    assert sum(len(v) for v in d["history"].values()) == 50
    assert len(d["receipts"]) == 50 * 5  # 2 defines + consumer + deprecate + retire


def test_deprecate_and_retire_unknown_word():
    d = new_dictionary()
    with pytest.raises(UndefinedWordError):
        deprecate(d, "nope")
    with pytest.raises(UndefinedWordError):
        retire(d, "nope", "migration")


def test_deprecate_retired_word_fails():
    d = new_dictionary()
    define(d, "w", ["1"], ("0", "1"))
    retire(d, "w", "gone")
    with pytest.raises(WordError):
        deprecate(d, "w")


# ---------------------------------------------------------------------------
# T5 — fail-closed: 200 undefined executions → 200 faults
# ---------------------------------------------------------------------------


def test_t5_fail_closed_undefined_words():
    d = new_dictionary()
    define(d, "real", ["1"], ("0", "1"))
    faults = 0
    for i in range(200):
        try:
            execute(d, f"ghost_{i:03d}", [i])
        except UndefinedWordError:
            faults += 1
        except WordError:
            pytest.fail("undefined word raised a non-specific WordError path")
    assert faults == 200
    # no collateral damage: defined words still work
    assert execute(d, "real", []) == [1]


# ---------------------------------------------------------------------------
# T6 — effect closure: no I/O modules at import; battery under I/O audit
# ---------------------------------------------------------------------------


def test_t6_import_closure_has_no_io_modules():
    src = Path(words.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    found.discard("__future__")
    banned = {
        "socket",
        "subprocess",
        "urllib",
        "requests",
        "http",
        "os",
        "sys",
        "shutil",
        "pathlib",
        "ctypes",
    }
    assert not (found & banned), f"I/O-adjacent imports: {found & banned}"
    assert found == set(), f"module should import nothing at runtime: {found}"


def test_t6_effect_closure_runtime_audit():
    d = new_dictionary()
    define(d, "battery", ["dup", "mul", "2", "divmod"], ("1", "2"))
    define(
        d,
        "dictwork",
        ["{}", "a", "1", "put", "b", "2", "put", "keys", "len"],
        ("0", "1"),
    )

    def boom(*a, **k):
        raise AssertionError("I/O attempted during word execution")

    errors = []
    with mock.patch("builtins.open", boom), mock.patch.object(socket, "socket", boom):
        try:
            for n in range(30):
                got = replay(d, "battery", [n])
                assert got == [(n * n) // 2, (n * n) % 2]
                assert replay(d, "dictwork", []) == [2]
        except Exception as e:  # noqa: BLE001 — audit must not leak
            errors.append(repr(e))
    assert errors == []


# ---------------------------------------------------------------------------
# T7 — offline: define + execute + replay with sockets disabled
# ---------------------------------------------------------------------------


def test_t7_offline_define_execute_replay():
    with _no_sockets():
        d = new_dictionary()
        define(d, "avg2", ["add", "2", "divmod", "drop"], ("2", "1"))
        assert execute(d, "avg2", [7, 9]) == [8]
        assert replay(d, "avg2", [7, 9]) == [8]
        define(d, "mk", ["{}", "swap", "x", "swap", "put"], ("1", "1"))
        assert replay(d, "mk", [41]) == [{"x": 41}]


# ---------------------------------------------------------------------------
# define-time stack-effect checking
# ---------------------------------------------------------------------------


def test_stack_underflow_rejected_at_define_time():
    d = new_dictionary()
    with pytest.raises(StackError):
        define(d, "bad1", ["drop", "drop"], ("1", "0"))
    with pytest.raises(StackError):
        define(d, "bad2", ["add", "drop"], ("1", "1"))


def test_wrong_final_depth_rejected_at_define_time():
    d = new_dictionary()
    with pytest.raises(EffectError):
        define(d, "bad3", ["dup", "dup"], ("1", "1"))
    with pytest.raises(EffectError):
        define(d, "bad4", ["1", "2", "add"], ("0", "2"))


def test_bad_stack_effect_strings_rejected():
    d = new_dictionary()
    with pytest.raises(WordError):
        define(d, "bad5", ["1"], ("x", "1"))
    with pytest.raises(WordError):
        define(d, "bad6", ["1"], ("0", "-1"))


def test_unbalanced_via_composed_word_rejected():
    d = new_dictionary()
    define(d, "two", ["1", "2"], ("0", "2"))
    with pytest.raises(EffectError):
        define(d, "bad7", ["two", "add", "add"], ("0", "1"))


def test_building_on_retired_word_rejected():
    d = new_dictionary()
    define(d, "old", ["1"], ("0", "1"))
    retire(d, "old", "superseded")
    with pytest.raises(WordError):
        define(d, "new", ["old"], ("0", "1"))


def test_recursion_guard():
    d = new_dictionary()
    # direct self-reference is allowed at define time (checked against the
    # word's own declared effect) but caught at run time
    define(d, "loop", ["loop"], ("0", "0"))
    with pytest.raises(WordError):
        execute(d, "loop", [])
    # mutual recursion via define-then-redefine is caught too
    define(d, "ping", ["1", "drop"], ("0", "0"))
    define(d, "pong", ["1", "drop"], ("0", "0"))
    define(d, "ping", ["pong"], ("0", "0"))
    define(d, "pong", ["ping"], ("0", "0"))
    with pytest.raises(WordError):
        execute(d, "ping", [])


# ---------------------------------------------------------------------------
# gloss coverage + regeneration
# ---------------------------------------------------------------------------


def test_gloss_coverage_and_regeneration():
    d = new_dictionary()
    define(d, "inc", ["1", "add"], ("1", "1"))
    define(d, "inc2", ["inc", "inc"], ("1", "1"))
    g1 = gloss(d, "inc2")
    assert g1.startswith("inc2: ") and len(g1) > len("inc2: ")
    # every defined word has a non-empty gloss
    for w in d["words"]:
        assert w["gloss"].strip()
        assert gloss(d, w["name"]) == w["gloss"]
    # redefine: gloss regenerates
    define(d, "inc", ["2", "add"], ("1", "1"))
    g2 = gloss(d, "inc")
    assert g2 != "inc: push the number 1 then add the top two numbers"
    assert "push the number 2" in g2
    with pytest.raises(UndefinedWordError):
        gloss(d, "missing")


# ---------------------------------------------------------------------------
# execution semantics
# ---------------------------------------------------------------------------


def test_execute_does_not_mutate_input_stack():
    d = new_dictionary()
    define(d, "w", ["dup", "add", "drop"], ("2", "1"))
    stack = [3, 4]
    out = execute(d, "w", stack)
    assert stack == [3, 4]
    assert out == [3]
    assert out is not stack


def test_fired_count_increments():
    d = new_dictionary()
    define(d, "inner", ["1", "add"], ("1", "1"))
    define(d, "outer", ["inner", "inner"], ("1", "1"))
    execute(d, "outer", [10])
    assert d["by_name"]["outer"]["fired_count"] == 1
    assert d["by_name"]["inner"]["fired_count"] == 2
    replay(d, "outer", [10])
    assert d["by_name"]["outer"]["fired_count"] == 2


def test_execute_undefined_word_is_fail_closed():
    d = new_dictionary()
    with pytest.raises(UndefinedWordError):
        execute(d, "never_defined", [])
    with pytest.raises(WordError):
        execute(d, "never_defined", [])


def test_divmod_quotient_then_remainder():
    d = new_dictionary()
    define(d, "dm", ["divmod"], ("2", "2"))
    assert execute(d, "dm", [7, 3]) == [2, 1]  # q deeper, r on top


def test_depth_reflects_runtime_stack():
    d = new_dictionary()
    define(d, "d", ["depth"], ("0", "1"))
    assert replay(d, "d", []) == [0]
    assert execute(d, "d", [1, 2]) == [1, 2, 2]


def test_dict_words_are_pure():
    d = new_dictionary()
    define(d, "setter", ["x", "9", "put"], ("1", "1"))
    define(d, "killer", ["x", "del"], ("1", "1"))
    original = {"x": 1}
    out = execute(d, "setter", [original])
    assert original == {"x": 1}
    assert out == [{"x": 9}]
    out2 = execute(d, "killer", [original])
    assert original == {"x": 1}
    assert out2 == [{}]


def test_type_errors_are_word_errors_never_silent():
    d = new_dictionary()
    define(d, "t1", ["add"], ("2", "1"))
    with pytest.raises(WordError):
        execute(d, "t1", ["a", "b"])  # strings are not numbers
    define(d, "t2", ["divmod"], ("2", "2"))
    with pytest.raises(WordError):
        execute(d, "t2", [1, 0])  # division by zero
    define(d, "t3", ["get"], ("2", "1"))
    with pytest.raises(WordError):
        execute(d, "t3", [{}, "missing"])  # missing key
    define(d, "t4", ["uncons"], ("1", "2"))
    with pytest.raises(WordError):
        execute(d, "t4", [[]])  # empty list
    define(d, "t5", ["and"], ("2", "1"))
    with pytest.raises(WordError):
        execute(d, "t5", [1, True])  # non-boolean
    define(d, "t6", ["not"], ("1", "1"))
    with pytest.raises(WordError):
        execute(d, "t6", [0])
    # runtime underflow (slipped past define-time because inputs vary)
    define(d, "t7", ["drop"], ("1", "0"))
    with pytest.raises(WordError):
        execute(d, "t7", [])


def test_literal_forms():
    d = new_dictionary()
    define(d, "lits", [], ("0", "0"))
    assert d["by_name"]["lits"]["definition"] == []
    define(d, "lits2", ["42", "3.5", "hello", "[]", "{}"], ("0", "5"))
    assert replay(d, "lits2", []) == [42, 3.5, "hello", [], {}]


def test_extend_vocabulary_batch_define():
    d = new_dictionary()
    receipts = extend_vocabulary(
        d,
        [
            ("one", ["1"], ("0", "1")),
            {
                "name": "two",
                "definition": ["one", "one", "add"],
                "stack_effect": ("0", "1"),
            },
        ],
    )
    assert [r["kind"] for r in receipts] == ["define", "define"]
    assert replay(d, "two", []) == [2]
    # fail-closed: bad entry raises, earlier receipts stand
    with pytest.raises(WordError):
        extend_vocabulary(
            d, [("ok", ["1"], ("0", "1")), ("bad", ["drop", "drop"], ("1", "0"))]
        )
    assert "ok" in d["by_name"]
    assert "bad" not in d["by_name"]
