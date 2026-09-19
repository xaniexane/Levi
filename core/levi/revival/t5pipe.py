"""Extreme task decomposition + pipelining — steps too small to get wrong.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #31).

The mechanism under study: a complex computation is decomposed until
each step is *one operation* — one add, one multiply, one cube — and
the steps are arranged as an assembly line. Intermediate results move
down the line like cards: each stage reads its inputs, does its single
op, and passes the card on. The decomposition is the algorithm; every
stage is inspectable (input, operation, output), so the pipeline can
be audited card by card.

This is an original, from-scratch implementation for LEVI. A
``Pipeline`` holds ordered ``Stage``s, each a single arithmetic op over
literal values or references to earlier cards (``ref(i)``). ``run()``
executes deterministically — forward references, unknown ops, and
bad operand counts are refused up front — and produces a ``Card`` per
stage: the explicit audit trail. ``audit()`` renders the card table as
text.

Public surface:
- ``OP``: the single-operation vocabulary (add, sub, mul, div, pow,
  neg, abs, sqrt).
- ``ref(i)``: reference the i-th earlier card.
- ``Pipeline``: ``add(op, *operands)``, ``run() -> List[Card]``,
  ``audit() -> str``, ``result()``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union

ORIGIN = "levi-revival/t5pipe"


class T5Error(Exception):
    """The pipeline refused: unknown op, forward reference, bad arity."""


class OP(Enum):
    """Single operations — each step of the line is exactly one of these."""

    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    POW = "pow"
    NEG = "neg"
    ABS = "abs"
    SQRT = "sqrt"


@dataclass(frozen=True)
class Ref:
    """Reference to an earlier card: the pipeline is a chain, never a loop."""

    index: int


def ref(index: int) -> Ref:
    """Reference card ``index`` (0-based) as an operand of a later stage."""
    return Ref(index)


@dataclass
class Stage:
    op: OP
    operands: List[Union[float, Ref]] = field(default_factory=list)


@dataclass
class Card:
    """One stage's audit record: input values, operation, output."""

    index: int
    op: str
    inputs: List[float]
    output: float


_ARITY = {
    OP.ADD: 2,
    OP.SUB: 2,
    OP.MUL: 2,
    OP.DIV: 2,
    OP.POW: 2,
    OP.NEG: 1,
    OP.ABS: 1,
    OP.SQRT: 1,
}


def _apply(op: OP, inputs: List[float]) -> float:
    a = inputs[0]
    if op is OP.ADD:
        return a + inputs[1]
    if op is OP.SUB:
        return a - inputs[1]
    if op is OP.MUL:
        return a * inputs[1]
    if op is OP.DIV:
        if inputs[1] == 0:
            raise T5Error("division by zero at pipeline stage")
        return a / inputs[1]
    if op is OP.POW:
        return a ** inputs[1]
    if op is OP.NEG:
        return -a
    if op is OP.ABS:
        return abs(a)
    if op is OP.SQRT:
        if a < 0:
            raise T5Error("sqrt of a negative value at pipeline stage")
        return math.sqrt(a)
    raise T5Error(f"unknown op {op}")  # unreachable: OP is closed


class Pipeline:
    """An assembly line of single-op stages. Cards flow down it in order."""

    def __init__(self, name: str = "pipeline") -> None:
        self.name = name
        self._stages: List[Stage] = []

    def add(self, op: OP, *operands: Union[float, int, Ref]) -> int:
        """Append one micro-step. Returns its card index for later ``ref`` use."""
        if op not in _ARITY:
            raise T5Error(f"unknown op {op!r}: pipeline steps are single OPs")
        if len(operands) != _ARITY[op]:
            raise T5Error(
                f"{op.value} needs {_ARITY[op]} operands, got {len(operands)}"
            )
        index = len(self._stages)
        normalized: List[Union[float, Ref]] = []
        for operand in operands:
            if isinstance(operand, Ref):
                if not 0 <= operand.index < index:
                    raise T5Error(
                        f"forward reference: stage {index} reads card "
                        f"{operand.index}, which does not exist yet"
                    )
                normalized.append(operand)
            else:
                normalized.append(float(operand))
        self._stages.append(Stage(op, normalized))
        return index

    def run(self) -> List[Card]:
        """Execute the line deterministically, returning the audit cards."""
        cards: List[Card] = []
        values: List[float] = []
        for index, stage in enumerate(self._stages):
            inputs = [
                values[o.index] if isinstance(o, Ref) else o for o in stage.operands
            ]
            output = _apply(stage.op, inputs)
            values.append(output)
            cards.append(
                Card(index=index, op=stage.op.value, inputs=list(inputs), output=output)
            )
        return cards

    def result(self) -> float:
        """The final card's value — the pipeline's answer."""
        cards = self.run()
        if not cards:
            raise T5Error("empty pipeline has no result")
        return cards[-1].output

    def audit(self) -> str:
        """Render the card table: each stage's input, op, and output."""
        lines = [f"T-5 pipeline '{self.name}': {len(self._stages)} stages"]
        for card in self.run():
            operands = ", ".join(repr(i) for i in card.inputs)
            lines.append(f"  [{card.index}] {card.op}({operands}) = {card.output}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._stages)
