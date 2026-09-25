"""A tiny concatenative two-stack word language.

Studied from: languages-hunt-20260915, report.md [S1, LOAD-BEARING].

Inspired by the *shape* of Forth: a data stack plus a return stack, where
every program is a sequence of named words and the programmer extends the
language itself by defining new words with ``: name ... ;``. This is an
original, from-scratch implementation for LEVI — no Forth code is used.

The compiler is just the dictionary: ``define(name, body)`` compiles a new
word from tokens, and ``: ... ;`` definitions can use the same immediate
words the interpreter runs. Branching (``if/else/then``) is handled by
backpatching jump targets at compile time; counted loops
(``do ... loop``) ride on the return stack, with ``i`` and ``j`` exposing
the loop indices.

Honest limits: integers only (no floats), fixed small builtin set, no
interactive debugger, no vocabulary scoping, no string variables —
``." text"`` prints immediately instead. Errors are raised as
:class:`WordError` subclasses rather than crashing silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Union

ORIGIN = "levi-revival/forth"

Token = Union[int, str, tuple]


class WordError(Exception):
    """Base class for word-language failures."""


class StackUnderflow(WordError):
    """A word needed more items than the data stack held."""


class UnknownWord(WordError):
    """No word is defined under that name."""


class CompileError(WordError):
    """A colon definition was malformed (e.g. unbalanced ``if``)."""


@dataclass
class Machine:
    """A two-stack concatenative machine.

    ``data`` is the parameter stack, ``ret`` is the return stack (used by
    ``do...loop`` and word-call frames). ``output`` collects everything
    printed by ``.``, ``."``, ``cr`` and ``space`` so programs are testable
    without a terminal.
    """

    data: List[int] = field(default_factory=list)
    ret: List[int] = field(default_factory=list)
    dictionary: Dict[str, Union[Callable, List[Token]]] = field(default_factory=dict)
    output: List[str] = field(default_factory=list)

    # -- stack helpers ----------------------------------------------------
    def push(self, value: int) -> None:
        self.data.append(value)

    def pop(self) -> int:
        if not self.data:
            raise StackUnderflow("data stack underflow")
        return self.data.pop()

    def peek(self, depth: int = 0) -> int:
        if len(self.data) <= depth:
            raise StackUnderflow("data stack underflow")
        return self.data[-1 - depth]


def _truth(value: int) -> int:
    return -1 if value else 0  # classic all-bits-set true


def _binop(machine: Machine, fn: Callable[[int, int], int]) -> None:
    b, a = machine.pop(), machine.pop()
    machine.push(fn(a, b))


def _install_builtins(machine: Machine) -> None:
    d = machine.dictionary

    # -- stack shuffling --------------------------------------------------
    def dup(m: Machine) -> None:
        m.push(m.peek())

    def drop(m: Machine) -> None:
        m.pop()

    def swap(m: Machine) -> None:
        b, a = m.pop(), m.pop()
        m.push(b)
        m.push(a)

    def over(m: Machine) -> None:
        m.push(m.peek(1))

    def rot(m: Machine) -> None:
        c, b, a = m.pop(), m.pop(), m.pop()
        m.push(b)
        m.push(c)
        m.push(a)

    def depth(m: Machine) -> None:
        m.push(len(m.data))

    def clear(m: Machine) -> None:
        m.data.clear()

    d.update(
        {
            "dup": dup,
            "drop": drop,
            "swap": swap,
            "over": over,
            "rot": rot,
            "depth": depth,
            "clear": clear,
        }
    )

    # -- arithmetic --------------------------------------------------------
    d["+"] = lambda m: _binop(m, lambda a, b: a + b)
    d["-"] = lambda m: _binop(m, lambda a, b: a - b)
    d["*"] = lambda m: _binop(m, lambda a, b: a * b)

    def slash_mod(m: Machine) -> None:
        b, a = m.pop(), m.pop()
        if b == 0:
            raise WordError("division by zero")
        m.push(a // b)
        m.push(a % b)

    d["/mod"] = slash_mod
    d["mod"] = lambda m: _binop(m, lambda a, b: a % b)
    d["negate"] = lambda m: m.push(-m.pop())
    d["abs"] = lambda m: m.push(abs(m.pop()))
    d["min"] = lambda m: _binop(m, min)
    d["max"] = lambda m: _binop(m, max)

    # -- comparison / logic ------------------------------------------------
    d["="] = lambda m: _binop(m, lambda a, b: _truth(a == b))
    d["<"] = lambda m: _binop(m, lambda a, b: _truth(a < b))
    d[">"] = lambda m: _binop(m, lambda a, b: _truth(a > b))
    d["0="] = lambda m: m.push(_truth(m.pop() == 0))
    d["0<"] = lambda m: m.push(_truth(m.pop() < 0))
    d["and"] = lambda m: _binop(m, lambda a, b: a & b)
    d["or"] = lambda m: _binop(m, lambda a, b: a | b)
    d["xor"] = lambda m: _binop(m, lambda a, b: a ^ b)
    d["invert"] = lambda m: m.push(~m.pop())

    # -- output -------------------------------------------------------------
    def dot(m: Machine) -> None:
        m.output.append(str(m.pop()) + " ")

    def dots(m: Machine) -> None:
        m.output.append(
            "<" + str(len(m.data)) + "> " + " ".join(str(x) for x in m.data) + " "
        )

    d["."] = dot
    d[".s"] = dots
    d["cr"] = lambda m: m.output.append("\n")
    d["space"] = lambda m: m.output.append(" ")
    d["emit"] = lambda m: m.output.append(chr(m.pop()))

    # -- return-stack words -------------------------------------------------
    def to_r(m: Machine) -> None:
        m.ret.append(m.pop())

    def r_from(m: Machine) -> None:
        if not m.ret:
            raise StackUnderflow("return stack underflow")
        m.push(m.ret.pop())

    def r_fetch(m: Machine) -> None:
        if not m.ret:
            raise StackUnderflow("return stack underflow")
        m.push(m.ret[-1])

    d[">r"] = to_r
    d["r>"] = r_from
    d["r@"] = r_fetch

    def i_word(m: Machine) -> None:
        if len(m.ret) < 2:
            raise StackUnderflow("no active do-loop for i")
        m.push(m.ret[-2])

    def j_word(m: Machine) -> None:
        if len(m.ret) < 4:
            raise StackUnderflow("no outer do-loop for j")
        m.push(m.ret[-4])

    d["i"] = i_word
    d["j"] = j_word


def new_machine() -> Machine:
    """Create a machine with the builtin word set installed."""
    machine = Machine()
    _install_builtins(machine)
    return machine


# ---------------------------------------------------------------------------
# Tokenizer / compiler
# ---------------------------------------------------------------------------


def tokenize(source: str) -> List[Token]:
    """Split source into tokens: ints, ``."..."`` strings, or word names.

    ``( comment )`` parenthesised comments are skipped.
    """
    tokens: List[Token] = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            end = source.find(")", i)
            if end == -1:
                raise CompileError("unterminated ( comment")
            i = end + 1
            continue
        if source.startswith('."', i):
            end = source.find('"', i + 2)
            if end == -1:
                raise CompileError('unterminated ." string')
            tokens.append((".str", source[i + 2 : end]))
            i = end + 1
            continue
        j = i
        while j < n and not source[j].isspace():
            j += 1
        word = source[i:j]
        try:
            tokens.append(int(word))
        except ValueError:
            tokens.append(word.lower())
        i = j
    return tokens


def compile_body(tokens: List[Token]) -> List[Token]:
    """Resolve ``if/else/then`` into backpatched branch instructions.

    Emits ``("?branch", target)`` and ``("branch", target)`` tuples with
    targets filled in once ``then`` is seen. Unbalanced structures raise
    :class:`CompileError`.
    """
    out: List[Token] = []
    pending: List[int] = []  # indices of ?branch awaiting else/then
    for tok in tokens:
        if tok == "if":
            pending.append(len(out))
            out.append(("?branch", None))
        elif tok == "else":
            if not pending:
                raise CompileError("else without if")
            q = pending.pop()
            out[q] = ("?branch", len(out) + 1)
            pending.append(len(out))
            out.append(("branch", None))
        elif tok == "then":
            if not pending:
                raise CompileError("then without if")
            q = pending.pop()
            out[q] = (out[q][0], len(out))
        else:
            out.append(tok)
    if pending:
        raise CompileError("if without then")
    return _mark_loops(out)


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


def _execute_tokens(machine: Machine, code: List[Token]) -> None:
    pc = 0
    while pc < len(code):
        tok = code[pc]
        if isinstance(tok, int):
            machine.push(tok)
            pc += 1
        elif isinstance(tok, tuple):
            kind = tok[0]
            if kind == ".str":
                machine.output.append(tok[1])
                pc += 1
            elif kind == "?branch":
                pc = tok[1] if machine.pop() == 0 else pc + 1
            elif kind == "branch":
                pc = tok[1]
            elif kind == "do":
                start, limit = machine.pop(), machine.pop()
                machine.ret.extend((start, limit))
                pc += 1
            elif kind == "loop":
                if len(machine.ret) < 2:
                    raise StackUnderflow("loop without do")
                limit = machine.ret.pop()
                index = machine.ret.pop() + 1
                if index < limit:
                    machine.ret.extend((index, limit))
                    pc = tok[1]  # jump back to first token after do
                else:
                    pc += 1
            else:
                raise WordError(f"bad compiled token {tok!r}")
        else:  # word name
            entry = machine.dictionary.get(tok)
            if entry is None:
                raise UnknownWord(f"unknown word: {tok}")
            if callable(entry):
                entry(machine)
                pc += 1
            else:
                _execute_tokens(machine, entry)  # nested colon word
                pc += 1


def _compile_definition(machine: Machine, tokens: List[Token], pos: int) -> int:
    name = tokens[pos]
    if not isinstance(name, str):
        raise CompileError("word name must be a name, not a number")
    body: List[Token] = []
    pos += 1
    while pos < len(tokens) and tokens[pos] != ";":
        body.append(tokens[pos])
        pos += 1
    if pos >= len(tokens):
        raise CompileError(f"definition of {name} missing ;")
    machine.dictionary[name] = compile_body(body)
    return pos + 1


def _mark_loops(code: List[Token]) -> List[Token]:
    """Turn ``do``/``loop`` words into loop markers with back-edge targets."""
    out: List[Token] = []
    do_stack: List[int] = []
    for tok in code:
        if tok == "do":
            do_stack.append(len(out))
            out.append(("do", None))
        elif tok == "loop":
            if not do_stack:
                raise CompileError("loop without do")
            start = do_stack.pop()
            out.append(("loop", start + 1))
        else:
            out.append(tok)
    if do_stack:
        raise CompileError("do without loop")
    return out


def run(machine: Machine, source: str) -> Machine:
    """Interpret ``source`` on ``machine``; returns the machine.

    ``:`` definitions are compiled as they are encountered; everything
    else executes immediately. Printed text accumulates in
    ``machine.output``; ``"".join(machine.output)`` is the program text.
    """
    tokens = tokenize(source)
    main: List[Token] = []
    pos = 0
    while pos < len(tokens):
        if tokens[pos] == ":":
            pos = _compile_definition(machine, tokens, pos + 1)
        elif tokens[pos] == ";":
            raise CompileError("stray ; outside a word definition")
        else:
            main.append(tokens[pos])
            pos += 1
    _execute_tokens(machine, _mark_loops(compile_body(main)))
    return machine


def evaluate(source: str) -> str:
    """Run ``source`` on a fresh machine and return its printed output."""
    machine = new_machine()
    run(machine, source)
    return "".join(machine.output)
