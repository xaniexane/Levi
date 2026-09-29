"""Value Analysis: L.D. Miles — stop thinking in parts, start thinking in
functions.

Origin: Lawrence D. Miles, purchasing executive at General Electric,
1947. Facing the postwar asbestos shortage (GE coated paint-room floors
with asbestos for fire safety), Miles asked the load-bearing question:
"for what purpose was asbestos used?" The substitute was cheaper, and
Miles generalized the question into Value Analysis: define every
component by its FUNCTION — a verb–noun pair ("prevent fire", "support
weight") — classify functions as USE (does the job) or ESTEEM
(looks/feels right), assign cost to functions instead of parts, and
compute value as function divided by cost. Cost that provides neither
use nor esteem is unnecessary cost, by definition. GE awarded Miles its
Charles A. Coffin Award in 1950; the US DoD adopted it (as Value
Engineering) in 1954. The discipline later diluted into procurement
cost-cutting theater — the function question replaced by the price
question.

The mechanism is the grammar: verb–noun functions force precision
("support 2 kg" can be costed; "make good" cannot), and hanging cost on
functions instead of parts makes a $40 bracket and a $4 wire comparable
for the first time. USE vs ESTEEM keeps the method honest: esteem is
real and priced, not dismissed.

What it is in LEVI: the function discipline, enforced in code. A
ValueStudy holds verb–noun functions with USE/ESTEEM classification and
a necessity weight; costs attach to functions; score() returns the
function/cost arithmetic; waste() names every function whose necessity
is zero — Miles's unnecessary cost, itemized.

LAWS (declared here, enforced below):
  L1. Every function is verb–noun. Blank verbs or nouns are rejected;
      the grammar is the engine.
  L2. Classification is USE or ESTEEM only. Nothing else is a function.
  L3. value = function / cost. Scoring requires at least one function
      and positive total cost; cost with no function — or a function of
      zero necessity — is waste by definition.

Honesty label: LOAD-BEARING — function-based costing is a concrete,
transferable discipline. The skepticism stays in the docstring: Miles's
savings claims come from his own books and GE's awards (practitioner
literature, not independent audit); the asbestos origin story has
variants; esteem is priced by opinion; and the numbers are approximate —
the method's precision is in the questions, not the arithmetic.

Deny-closed inputs: blank verb/noun, unknown classification, necessity
outside [0, 1], negative cost, unknown function id, scoring with no
functions, scoring with non-positive total cost — all ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["Function", "ValueStudy", "USE", "ESTEEM"]

USE = "use"
ESTEEM = "esteem"
CLASSIFICATIONS = (USE, ESTEEM)


@dataclass(frozen=True)
class Function:
    verb: str
    noun: str
    classification: str
    necessity: float = 1.0  # 0 = provides nothing = waste by definition (L3)

    def __post_init__(self) -> None:
        if not self.verb or not self.verb.strip():
            raise ValueError("function verb must not be blank (L1)")
        if not self.noun or not self.noun.strip():
            raise ValueError("function noun must not be blank (L1)")
        if self.classification not in CLASSIFICATIONS:
            raise ValueError("classification must be 'use' or 'esteem' (L2), got %r" % (self.classification,))
        if not 0.0 <= self.necessity <= 1.0:
            raise ValueError("necessity must be in [0, 1], got %r" % (self.necessity,))

    @property
    def phrase(self) -> str:
        return "%s %s" % (self.verb.strip(), self.noun.strip())


class ValueStudy:
    """One Miles value study over a single item."""

    def __init__(self, item: str) -> None:
        if not item or not item.strip():
            raise ValueError("item must not be blank")
        self._item = item.strip()
        self._functions: Dict[str, Function] = {}
        self._costs: Dict[str, float] = {}
        self._next_id = 1

    @property
    def item(self) -> str:
        return self._item

    def add_function(self, verb: str, noun: str, classification: str, necessity: float = 1.0) -> str:
        """Add a verb–noun function (L1, L2). Returns its id."""
        fn = Function(verb=verb, noun=noun, classification=classification, necessity=necessity)
        fid = "f%d" % self._next_id
        self._next_id += 1
        self._functions[fid] = fn
        self._costs[fid] = 0.0
        return fid

    def assign_cost(self, function_id: str, amount: float) -> float:
        """Hang a cost on a function (L3: cost lives on functions, not parts)."""
        if function_id not in self._functions:
            raise ValueError("unknown function: %s" % (function_id,))
        if amount < 0:
            raise ValueError("cost cannot be negative")
        self._costs[function_id] = float(amount)
        return float(amount)

    def functions(self) -> Dict[str, Function]:
        return dict(self._functions)

    def total_cost(self) -> float:
        return sum(self._costs.values())

    def waste(self) -> List[str]:
        """Functions of zero necessity — Miles's unnecessary cost (L3)."""
        return [fid for fid, fn in self._functions.items() if fn.necessity == 0.0]

    def score(self) -> Dict[str, float]:
        """The whole arithmetic: value = function / cost (L3)."""
        if not self._functions:
            raise ValueError("cannot score a study with no functions")
        total = self.total_cost()
        if total <= 0:
            raise ValueError("cannot score: total cost must be positive")
        weighted = sum(fn.necessity for fn in self._functions.values())
        waste_cost = sum(self._costs[fid] for fid in self.waste())
        return {
            "functions": float(len(self._functions)),
            "weighted_function": weighted,
            "total_cost": total,
            "value_ratio": weighted / total,
            "waste_cost": waste_cost,
        }
