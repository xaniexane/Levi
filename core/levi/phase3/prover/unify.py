"""Deterministic structural unification with the occurs check.

``unify(t1, t2)`` is a pure function: it returns a substitution mapping
variable names to terms, or ``None`` on failure (FAIL). It has no side
effects and never depends on ordering beyond the fixed argument order —
same inputs always yield the same substitution.
"""

from __future__ import annotations

from .terms import Compound, Term, Var

#: A substitution: variable name -> term.
Subst = dict[str, Term]


def walk(term: Term, subst: Subst) -> Term:
    """Follow a variable's binding chain to its current representative."""
    while isinstance(term, Var) and term.name in subst:
        term = subst[term.name]
    return term


def occurs(var: Var, term: Term, subst: Subst) -> bool:
    """True if ``var`` occurs anywhere inside ``term`` (post-walk)."""
    term = walk(term, subst)
    if term == var:
        return True
    if isinstance(term, Compound):
        return any(occurs(var, a, subst) for a in term.args)
    return False


def apply(term: Term, subst: Subst) -> Term:
    """Fully instantiate ``term`` under ``subst`` (new term, no mutation)."""
    term = walk(term, subst)
    if isinstance(term, Compound):
        return Compound(term.functor, tuple(apply(a, subst) for a in term.args))
    return term


def unify(t1: Term, t2: Term, subst: Subst | None = None) -> Subst | None:
    """Unify two terms; return the substitution or ``None`` on FAIL.

    Iterative (explicit work stack) so pathological nesting cannot blow
    the interpreter stack. Deterministic: argument order is fixed, and
    bindings are recorded in the order they are made.
    """
    s: Subst = dict(subst) if subst else {}
    stack: list[tuple[Term, Term]] = [(t1, t2)]
    while stack:
        a, b = stack.pop()
        a = walk(a, s)
        b = walk(b, s)
        if a == b:
            continue
        if isinstance(a, Var):
            if occurs(a, b, s):
                return None
            s[a.name] = b
            continue
        if isinstance(b, Var):
            if occurs(b, a, s):
                return None
            s[b.name] = a
            continue
        if (
            isinstance(a, Compound)
            and isinstance(b, Compound)
            and a.functor == b.functor
            and len(a.args) == len(b.args)
        ):
            stack.extend(zip(a.args, b.args, strict=True))
            continue
        return None
    return s
