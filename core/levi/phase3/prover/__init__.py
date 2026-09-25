"""Logic-prover primitives (A5 salvage: unification, bounded backtracking,
proof-as-explanation). WORKING TITLE — naming is Chauncey's, never canon.

Prolog-the-language stays dead; this module recreates only the mechanisms
as internal reasoning operations of one mind:

- :mod:`.terms`  — terms (atoms, variables, compound structures).
- :mod:`.unify`  — deterministic structural unification with occurs check.
- :mod:`.rules`  — Rule / Fact / Budget / proof-tree data types.
- :mod:`.prove`  — bounded backward-chaining search (depth, branches,
  wall-clock all capped; cap-exceeded is a receipted fault, never a hang).
- :mod:`.explain` — proof trees rendered as plain-speech "why" walks.
- :mod:`.sources` — thin ``RuleSource`` / ``FactSource`` protocols plus
  local ``DictRuleSource`` / ``DictFactSource`` stubs until the middle
  team pins the real protocols.

Laws: stdlib-only at import; zero network at runtime; deterministic —
same rules + same facts + same goal always yields the same proof tree.
No sentience or subjective-experience claims anywhere here: a proof is a
receipt, not a thought.
"""

from .explain import explain
from .prove import ProofFault, ProofOutcome, prove
from .rules import Budget, Fact, ProofNode, Rule
from .sources import DictFactSource, DictRuleSource, FactSource, RuleSource
from .terms import Atom, Compound, Term, Var
from .unify import Subst, unify

__all__ = [
    "Atom",
    "Budget",
    "Compound",
    "DictFactSource",
    "DictRuleSource",
    "Fact",
    "FactSource",
    "ProofFault",
    "ProofNode",
    "ProofOutcome",
    "Rule",
    "RuleSource",
    "Subst",
    "Term",
    "Var",
    "explain",
    "prove",
    "unify",
]
