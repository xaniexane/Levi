"""The dictionary: a Forth-like threaded muscle language for the scan-mind.

Working module name — **naming is Chauncey's**.

GTPM (Chauncey): "Basically analyzing but pure deterministic. I call it
goal targeted predator mentality." This module is a GTPM technique: words
compose words, and every behavior replays with bit-identical determinism —
a predator that locks its target and pursues it without drift.

A word is a threaded list of tokens. Tokens resolve, in order, to a
primitive (the closed set below), a defined word (newest definition wins),
or a literal (``int`` → ``float`` → ``"[]"``/``"{}"`` → plain string).
The inner interpreter walks the list; primitives run their declared
effects only; word tokens recurse with a depth guard.

A dictionary is a vocabulary, not a voice. No sentience or
subjective-experience claims attach to any of this.

Testable claims (from the formal spec) and their honest status:

- T1 replay fidelity — tested: N behaviors × M replays, all outputs
  identical. Cross-process identity is structural (no clock, no random,
  no ambient state), not re-tested per run.
- T2 dictionary economy (median words-per-behavior trending down over
  6 months) — LONGITUDINAL, not testable in one run; not claimed here.
- T3 gloss accuracy — gates on Chauncey or his delegate auditing a
  100-word sample; not claimed here.
- T4 hygiene, T5 fail-closed, T6 effect closure, T7 offline — tested.

Deliberate deviations from the contract/spec, with reasons:

1. The contract says "unknown token → WordError" at define-time, but its
   own example defines ``["add", "2", "divmod", ...]`` — numeric literals
   in definitions. Implemented: token → primitive → defined word →
   literal (int, then float, then the exact tokens ``[]``/``{}`` for
   empty list/dict, else the raw string). Fail-closed is kept at the
   word level: executing an *undefined word name* is always WordError.
2. Spec §4 shows ``stack_effect`` as a ``[str, str]`` list; the interface
   contract says tuple of decimal strings — implemented as a tuple.
3. Spec §5 places this at ``core/levi/synthesis/words.py``; the build
   contract assigns ``core/levi/gtpm/words.py`` to the middle team —
   this file follows the contract.
4. Receipts carry ``"t"`` as a logical monotonic counter (``r000001``…)
   derived from receipt+warning counts, not wall-clock time: a clock
   read would be ambient I/O and break the determinism story.
5. Spec §4's ``Dictionary`` lacks history/warnings/receipts; they are
   present per the contract (``new_dictionary`` keys are exactly the
   contract's six).
6. Nested word calls resolve through ``by_name`` at run time (newest
   definition wins), matching the spec's "lookup is newest-first" rule.
   A word defined against an older definition therefore sees the newest
   one when it runs — documented, not silent.
7. A definition may name the word being defined (direct recursion):
   the token is checked against the word's own declared effect, so
   recursive words need no stub-then-shadow dance. Mutual recursion
   still goes through define-then-redefine.
"""

from __future__ import annotations

__all__ = [
    "WordError",
    "UndefinedWordError",
    "StackError",
    "EffectError",
    "PRIMITIVE_EFFECTS",
    "PRIMITIVE_GLOSS",
    "new_dictionary",
    "define",
    "execute",
    "replay",
    "gloss",
    "deprecate",
    "retire",
    "extend_vocabulary",
]

_RECURSION_LIMIT = 500  # well under CPython's own frame limit


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WordError(Exception):
    """Base fault for the dictionary. Never a guess, never a silent no-op."""


class UndefinedWordError(WordError):
    """Executing (or managing) a word that is not in the dictionary."""


class StackError(WordError):
    """Stack underflow — at define-time (static check) or at run-time."""


class EffectError(WordError):
    """A definition whose composed stack effect does not match its claim."""


# ---------------------------------------------------------------------------
# Primitives — the CLOSED set. Pure stack→stack functions, no I/O.
# Each takes the working stack list and mutates only that list.
# ---------------------------------------------------------------------------


def _underflow(name, need, have):
    return StackError(f"{name}: stack underflow (needs {need}, has {have})")


def _need(stack, n, name):
    if len(stack) < n:
        raise _underflow(name, n, len(stack))


def _num(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise WordError(f"{name}: expected a number, got {type(x).__name__}")
    return x


def _p_dup(s):  # (x -- x x)
    _need(s, 1, "dup")
    s.append(s[-1])


def _p_drop(s):  # (x --)
    _need(s, 1, "drop")
    s.pop()


def _p_swap(s):  # (a b -- b a)
    _need(s, 2, "swap")
    s[-1], s[-2] = s[-2], s[-1]


def _p_over(s):  # (a b -- a b a)
    _need(s, 2, "over")
    s.append(s[-2])


def _p_rot(s):  # (a b c -- b c a)
    _need(s, 3, "rot")
    s[-3], s[-2], s[-1] = s[-2], s[-1], s[-3]


def _p_depth(s):  # ( -- n)
    s.append(len(s))


def _p_add(s):  # (a b -- a+b)
    _need(s, 2, "add")
    b, a = s.pop(), s.pop()
    s.append(_num(a, "add") + _num(b, "add"))


def _p_sub(s):  # (a b -- a-b)
    _need(s, 2, "sub")
    b, a = s.pop(), s.pop()
    s.append(_num(a, "sub") - _num(b, "sub"))


def _p_mul(s):  # (a b -- a*b)
    _need(s, 2, "mul")
    b, a = s.pop(), s.pop()
    s.append(_num(a, "mul") * _num(b, "mul"))


def _p_divmod(s):  # (a b -- q r)
    _need(s, 2, "divmod")
    b, a = s.pop(), s.pop()
    a, b = _num(a, "divmod"), _num(b, "divmod")
    if b == 0:
        raise WordError("divmod: division by zero")
    q, r = divmod(a, b)
    s.append(q)
    s.append(r)


def _p_neg(s):  # (x -- -x)
    _need(s, 1, "neg")
    s.append(-_num(s.pop(), "neg"))


def _p_eq(s):  # (a b -- a==b)
    _need(s, 2, "eq")
    b, a = s.pop(), s.pop()
    s.append(a == b)


def _p_neq(s):  # (a b -- a!=b)
    _need(s, 2, "neq")
    b, a = s.pop(), s.pop()
    s.append(a != b)


def _cmp(name, op):
    def run(s):
        _need(s, 2, name)
        b, a = s.pop(), s.pop()
        a, b = _num(a, name), _num(b, name)
        s.append(op(a, b))

    run.__name__ = f"_p_{name}"
    return run


def _p_and(s):  # (a b -- a and b), booleans only
    _need(s, 2, "and")
    b, a = s.pop(), s.pop()
    if not isinstance(a, bool) or not isinstance(b, bool):
        raise WordError("and: expected booleans")
    s.append(a and b)


def _p_or(s):  # (a b -- a or b), booleans only
    _need(s, 2, "or")
    b, a = s.pop(), s.pop()
    if not isinstance(a, bool) or not isinstance(b, bool):
        raise WordError("or: expected booleans")
    s.append(a or b)


def _p_not(s):  # (a -- not a), boolean only
    _need(s, 1, "not")
    a = s.pop()
    if not isinstance(a, bool):
        raise WordError("not: expected a boolean")
    s.append(not a)


def _p_len(s):  # (x -- n)
    _need(s, 1, "len")
    x = s.pop()
    if not isinstance(x, (list, tuple, str, dict)):
        raise WordError(
            f"len: expected a list, tuple, string or dict, got {type(x).__name__}"
        )
    s.append(len(x))


def _p_cons(s):  # (x list -- list)
    _need(s, 2, "cons")
    lst, x = s.pop(), s.pop()
    if not isinstance(lst, list):
        raise WordError(f"cons: expected a list, got {type(lst).__name__}")
    s.append([x] + lst)


def _p_uncons(s):  # (list -- x rest)
    _need(s, 1, "uncons")
    lst = s.pop()
    if not isinstance(lst, list):
        raise WordError(f"uncons: expected a list, got {type(lst).__name__}")
    if not lst:
        raise WordError("uncons: empty list")
    s.append(lst[0])
    s.append(lst[1:])


def _p_append(s):  # (list x -- list)
    _need(s, 2, "append")
    x, lst = s.pop(), s.pop()
    if not isinstance(lst, list):
        raise WordError(f"append: expected a list, got {type(lst).__name__}")
    s.append(lst + [x])


def _p_get(s):  # (dict key -- value); missing key is fail-closed
    _need(s, 2, "get")
    key, dct = s.pop(), s.pop()
    if not isinstance(dct, dict):
        raise WordError(f"get: expected a dict, got {type(dct).__name__}")
    try:
        s.append(dct[key])
    except KeyError:
        raise WordError(f"get: missing key {key!r}") from None
    except TypeError:
        raise WordError(f"get: unhashable key {key!r}") from None


def _p_put(s):  # (dict key value -- dict); returns a NEW dict (pure)
    _need(s, 3, "put")
    value, key, dct = s.pop(), s.pop(), s.pop()
    if not isinstance(dct, dict):
        raise WordError(f"put: expected a dict, got {type(dct).__name__}")
    try:
        new = dict(dct)
        new[key] = value
    except TypeError:
        raise WordError(f"put: unhashable key {key!r}") from None
    s.append(new)


def _p_del(s):  # (dict key -- dict); missing key is fail-closed
    _need(s, 2, "del")
    key, dct = s.pop(), s.pop()
    if not isinstance(dct, dict):
        raise WordError(f"del: expected a dict, got {type(dct).__name__}")
    try:
        new = dict(dct)
        del new[key]
    except KeyError:
        raise WordError(f"del: missing key {key!r}") from None
    except TypeError:
        raise WordError(f"del: unhashable key {key!r}") from None
    s.append(new)


def _p_keys(s):  # (dict -- [keys])
    _need(s, 1, "keys")
    dct = s.pop()
    if not isinstance(dct, dict):
        raise WordError(f"keys: expected a dict, got {type(dct).__name__}")
    s.append(list(dct.keys()))


_PRIMITIVES = {
    "dup": _p_dup,
    "drop": _p_drop,
    "swap": _p_swap,
    "over": _p_over,
    "rot": _p_rot,
    "depth": _p_depth,
    "add": _p_add,
    "sub": _p_sub,
    "mul": _p_mul,
    "divmod": _p_divmod,
    "neg": _p_neg,
    "eq": _p_eq,
    "neq": _p_neq,
    "gt": _cmp("gt", lambda a, b: a > b),
    "lt": _cmp("lt", lambda a, b: a < b),
    "gte": _cmp("gte", lambda a, b: a >= b),
    "lte": _cmp("lte", lambda a, b: a <= b),
    "and": _p_and,
    "or": _p_or,
    "not": _p_not,
    "len": _p_len,
    "cons": _p_cons,
    "uncons": _p_uncons,
    "append": _p_append,
    "get": _p_get,
    "put": _p_put,
    "del": _p_del,
    "keys": _p_keys,
}

#: Declared stack effects of the closed primitive set: name → (n_in, n_out).
PRIMITIVE_EFFECTS = {
    "dup": (1, 2),
    "drop": (1, 0),
    "swap": (2, 2),
    "over": (2, 3),
    "rot": (3, 3),
    "depth": (0, 1),
    "add": (2, 1),
    "sub": (2, 1),
    "mul": (2, 1),
    "divmod": (2, 2),
    "neg": (1, 1),
    "eq": (2, 1),
    "neq": (2, 1),
    "gt": (2, 1),
    "lt": (2, 1),
    "gte": (2, 1),
    "lte": (2, 1),
    "and": (2, 1),
    "or": (2, 1),
    "not": (1, 1),
    "len": (1, 1),
    "cons": (2, 1),
    "uncons": (1, 2),
    "append": (2, 1),
    "get": (2, 1),
    "put": (3, 1),
    "del": (2, 1),
    "keys": (1, 1),
}

#: Plain-language gloss for each primitive — the receipt's raw material.
PRIMITIVE_GLOSS = {
    "dup": "duplicate the top item",
    "drop": "discard the top item",
    "swap": "swap the top two items",
    "over": "copy the second item to the top",
    "rot": "rotate the top three items",
    "depth": "push the current stack depth",
    "add": "add the top two numbers",
    "sub": "subtract the top number from the second",
    "mul": "multiply the top two numbers",
    "divmod": "divide the second number by the top, pushing quotient then remainder",
    "neg": "negate the top number",
    "eq": "push whether the top two items are equal",
    "neq": "push whether the top two items differ",
    "gt": "push whether the second number exceeds the top",
    "lt": "push whether the second number is below the top",
    "gte": "push whether the second number is at least the top",
    "lte": "push whether the second number is at most the top",
    "and": "push the logical and of the top two booleans",
    "or": "push the logical or of the top two booleans",
    "not": "push the negation of the top boolean",
    "len": "push the length of the top list, string, or dict",
    "cons": "prepend the second item onto the top list",
    "uncons": "split the top list into its head and tail",
    "append": "append the top item onto the second list",
    "get": "push the value for the top key in the second dict",
    "put": "return a new dict with the key set to the value",
    "del": "return a new dict with the key removed",
    "keys": "push the list of keys of the top dict",
}


# ---------------------------------------------------------------------------
# Dictionary
# ---------------------------------------------------------------------------


def new_dictionary():
    """Return a fresh, empty dictionary."""
    return {
        "words": [],
        "by_name": {},
        "history": {},
        "version": 1,
        "warnings": [],
        "receipts": [],
    }


def _check_dict(d):
    for key in ("words", "by_name", "history", "version", "warnings", "receipts"):
        if key not in d:
            raise WordError(f"not a dictionary: missing {key!r}")


def _stamp(d):
    """Logical timestamp: unique, monotonic, no clock reads."""
    n = len(d["receipts"]) + len(d["warnings"]) + 1
    return f"r{n:06d}"


def _as_literal(token):
    """Token → literal value: int, then float, then [] / {}, else the string."""
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if token == "[]":
        return []
    if token == "{}":
        return {}
    return token


def _literal_gloss(value):
    if isinstance(value, bool):
        return f"push the boolean {value}"
    if isinstance(value, (int, float)):
        return f"push the number {value!r}"
    if isinstance(value, list):
        return "push an empty list"
    if isinstance(value, dict):
        return "push an empty dict"
    return f"push the text {value!r}"


def _classify(d, token):
    """Token → ("primitive", name) | ("word", name) | ("literal", value)."""
    if token in _PRIMITIVES:
        return ("primitive", token)
    if token in d["by_name"]:
        return ("word", token)
    return ("literal", _as_literal(token))


def _token_effect(d, kind, payload, self_effect=None):
    if kind == "primitive":
        return PRIMITIVE_EFFECTS[payload]
    if kind == "self":
        return self_effect
    if kind == "word":
        se = d["by_name"][payload]["stack_effect"]
        return (int(se[0]), int(se[1]))
    return (0, 1)  # a literal pushes one value


def _build_gloss(d, name, resolved):
    parts = []
    for kind, payload in resolved:
        if kind == "primitive":
            parts.append(PRIMITIVE_GLOSS[payload])
        elif kind == "self":
            parts.append(f"recurse into {payload}")
        elif kind == "word":
            parts.append(d["by_name"][payload]["gloss"])
        else:
            parts.append(_literal_gloss(payload))
    if not parts:
        return f"{name}: does nothing"
    return f"{name}: " + " then ".join(parts)


def define(d, name, definition, stack_effect):
    """Define a word; fail-closed on unbalanced definitions.

    ``stack_effect`` is ``(n_in, n_out)`` as decimal strings.
    Returns a DefineReceipt dict; also records it in ``d["receipts"]``.
    """
    _check_dict(d)
    if not isinstance(name, str) or not name:
        raise WordError(f"word name must be a non-empty string, got {name!r}")
    if name in _PRIMITIVES:
        raise WordError(f"cannot define {name!r}: the primitive set is closed")
    try:
        n_in = int(stack_effect[0])
        n_out = int(stack_effect[1])
    except (TypeError, IndexError, ValueError):
        raise WordError(
            f"define {name!r}: stack_effect must be (n_in, n_out) as "
            f"decimal strings, got {stack_effect!r}"
        ) from None
    if n_in < 0 or n_out < 0:
        raise WordError(f"define {name!r}: negative stack effect")
    definition = list(definition)

    resolved = []
    depth = n_in
    for token in definition:
        if not isinstance(token, str):
            raise WordError(
                f"define {name!r}: definition tokens must be strings, got {token!r}"
            )
        if token == name:
            # direct self-reference: recursion against the declared effect
            kind, payload = "self", name
            ein, eout = n_in, n_out
        else:
            kind, payload = _classify(d, token)
            if kind == "word":
                w = d["by_name"][payload]
                if w["status"] == "retired":
                    raise WordError(
                        f"define {name!r}: cannot build on retired word {payload!r}"
                    )
                if w["status"] == "deprecated":
                    d["warnings"].append(
                        {
                            "kind": "warning",
                            "word": name,
                            "note": f"new definition uses deprecated word {payload!r}",
                            "t": _stamp(d),
                        }
                    )
            ein, eout = _token_effect(d, kind, payload, (n_in, n_out))
        depth += eout - ein
        if depth < 0:
            raise StackError(f"define {name!r}: stack underflow at token {token!r}")
        resolved.append((kind, payload))
    if depth != n_out:
        raise EffectError(
            f"define {name!r}: declared effect ({n_in} -- {n_out}) but the "
            f"definition leaves depth {depth}"
        )

    gloss_text = _build_gloss(d, name, resolved)
    t = _stamp(d)
    old = d["by_name"].get(name)
    shadowed = old is not None
    if shadowed:
        d["history"].setdefault(name, []).append(old)
    word = {
        "name": name,
        "definition": list(definition),
        "stack_effect": (str(n_in), str(n_out)),
        "gloss": gloss_text,
        "provenance": [],
        "status": "active",
        "born_at": t,
        "fired_count": 0,
    }
    d["words"].append(word)
    d["by_name"][name] = word
    receipt = {
        "kind": "define",
        "word": name,
        "definition": list(definition),
        "stack_check": True,
        "gloss": gloss_text,
        "t": t,
        "shadowed": shadowed,
    }
    d["receipts"].append(receipt)
    return receipt


def _run_word(d, word, stack, depth):
    if depth > _RECURSION_LIMIT:
        raise WordError(
            f"recursion limit ({_RECURSION_LIMIT}) exceeded in {word['name']!r}"
        )
    if word["status"] == "retired":
        raise WordError(f"word {word['name']!r} is retired and cannot execute")
    if word["status"] == "deprecated":
        d["warnings"].append(
            {
                "kind": "warning",
                "word": word["name"],
                "note": "use of deprecated word",
                "t": _stamp(d),
            }
        )
    for token in word["definition"]:
        if token in _PRIMITIVES:
            _PRIMITIVES[token](stack)
        else:
            inner = d["by_name"].get(token)
            if inner is not None:
                _run_word(d, inner, stack, depth + 1)
            else:
                stack.append(_as_literal(token))
    word["fired_count"] += 1
    return stack


def execute(d, name, stack):
    """Run a word on a COPY of ``stack``; return the resulting stack.

    The input stack is never mutated. Undefined or retired words raise
    WordError (fail-closed); deprecated words run and log a warning.
    """
    _check_dict(d)
    word = d["by_name"].get(name)
    if word is None:
        raise UndefinedWordError(f"undefined word: {name!r}")
    try:
        return _run_word(d, word, list(stack), 0)
    except RecursionError:
        # belt and suspenders behind the explicit depth guard above
        raise WordError(
            f"recursion limit ({_RECURSION_LIMIT}) exceeded in {name!r}"
        ) from None


def replay(d, name, inputs):
    """Deterministic replay: ``execute`` with ``inputs`` as the stack."""
    return execute(d, name, list(inputs))


def gloss(d, name):
    """Return the word's plain-language gloss, regenerated from its tokens."""
    _check_dict(d)
    word = d["by_name"].get(name)
    if word is None:
        raise UndefinedWordError(f"undefined word: {name!r}")
    resolved = [_classify(d, token) for token in word["definition"]]
    return _build_gloss(d, name, resolved)


def deprecate(d, name):
    """Mark a word deprecated: it keeps working, but uses warn.

    Returns a receipt dict.
    """
    _check_dict(d)
    word = d["by_name"].get(name)
    if word is None:
        raise UndefinedWordError(f"undefined word: {name!r}")
    if word["status"] == "retired":
        raise WordError(f"cannot deprecate retired word {name!r}")
    word["status"] = "deprecated"
    receipt = {
        "kind": "deprecate",
        "word": name,
        "status": "deprecated",
        "t": _stamp(d),
    }
    d["receipts"].append(receipt)
    return receipt


def retire(d, name, migration):
    """Retire a word: it can no longer execute. Requires a migration note.

    Returns a receipt dict.
    """
    _check_dict(d)
    if not isinstance(migration, str) or not migration.strip():
        raise ValueError("retire requires a non-empty migration note")
    word = d["by_name"].get(name)
    if word is None:
        raise UndefinedWordError(f"undefined word: {name!r}")
    word["status"] = "retired"
    receipt = {"kind": "retire", "word": name, "migration": migration, "t": _stamp(d)}
    d["receipts"].append(receipt)
    return receipt


def extend_vocabulary(d, word_defs):
    """Batch-define words (the end-team hook); returns one receipt per word.

    Each entry is ``(name, definition, stack_effect)`` or
    ``{"name": ..., "definition": ..., "stack_effect": ...}``.
    Fail-closed: the first invalid entry raises; earlier receipts stand.
    """
    _check_dict(d)
    receipts = []
    for entry in word_defs:
        if isinstance(entry, dict):
            name, definition, se = (
                entry["name"],
                entry["definition"],
                entry["stack_effect"],
            )
        else:
            name, definition, se = entry
        receipts.append(define(d, name, definition, se))
    return receipts
