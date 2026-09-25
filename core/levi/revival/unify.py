"""LEVI's tiny logic engine: Warren's lesson as runnable code.

Studied from: ai-si (§1.11) — Warren's lesson (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a logic program is just terms, and
answering a query is just *unification* plus disciplined backtracking.
This module is a real, runnable Prolog subset:

- **terms**: atoms, numbers, variables, compound terms;
- **unification** with the occurs-check (``X = f(X)`` fails, honestly);
- **choice points + trail**: backtracking is reified — every binding is
  logged on a trail, every untried clause is an explicit choice point,
  and failure unwinds the trail to the mark;
- **first-argument indexing**: clause lookup dispatches on the
  (functor, arity, ground-first-argument) discriminator — it never scans
  the whole clause store when the goal's first argument is ground;
- a small query language: ``tell`` facts/rules, ``query`` goals.

Honesty: LOAD-BEARING, with stated limits. This is a teaching-scale
engine — no cut, no negation-as-failure, no lists, no arithmetic, depth-
first with no occurs-check-free shortcuts. It will loop on left-recursive
rules exactly like the real thing does.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Tuple

ORIGIN = "levi-revival/unify"


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


class V:
    """A logic variable. Identity matters — freshening makes new ones."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"V({self.name})"


class T:
    """A compound term: functor applied to argument terms."""

    __slots__ = ("functor", "args")

    def __init__(self, functor: str, args: List[Any]) -> None:
        self.functor = functor
        self.args = args

    def __repr__(self) -> str:
        return f"{self.functor}({', '.join(map(repr, self.args))})"


Atom = str  # atoms are plain strings; numbers are int/float


def term_str(t: Any) -> str:
    if isinstance(t, V):
        return t.name
    if isinstance(t, T):
        return f"{t.functor}({', '.join(term_str(a) for a in t.args)})"
    if isinstance(t, str):  # atoms print bare, not repr-quoted
        return t
    return repr(t)


# ---------------------------------------------------------------------------
# Parser — facts, rules, queries
# ---------------------------------------------------------------------------

_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<var>[A-Z_][A-Za-z0-9_]*)"
    r"|(?P<num>\d+(?:\.\d+)?)"
    r"|(?P<atom>[a-z][A-Za-z0-9_]*)"
    r"|(?P<query>\?-)"
    r"|(?P<op>:-|[(),.])"
    r")"
)


class _Parser:
    def __init__(self, text: str) -> None:
        # m.group() includes the leading \s* whitespace; the named group
        # itself is the clean token text.
        self.toks = [(m.lastgroup, m.group(m.lastgroup)) for m in _TOKEN.finditer(text)]
        self.i = 0
        # variable interning, reset per clause/query: same name in one
        # clause is the SAME variable (else rule bodies never see the
        # head's bindings).
        self._vars: Dict[str, V] = {}

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, val: str) -> None:
        kind, text = self.next()
        if text != val:
            raise SyntaxError(f"unify: expected {val!r}, got {text!r}")

    def term(self) -> Any:
        kind, text = self.next()
        if kind == "var":
            # intern by name: every "X" in this clause is one variable
            return self._vars.setdefault(text, V(text))
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "atom":
            if self.peek()[1] == "(":
                self.next()
                args = [self.term()]
                while self.peek()[1] == ",":
                    self.next()
                    args.append(self.term())
                self.expect(")")
                return T(text, args)
            return text
        raise SyntaxError(f"unify: unexpected {text!r} in term")

    def clause(self) -> Tuple[Any, List[Any]]:
        self._vars = {}  # fresh scope: clauses don't share variables
        head = self.term()
        body: List[Any] = []
        if self.peek()[1] == ":-":
            self.next()
            body.append(self.term())
            while self.peek()[1] == ",":
                self.next()
                body.append(self.term())
        self.expect(".")
        return head, body

    def query(self) -> List[Any]:
        self._vars = {}  # fresh scope for the query's variables
        kind, text = self.next()
        if text != "?-":
            raise SyntaxError("unify: query must start with ?-")
        goals = [self.term()]
        while self.peek()[1] == ",":
            self.next()
            goals.append(self.term())
        self.expect(".")
        return goals


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


class Engine:
    """A tiny Prolog-subset engine with reified backtracking."""

    def __init__(self) -> None:
        # (functor, arity) -> {"var_first": [clauses], "ground": {key: [clauses]}}
        self._index: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.clauses: List[Tuple[Any, List[Any]]] = []
        self.choice_points: List[Tuple[str, int]] = []  # reified: (goal, clause#)

    # -- asserting ----------------------------------------------------------
    def tell(self, source: str) -> "Engine":
        """Assert facts and rules: ``parent(tom, bob).`` / ``a(X) :- b(X).``"""
        p = _Parser(source)
        while p.peek()[0] is not None:
            head, body = p.clause()
            self._assert(head, body)
        return self

    def _key(self, head: Any) -> Tuple[str, int]:
        if isinstance(head, T):
            return head.functor, len(head.args)
        return str(head), 0

    def _first_arg_key(self, head: Any):
        if isinstance(head, T) and head.args:
            a = head.args[0]
            if isinstance(a, str):
                return ("atom", a)
            if isinstance(a, (int, float)):
                return ("num", a)
        return None  # variable or missing first arg

    def _assert(self, head: Any, body: List[Any]) -> None:
        idx = len(self.clauses)
        self.clauses.append((head, body))
        bucket = self._index.setdefault(
            self._key(head), {"var_first": [], "ground": {}}
        )
        gk = self._first_arg_key(head)
        if gk is None:
            bucket["var_first"].append(idx)
        else:
            bucket["ground"].setdefault(gk, []).append(idx)

    # -- unification ----------------------------------------------------------
    @staticmethod
    def _deref(t: Any, subst: Dict[V, Any]) -> Any:
        while isinstance(t, V) and t in subst:
            t = subst[t]
        return t

    @classmethod
    def _occurs(cls, v: V, t: Any, subst: Dict[V, Any]) -> bool:
        t = cls._deref(t, subst)
        if t is v:
            return True
        if isinstance(t, T):
            return any(cls._occurs(v, a, subst) for a in t.args)
        return False

    def _unify(self, a: Any, b: Any, subst: Dict[V, Any], trail: List[V]) -> bool:
        """Unify in place; every binding is logged on the trail."""
        a = self._deref(a, subst)
        b = self._deref(b, subst)
        if isinstance(a, V):
            if a is b:
                return True
            if self._occurs(a, b, subst):  # the occurs-check
                return False
            subst[a] = b
            trail.append(a)
            return True
        if isinstance(b, V):
            return self._unify(b, a, subst, trail)
        if isinstance(a, T) and isinstance(b, T):
            return (
                a.functor == b.functor
                and len(a.args) == len(b.args)
                and all(
                    self._unify(x, y, subst, trail)
                    for x, y in zip(a.args, b.args, strict=True)
                )
            )
        return a == b and type(a) is type(b)

    @staticmethod
    def _unwind(trail: List[V], mark: int, subst: Dict[V, Any]) -> None:
        """Undo every binding made since the mark — reified backtracking."""
        while len(trail) > mark:
            del subst[trail.pop()]

    # -- freshening ---------------------------------------------------------
    @staticmethod
    def _freshen(head: Any, body: List[Any]) -> Tuple[Any, List[Any]]:
        fresh: Dict[V, V] = {}

        def _fresh(t: Any) -> Any:
            if isinstance(t, V):
                return fresh.setdefault(t, V(t.name))
            if isinstance(t, T):
                return T(t.functor, [_fresh(a) for a in t.args])
            return t

        return _fresh(head), [_fresh(g) for g in body]

    # -- first-argument dispatch ----------------------------------------------
    def _candidates(self, goal: Any, subst: Dict[V, Any]) -> List[int]:
        """Dispatch on the discriminator; never scan the whole store when
        the goal's first argument is ground."""
        key = self._key(self._deref(goal, subst))
        bucket = self._index.get(key)
        if bucket is None:
            return []
        if isinstance(goal, T) and goal.args:
            first = self._deref(goal.args[0], subst)
            gk = None
            if isinstance(first, str):
                gk = ("atom", first)
            elif isinstance(first, (int, float)):
                gk = ("num", first)
            if gk is not None:
                # ground discriminator: ground bucket + var-headed clauses
                return bucket["ground"].get(gk, []) + bucket["var_first"]
        return bucket["var_first"] + [i for v in bucket["ground"].values() for i in v]

    # -- the prover -----------------------------------------------------------
    def _solve(
        self, goals: List[Any], subst: Dict[V, Any], trail: List[V]
    ) -> Iterator[Dict[V, Any]]:
        if not goals:
            yield dict(subst)
            return
        goal = self._deref(goals[0], subst)
        rest = goals[1:]
        for idx in self._candidates(goal, subst):
            mark = len(trail)
            head, body = self._freshen(*self.clauses[idx])
            self.choice_points.append((term_str(goal), idx))
            if self._unify(goal, head, subst, trail):
                yield from self._solve([*body, *rest], subst, trail)
            self.choice_points.pop()
            self._unwind(trail, mark, subst)

    def query(self, source: str) -> List[Dict[str, str]]:
        """Run ``?- goal.`` — returns a list of variable bindings."""
        goals = _Parser(source).query()
        qvars: Dict[str, V] = {}
        for g in goals:
            for v in _walk_vars(g):
                qvars.setdefault(v.name, v)
        out = []
        for subst in self._solve(goals, {}, []):
            out.append(
                {name: term_str(self._deref(v, subst)) for name, v in qvars.items()}
            )
        return out


def _walk_vars(t: Any) -> Iterator[V]:
    if isinstance(t, V):
        yield t
    elif isinstance(t, T):
        for a in t.args:
            yield from _walk_vars(a)


# ---------------------------------------------------------------------------
# Demo — a family tree with a recursive ancestor rule
# ---------------------------------------------------------------------------


def demo_kb() -> Engine:
    e = Engine()
    e.tell("""
        parent(tom, bob).
        parent(tom, liz).
        parent(bob, ann).
        parent(liz, jim).
        ancestor(X, Y) :- parent(X, Y).
        ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).
    """)
    return e


def demo() -> List[Dict[str, str]]:
    return demo_kb().query("?- ancestor(tom, Who).")


if __name__ == "__main__":  # pragma: no cover - demo
    for sol in demo():
        print(sol)
