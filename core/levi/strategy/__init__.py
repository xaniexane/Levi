"""The 48 — forward/reverse compressed strategy engine.

THE LIFE FORMULA (deterministic, repeatable — situation in, projection out):

    Projection = 5-3-5( consult( Situation ) )

- The 48 laws are the CONSTANTS.
- Return-to-sender is the OPERATOR (applied when the situation is an attack).
- 5-3-5 is the COMPUTATION: think 5 ahead, lock 3, map the next 5 — every
  angle, every outcome, best EFFICIENT outcome (best at lowest cost).

Domain-universal: any life area in — health, relationships, money, work,
goals, daily decisions, anything.

Doctrine (binding): defense never manipulates; attack = going and getting
the goal. All 48 laws are original LEVI-native works.
"""

from .engine import (
    Engine,
    FormulaResult,
    Law,
    Projection,
    Reading,
    Reflection,
    Step,
)
from .laws import build_laws

ENGINE = Engine(build_laws())


def consult(situation: str, top: int = 5, domain=None):
    """Rank the laws that bear on a situation, forward+reverse together."""
    return ENGINE.consult(situation, top=top, domain=domain)


def project(situation: str, depth: int = 5, domain=None) -> Projection:
    """Apply the 5-3-5 lookahead: `depth` ahead, lock 3, map next `depth`."""
    return ENGINE.project(situation, depth=depth, domain=domain)


def apply(situation: str, domain=None) -> FormulaResult:
    """Apply the whole life formula: RTS operator ? 48 laws ? 5-3-5."""
    return ENGINE.apply(situation, domain=domain)


def return_to_sender(attack: str) -> Reflection:
    """The signature defensive move: reflect it back cleanly."""
    return ENGINE.return_to_sender(attack)


def laws():
    return ENGINE.laws


def get_law(law_id: int) -> Law:
    return ENGINE.get(law_id)


def domains():
    return ENGINE.domains()


__all__ = [
    "Engine", "Law", "Reading", "Step", "Projection", "Reflection",
    "FormulaResult", "ENGINE", "consult", "project", "apply",
    "return_to_sender", "laws", "get_law", "domains",
]
