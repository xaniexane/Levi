"""A hybrid pipeline: machine function units, hand teams, and role transfer.

Studied from: pre-digital-computation-20260916/report.md [Beat C #2]
(Moore School -> ENIAC Six, 1940-45)

The studied shape: a hybrid pipeline where a differential analyzer and
hand-computing teams split the work, and the operators learned the
machine from its blueprints — role transfer as an explicit discipline.
The machine is a set of function units wired together; the program is
the wiring plus a step sequence; no operator runs a unit she has not
demonstrated competence on.

LEVI-native re-expression: a **Blueprint** declares function units and
their wiring (unit outputs feeding unit inputs); a **Machine** runs a
program against the blueprint; **Operators** belong to **Teams** that
can do steps by hand (heuristic stand-ins); **role transfer** is a
certification ledger — an operator studies a blueprint, runs a
competence program on the machine, and is certified per unit before
operating it.

Operations:

* ``Blueprint()`` / ``add_unit(name, op)`` / ``wire(src, dst)`` — op is a pure function
* ``Machine.run(blueprint, steps, inputs)`` — execute wired units in step order
* ``Team.assign(step, operator)`` — hand-computed steps with operator attribution
* ``RoleTransfer.certify(operator, unit, blueprint, competence_inputs)`` — study -> demo -> certified
* ``is_qualified(operator, unit)`` — gate check before operating

Honest limits: function-unit ops are ordinary Python functions, not
electronic simulation. Competence is demonstrated by reproducing the
unit's expected output on given inputs — a checking discipline, not a
claim about human learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set


ORIGIN = "levi-revival/eniac-six"

# A function unit's operation: input values -> output value. Pure function.
UnitOp = Callable[..., Any]


@dataclass(frozen=True)
class FunctionUnit:
    """One wired unit on the blueprint: name + pure operation."""

    name: str
    op: UnitOp


class Blueprint:
    """The machine's wiring diagram: units plus output->input connections."""

    def __init__(self) -> None:
        self.units: Dict[str, FunctionUnit] = {}
        self.wires: Dict[str, str] = {}  # consumer input label -> producer unit name
        self.description: str = ""

    def add_unit(self, name: str, op: UnitOp) -> "Blueprint":
        if name in self.units:
            raise ValueError(f"unit {name!r} already on the blueprint")
        self.units[name] = FunctionUnit(name, op)
        return self

    def wire(self, producer: str, consumer_input: str) -> "Blueprint":
        if producer not in self.units:
            raise ValueError(f"no unit {producer!r} on the blueprint")
        self.wires[consumer_input] = producer
        return self

    def resolve(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Follow wiring: map every consumer input label to its producer's output.

        Wires route lazily: a label resolves as soon as its producer's
        value exists, so wiring can be declared before any unit runs.
        """
        resolved = dict(values)
        for label, producer in self.wires.items():
            if producer in values:
                resolved[label] = values[producer]
        return resolved


class Machine:
    """Runs a program: an ordered list of (unit_name, arg_labels) steps."""

    @staticmethod
    def run(
        blueprint: Blueprint,
        steps: List[tuple],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        values: Dict[str, Any] = dict(inputs)
        for unit_name, arg_labels in steps:
            if unit_name not in blueprint.units:
                raise ValueError(f"program calls unknown unit {unit_name!r}")
            resolved = blueprint.resolve(values)
            args = [resolved[label] for label in arg_labels]
            values[unit_name] = blueprint.units[unit_name].op(*args)
        return values


@dataclass
class Operator:
    """One member of the computing staff."""

    name: str
    certifications: Set[str] = field(default_factory=set)

    def is_qualified(self, unit: str) -> bool:
        return unit in self.certifications


class RoleTransfer:
    """The transfer discipline: study the blueprint, demo the unit, get certified.

    Competence is demonstrated, not declared: the operator must run the
    unit's operation on the competence inputs and reproduce the expected
    outputs exactly.
    """

    def __init__(self) -> None:
        self.log: List[Dict[str, Any]] = []

    def certify(
        self,
        operator: Operator,
        unit: str,
        blueprint: Blueprint,
        competence_cases: List[tuple],
    ) -> bool:
        """Study (read blueprint) then demo (reproduce every competence case).

        ``competence_cases``: list of (args_tuple, expected) for the unit's op.
        Returns True and certifies on success; False leaves certification untouched.
        """
        if unit not in blueprint.units:
            raise ValueError(f"no unit {unit!r} on the blueprint")
        op = blueprint.units[unit].op
        for args, expected in competence_cases:
            if op(*args) != expected:
                self.log.append(
                    {"operator": operator.name, "unit": unit, "passed": False}
                )
                return False
        operator.certifications.add(unit)
        self.log.append({"operator": operator.name, "unit": unit, "passed": True})
        return True


@dataclass
class HandStep:
    """A program step computed by a hand team member instead of the machine."""

    step_name: str
    operator: str
    result: Any


class HybridTeam:
    """Machine steps plus hand-computed steps, all attributed to operators."""

    def __init__(self, blueprint: Blueprint) -> None:
        self.blueprint = blueprint
        self.hand_steps: List[HandStep] = []
        self.machine_runs: List[Dict[str, Any]] = []

    def machine_step(
        self, operator: Operator, unit: str, steps: List[tuple], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not operator.is_qualified(unit):
            raise PermissionError(
                f"operator {operator.name!r} is not certified for unit {unit!r} — role transfer required"
            )
        result = Machine.run(self.blueprint, steps, inputs)
        self.machine_runs.append(
            {"operator": operator.name, "unit": unit, "result": result}
        )
        return result

    def hand_step(
        self, operator: Operator, step_name: str, compute: Callable[[], Any]
    ) -> Any:
        """A hand-team computation: ``compute`` is a heuristic stand-in for hand work."""
        result = compute()
        self.hand_steps.append(HandStep(step_name, operator.name, result))
        return result
