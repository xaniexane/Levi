"""concatenative: Stackscript — LEVI's own bounded stack machine.

REMIX DELTA: Forth (1970, Charles H. Moore) proved a whole interactive
programming system can fit in kilobytes: two stacks, composable words,
live development on the smallest hardware. What killed Forth in the
mainstream was the "write-only" failure mode — total malleability let
undisciplined code rot silently. Stackscript takes the concatenative
core and makes the discipline structural instead of advisory:

- bounded execution: max steps and max stack depth, deny-closed —
  overflow raises, never wraps, never hangs;
- every run returns a receipt (steps used, peak depth, words called);
- pure compute: no file/network/process words exist, so a recipe can
  never reach outside the machine. Automation recipes built on top get
  their side effects from LEVI's permissioned primitives, never from
  the script itself.

Clean-room design from first principles (no Forth source read or
copied). stdlib-only.

Grammar:
    <int> | <float> | "string"      push literals
    : name ... ;                    define a word (body = token list)
    <word>                          call a builtin or defined word

Builtins (stack effects in parens):
    + - * / mod neg abs ( a b -- c )
    dup drop swap over rot nip ( stack shuffling )
    = <> < > <= >= ( a b -- flag )
    and or not ( flags )
    depth ( -- n )  .s ( -- ) debug print of stack
    if ... else ... then   ( flag -- ) immediate branching
    begin ... flag until   ( -- ) post-test loop
    times                  ( n quot -- ) run quotation n times

Quotations: [ ... ] pushes a token list; `call` executes it.
`times` consumes a count and a quotation.

Example:
    stack, receipt = run(": sq dup * ; 5 sq")   # stack == [25]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple


class StackError(Exception):
    """Deny-closed execution failure: underflow, overflow, step limit,
    unknown word, or malformed program. Never raised as a crash."""


# ---------------------------------------------------------------------------
# tokenizer
# ---------------------------------------------------------------------------


def tokenize(source: str) -> List[Any]:
    """Split source into tokens: numbers become numbers, quoted text
    becomes strings, everything else stays a word name."""
    tokens: List[Any] = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            j = source.find('"', i + 1)
            if j == -1:
                raise StackError("unterminated string literal")
            tokens.append(("lit", source[i + 1 : j]))
            i = j + 1
            continue
        if ch == "[":
            depth, j = 1, i + 1
            while j < n and depth:
                if source[j] == "[":
                    depth += 1
                elif source[j] == "]":
                    depth -= 1
                j += 1
            if depth:
                raise StackError("unterminated quotation")
            tokens.append(("quot", tokenize(source[i + 1 : j - 1])))
            i = j
            continue
        j = i
        while j < n and not source[j].isspace() and source[j] not in '"[]':
            j += 1
        word = source[i:j]
        tokens.append(_number(word) if _number(word) is not None else word)
        i = j
    return tokens


def _number(word: str):
    try:
        return int(word)
    except ValueError:
        pass
    try:
        return float(word)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# machine
# ---------------------------------------------------------------------------


@dataclass
class Receipt:
    steps: int = 0
    max_depth: int = 0
    words_defined: List[str] = field(default_factory=list)
    words_called: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "max_depth": self.max_depth,
            "words_defined": list(self.words_defined),
            "words_called": dict(self.words_called),
        }


class StackMachine:
    def __init__(self, max_steps: int = 10_000, max_depth: int = 256):
        if max_steps <= 0 or max_depth <= 0:
            raise ValueError("bounds must be positive")
        self.max_steps = max_steps
        self.max_depth = max_depth
        self.stack: List[Any] = []
        self.dictionary: Dict[str, List[Any]] = {}
        self.receipt = Receipt()
        self._builtins: Dict[str, Callable[[], None]] = {}
        self._install_builtins()

    # -- stack helpers ----------------------------------------------------
    def _push(self, value: Any) -> None:
        if len(self.stack) >= self.max_depth:
            raise StackError("stack depth limit (%d) exceeded" % self.max_depth)
        self.stack.append(value)
        if len(self.stack) > self.receipt.max_depth:
            self.receipt.max_depth = len(self.stack)

    def _pop(self) -> Any:
        if not self.stack:
            raise StackError("stack underflow")
        return self.stack.pop()

    # -- execution --------------------------------------------------------
    def execute(self, tokens: List[Any]) -> List[Any]:
        self._run_tokens(tokens)
        return list(self.stack)

    def _run_tokens(self, tokens: List[Any]) -> None:
        ip = 0
        while ip < len(tokens):
            self._tick()
            tok = tokens[ip]
            ip = self._step(tok, tokens, ip)

    def _tick(self) -> None:
        self.receipt.steps += 1
        if self.receipt.steps > self.max_steps:
            raise StackError("step limit (%d) exceeded" % self.max_steps)

    def _step(self, tok: Any, tokens: List[Any], ip: int) -> int:
        if isinstance(tok, (int, float)):
            self._push(tok)
            return ip + 1
        if isinstance(tok, tuple):
            kind, value = tok
            if kind == "lit":
                self._push(value)
            else:  # quot
                self._push(value)
            return ip + 1
        # word
        if tok in self._builtins:
            self._builtins[tok]()
            self._count(tok)
            return ip + 1
        if tok in self.dictionary:
            self._count(tok)
            self._run_tokens(self.dictionary[tok])
            return ip + 1
        if tok == ":":
            return self._define(tokens, ip)
        if tok == "if":
            return self._branch(tokens, ip)
        if tok == "begin":
            return self._loop(tokens, ip)
        raise StackError("unknown word: %r" % (tok,))

    def _count(self, word: str) -> None:
        self.receipt.words_called[word] = self.receipt.words_called.get(word, 0) + 1

    # -- definitions ------------------------------------------------------
    def _define(self, tokens: List[Any], ip: int) -> int:
        try:
            end = tokens.index(";", ip)
        except ValueError:
            raise StackError("':' without matching ';'") from None
        if ip + 1 >= end:
            raise StackError("':' with no word name")
        name = tokens[ip + 1]
        if not isinstance(name, str):
            raise StackError("word name must be a word, got %r" % (name,))
        if name in self._builtins:
            raise StackError("cannot redefine builtin %r" % (name,))
        self.dictionary[name] = tokens[ip + 2 : end]
        if name not in self.receipt.words_defined:
            self.receipt.words_defined.append(name)
        return end + 1

    # -- control flow -----------------------------------------------------
    @staticmethod
    def _match(
        tokens: List[Any], start: int, openers: Tuple[str, ...], closer: str
    ) -> int:
        depth = 0
        for i in range(start, len(tokens)):
            t = tokens[i]
            if t in openers:
                depth += 1
            elif t == closer:
                if depth == 0:
                    return i
                depth -= 1
        raise StackError("no matching %r" % (closer,))

    def _branch(self, tokens: List[Any], ip: int) -> int:
        flag = self._pop()
        else_at = then_at = None
        depth = 0
        i = ip + 1
        while i < len(tokens):
            t = tokens[i]
            if t == "if":
                depth += 1
            elif t == "then":
                if depth == 0:
                    then_at = i
                    break
                depth -= 1
            elif t == "else" and depth == 0:
                else_at = i
            i += 1
        if then_at is None:
            raise StackError("'if' without matching 'then'")
        if flag:
            self._run_tokens(
                tokens[ip + 1 : else_at if else_at is not None else then_at]
            )
        elif else_at is not None:
            self._run_tokens(tokens[else_at + 1 : then_at])
        return then_at + 1

    def _loop(self, tokens: List[Any], ip: int) -> int:
        until_at = self._match(tokens, ip + 1, ("begin",), "until")
        body = tokens[ip + 1 : until_at]
        while True:
            self._run_tokens(body)
            flag = self._pop()
            if flag:
                break
        return until_at + 1

    # -- builtins ---------------------------------------------------------
    def _install_builtins(self) -> None:
        m = self._builtins
        b2 = lambda f: self._binary(f)  # noqa: E731
        m["+"] = b2(lambda a, b: a + b)
        m["-"] = b2(lambda a, b: a - b)
        m["*"] = b2(lambda a, b: a * b)
        m["/"] = b2(lambda a, b: a / b if b != 0 else self._div0())
        m["mod"] = b2(lambda a, b: a % b if b != 0 else self._div0())
        m["="] = b2(lambda a, b: 1 if a == b else 0)
        m["<>"] = b2(lambda a, b: 1 if a != b else 0)
        m["<"] = b2(lambda a, b: 1 if a < b else 0)
        m[">"] = b2(lambda a, b: 1 if a > b else 0)
        m["<="] = b2(lambda a, b: 1 if a <= b else 0)
        m[">="] = b2(lambda a, b: 1 if a >= b else 0)
        m["and"] = b2(lambda a, b: 1 if (a and b) else 0)
        m["or"] = b2(lambda a, b: 1 if (a or b) else 0)
        m["min"] = b2(lambda a, b: a if a < b else b)
        m["max"] = b2(lambda a, b: a if a > b else b)
        m["dup"] = lambda: self._push(self.stack[-1] if self.stack else self._pop())
        m["drop"] = lambda: self._pop()
        m["swap"] = self._swap
        m["over"] = self._over
        m["rot"] = self._rot
        m["nip"] = self._nip
        m["neg"] = lambda: self._push(-self._pop())
        m["abs"] = lambda: self._push(abs(self._pop()))
        m["not"] = lambda: self._push(0 if self._pop() else 1)
        m["depth"] = lambda: self._push(len(self.stack))
        m["call"] = self._call
        m["times"] = self._times
        m[".s"] = self._debug_print

    def _div0(self):
        raise StackError("division by zero")

    def _binary(self, f: Callable[[Any, Any], Any]) -> Callable[[], None]:
        def run() -> None:
            b = self._pop()
            a = self._pop()
            if isinstance(a, bool) or isinstance(b, bool):
                raise StackError("boolean on arithmetic stack")
            try:
                self._push(f(a, b))
            except TypeError:
                raise StackError("type mismatch for arithmetic") from None

        return run

    def _swap(self) -> None:
        b = self._pop()
        a = self._pop()
        self._push(b)
        self._push(a)

    def _over(self) -> None:
        if len(self.stack) < 2:
            raise StackError("stack underflow")
        self._push(self.stack[-2])

    def _rot(self) -> None:
        if len(self.stack) < 3:
            raise StackError("stack underflow")
        c = self.stack.pop()
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.extend([b, c, a])
        if len(self.stack) > self.receipt.max_depth:
            self.receipt.max_depth = len(self.stack)

    def _nip(self) -> None:
        b = self._pop()
        self._pop()
        self._push(b)

    def _call(self) -> None:
        quot = self._pop()
        if not (isinstance(quot, list)):
            raise StackError("call expects a quotation [ ... ]")
        self._run_tokens(quot)

    def _times(self) -> None:
        quot = self._pop()
        count = self._pop()
        if not isinstance(quot, list):
            raise StackError("times expects a quotation [ ... ]")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise StackError("times expects a non-negative integer count")
        for _ in range(count):
            self._run_tokens(quot)

    def _debug_print(self) -> None:
        print("<%d> %s" % (len(self.stack), " ".join(map(str, self.stack))))


def run(
    source: str, max_steps: int = 10_000, max_depth: int = 256
) -> Tuple[List[Any], Receipt]:
    """Run Stackscript source. Returns (final_stack, receipt).

    Raises StackError on any violation — the machine never half-runs.
    """
    machine = StackMachine(max_steps=max_steps, max_depth=max_depth)
    machine.execute(tokenize(source))
    return machine.stack, machine.receipt
