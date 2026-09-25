"""Demo: the prover proving a kinship claim and explaining itself.

Run: ``python -m levi.phase3.prover`` (from the repo root with
``core/`` on ``sys.path``).
"""

from __future__ import annotations

from . import (
    Atom,
    Budget,
    Compound,
    DictFactSource,
    DictRuleSource,
    Var,
    explain,
    prove,
)


def _demo_base() -> tuple[DictRuleSource, DictFactSource]:
    a = Atom
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    rules = DictRuleSource(
        [
            {
                "id": "gp1",
                "head": Compound("grandparent", (X, Z)),
                "body": [
                    Compound("parent", (X, Y)),
                    Compound("parent", (Y, Z)),
                ],
                "provenance": "demo: kinship axioms",
            },
            {
                "id": "p1",
                "head": Compound("parent", (X, Y)),
                "body": [Compound("mother", (X, Y))],
                "provenance": "demo: kinship axioms",
            },
            {
                "id": "p2",
                "head": Compound("parent", (X, Y)),
                "body": [Compound("father", (X, Y))],
                "provenance": "demo: kinship axioms",
            },
        ]
    )
    facts = DictFactSource(
        [
            {
                "id": "f1",
                "term": Compound("mother", (a("aria"), a("bea"))),
                "witness": "r-7",
            },
            {
                "id": "f2",
                "term": Compound("father", (a("bea"), a("cy"))),
                "witness": "r-9",
            },
            {
                "id": "f3",
                "term": Compound("father", (a("aria"), a("dex"))),
                "witness": "r-11",
            },
        ]
    )
    return rules, facts


def main() -> None:
    rules, facts = _demo_base()
    goal = Compound("grandparent", (Atom("aria"), Atom("cy")))
    outcome = prove(goal, rules, facts, Budget(max_depth=8, max_ms=2000))
    print(explain(outcome))
    print()
    # Budget demo: an exploding rule base faults receipted, never hangs.
    boom = DictRuleSource(
        [
            {
                "id": "b1",
                "head": Compound("p", (Var("X"),)),
                "body": [Compound("p", (Var("Y"),)), Compound("p", (Var("Z"),))],
                "provenance": "demo: adversarial branching",
            }
        ]
    )
    empty = DictFactSource([])
    bad = prove(
        Compound("p", (Atom("q"),)),
        boom,
        empty,
        Budget(max_depth=64, max_branches=50_000, max_ms=500),
    )
    print(explain(bad))


if __name__ == "__main__":
    main()
