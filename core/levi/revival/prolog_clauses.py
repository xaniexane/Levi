"""Horn-clause logic programming: facts, rules, unification, backtracking.

Studied from: languages-hunt-20260915, report.md [S3, USEFUL PATTERN].

Inspired by the *shape* of Prolog: declare facts (``parent(tom, bob).``)
and rules (``grandparent(X, Z) :- parent(X, Y), parent(Y, Z).``), then ask
questions and let the machine search proofs by unifying terms and
backtracking through alternatives. This is an original, from-scratch
implementation for LEVI — no Prolog code is used.

Terms are :class:`Atom` (lowercase names, numbers), :class:`Var`
(uppercase names), and :class:`Compound` (functor with arguments).
:class:`KnowledgeBase` parses program text and answers queries,
yielding one binding dictionary per proof, with fresh variable renaming
per rule use so recursive rules terminate correctly on finite data.

Honest limits: no cut (``!``), no negation-as-failure, no arithmetic
evaluation, no disjunction in bodies, and search is depth-first —
left-recursive rules can loop forever. Occurs-check is implemented, so
``X = f(X)`` correctly fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Generator, Iterator, List, Optional, Tuple, Union

ORIGIN = "levi-revival/prolog"


class LogicError(Exception):
    """Base class for logic-programming failures."""


class ParseError(LogicError):
    """Program or query text could not be parsed."""


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Atom:
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Var:
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Compound:
    functor: str
    args: Tuple["Term", ...]

    def __repr__(self) -> str:
        return f"{self.functor}({', '.join(map(repr, self.args))})"


Term = Union[Atom, Var, Compound]
Subst = Dict[str, Term]


def _walk(term: Term, subst: Subst) -> Term:
    while isinstance(term, Var) and term.name in subst:
        term = subst[term.name]
    return term


def _occurs(var: str, term: Term, subst: Subst) -> bool:
    term = _walk(term, subst)
    if isinstance(term, Var):
        return term.name == var
    if isinstance(term, Compound):
        return any(_occurs(var, a, subst) for a in term.args)
    return False


def unify(a: Term, b: Term, subst: Optional[Subst] = None) -> Optional[Subst]:
    """Unify two terms; return the extended substitution or None on failure."""
    subst = dict(subst) if subst else {}
    a, b = _walk(a, subst), _walk(b, subst)
    if isinstance(a, Var):
        if isinstance(b, Var) and a.name == b.name:
            return subst
        if _occurs(a.name, b, subst):
            return None
        subst[a.name] = b
        return subst
    if isinstance(b, Var):
        return unify(b, a, subst)
    if isinstance(a, Atom) and isinstance(b, Atom):
        return subst if a.name == b.name else None
    if isinstance(a, Compound) and isinstance(b, Compound):
        if a.functor != b.functor or len(a.args) != len(b.args):
            return None
        for x, y in zip(a.args, b.args, strict=True):
            subst = unify(x, y, subst)
            if subst is None:
                return None
        return subst
    return None


def apply(term: Term, subst: Subst) -> Term:
    """Apply a substitution all the way down a term."""
    term = _walk(term, subst)
    if isinstance(term, Compound):
        return Compound(term.functor, tuple(apply(a, subst) for a in term.args))
    return term


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self) -> str:
        self._skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _expect(self, ch: str) -> None:
        if self._peek() != ch:
            raise ParseError(f"expected {ch!r} at position {self.pos}")
        self.pos += 1

    def _name(self) -> str:
        self._skip()
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] == "_"
        ):
            self.pos += 1
        if start == self.pos:
            raise ParseError(f"expected a name at position {self.pos}")
        return self.text[start : self.pos]

    def term(self) -> Term:
        name = self._name()
        if self._peek() == "(":
            self.pos += 1
            args = [self.term()]
            while self._peek() == ",":
                self.pos += 1
                args.append(self.term())
            self._expect(")")
            return Compound(name, tuple(args))
        if name[0].isupper() or name[0] == "_":
            return Var(name)
        return Atom(name)

    def clause(self) -> Tuple[Compound, List[Compound]]:
        head = self.term()
        if not isinstance(head, Compound):
            raise ParseError("clause head must be a compound term")
        body: List[Compound] = []
        self._skip()
        if self.text.startswith(":-", self.pos):
            self.pos += 2
            goal = self.term()
            if not isinstance(goal, Compound):
                raise ParseError("rule body goals must be compound terms")
            body.append(goal)
            while self._peek() == ",":
                self.pos += 1
                goal = self.term()
                if not isinstance(goal, Compound):
                    raise ParseError("rule body goals must be compound terms")
                body.append(goal)
        self._expect(".")
        return head, body


def parse_clause(text: str) -> Tuple[Compound, List[Compound]]:
    """Parse one ``head.`` fact or ``head :- body.`` rule."""
    return _Parser(text).clause()


def parse_query(text: str) -> List[Compound]:
    """Parse a comma-separated query like ``parent(tom, X), parent(X, Y)``."""
    parser = _Parser(text)
    goals = [parser.term()]
    while parser._peek() == ",":
        parser.pos += 1
        goals.append(parser.term())
    for g in goals:
        if not isinstance(g, Compound):
            raise ParseError("query goals must be compound terms")
    return goals


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


class KnowledgeBase:
    """A database of facts and rules with backtracking query search."""

    def __init__(self) -> None:
        self.clauses: List[Tuple[Compound, List[Compound]]] = []
        self._counter = 0

    def assert_program(self, program: str) -> None:
        """Parse and add every clause in ``program`` text."""
        parser = _Parser(program)
        while True:
            parser._skip()
            if parser.pos >= len(parser.text):
                break
            self.clauses.append(parser.clause())

    def assert_clause(self, text: str) -> None:
        """Add a single fact or rule given as text."""
        self.clauses.append(parse_clause(text))

    def _rename(
        self, clause: Tuple[Compound, List[Compound]]
    ) -> Tuple[Compound, List[Compound]]:
        """Give each rule use fresh variables so recursion stays sound."""
        self._counter += 1
        suffix = f"_{self._counter}"

        def fresh(term: Term) -> Term:
            if isinstance(term, Var):
                return Var(term.name + suffix)
            if isinstance(term, Compound):
                return Compound(term.functor, tuple(fresh(a) for a in term.args))
            return term

        head, body = clause
        return fresh(head), [fresh(g) for g in body]  # type: ignore[return-value]

    def _solve(
        self, goals: List[Compound], subst: Subst
    ) -> Generator[Subst, None, None]:
        if not goals:
            yield subst
            return
        first, rest = goals[0], goals[1:]
        for clause in self.clauses:
            head, body = self._rename(clause)
            unified = unify(first, head, subst)
            if unified is not None:
                yield from self._solve(list(body) + list(rest), unified)

    def query(
        self, text: str, limit: Optional[int] = None
    ) -> Iterator[Dict[str, Term]]:
        """Yield one binding dict per proof of ``text``.

        Only the query's own variables appear in each dict; anonymous
        ``_`` variables are dropped. ``limit`` caps the number of proofs.
        """
        goals = parse_query(text)
        wanted = {v.name for v in _query_vars(goals) if v.name != "_"}
        count = 0
        for subst in self._solve(goals, {}):
            yield {name: apply(Var(name), subst) for name in wanted}
            count += 1
            if limit is not None and count >= limit:
                break

    def ask(self, text: str) -> List[Dict[str, Term]]:
        """Collect every proof of ``text`` into a list."""
        return list(self.query(text))


def _query_vars(goals: List[Compound]) -> List[Var]:
    found: List[Var] = []

    def visit(term: Term) -> None:
        if isinstance(term, Var):
            found.append(term)
        elif isinstance(term, Compound):
            for a in term.args:
                visit(a)

    for g in goals:
        visit(g)
    return found
