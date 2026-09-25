"""Terms: the prover's data.

A term is one of:

- ``Atom`` — a named constant (``fred``).
- ``Var`` — a named placeholder (``X``, ``Y``).
- ``Compound`` — a functor applied to argument terms (``parent(fred, X)``).

Terms are immutable, hashable, and serialize to canonical dicts so proof
trees are byte-identical across runs and processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Term:
    """Base class for prover terms."""

    def to_dict(self) -> dict[str, Any]:
        """Canonical JSON-able dict for this term."""
        raise NotImplementedError


@dataclass(frozen=True)
class Atom(Term):
    """A named constant."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("prover: Atom name must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {"k": "atom", "n": self.name}

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Var(Term):
    """A named logic variable."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("prover: Var name must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {"k": "var", "n": self.name}

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Compound(Term):
    """A functor applied to argument terms."""

    functor: str
    args: tuple[Term, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.functor, str) or not self.functor:
            raise ValueError("prover: Compound functor must be a non-empty string")
        object.__setattr__(self, "args", tuple(self.args))
        for arg in self.args:
            if not isinstance(arg, Term):
                raise ValueError("prover: Compound args must all be Terms")

    def to_dict(self) -> dict[str, Any]:
        return {
            "k": "compound",
            "f": self.functor,
            "a": [a.to_dict() for a in self.args],
        }

    def __repr__(self) -> str:
        return "%s(%s)" % (self.functor, ", ".join(repr(a) for a in self.args))


def term_from_dict(data: dict[str, Any]) -> Term:
    """Rebuild a term from :meth:`Term.to_dict` output."""
    kind = data["k"]
    if kind == "atom":
        return Atom(data["n"])
    if kind == "var":
        return Var(data["n"])
    if kind == "compound":
        return Compound(data["f"], tuple(term_from_dict(a) for a in data["a"]))
    raise ValueError("prover: unknown term kind %r" % (kind,))
