"""Soroban and suanpan: bi-quinary bead reckoning.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #13)

The mechanism: each rod carries two ranks of beads separated by a bar.
Heaven beads above the bar are worth 5 each; earth beads below are
worth 1 each. A soroban rod has 1 heaven + 4 earth beads (digits 0-9);
a suanpan rod has 2 heaven + 5 earth beads (the spares absorb
intermediate carries, a legacy of hexadecimal weight work). Beads count
only when moved to the bar — the number on a rod is a physical
configuration, not a symbol.

Addition never counts past 9 on a rod. Instead it uses complements:
- 5-complement: to add 4 to a rod showing 1, engage heaven (+5) and
  drop 1 earth bead — "add 5, subtract 1".
- 10-complement: to add 8 to a rod showing 7, carry 1 left and subtract
  2 here — "add 10, subtract 2".
- combined 5-and-10 complement when both are needed at once.

What this module models:
- ``Abacus``: rods of (heaven, earth) bead state; ``set_value``,
  ``read``, ``add``, ``subtract`` with genuine per-rod bead moves and
  the complement technique recorded per rod in ``last_techniques``.
- Suanpan spare beads: permitted as intermediate states, normalized on
  read — ``normalize`` carries the spares.
- ``bead_diagram``: the frame as text.
- ``anzan_drill``: a mental-arithmetic practice harness — flashes a
  sequence (as data) and checks the trainee's answer.

Honest limits: non-negative integer arithmetic within the rod count
(overflow raises rather than wrapping — a real frame has no hidden
extra rod); the anzan drill is a practice harness, not a model of
embodied cognition — it cannot tell you how mental visualization
works, only whether your answer matches. No network, stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


ORIGIN = "levi-revival/soroban-suanpan"


@dataclass
class RodState:
    """Bead configuration of one rod: beads engaged toward the bar."""

    heaven: int = 0  # each worth 5
    earth: int = 0  # each worth 1

    def value(self) -> int:
        return 5 * self.heaven + self.earth


class Abacus:
    """A bi-quinary bead frame.

    ``heaven``/``earth`` set the bead counts per rod: (1, 4) is a
    soroban, (2, 5) a suanpan. ``rods`` is the digit width; the
    rightmost rod is the units column.
    """

    def __init__(self, rods: int = 13, heaven: int = 1, earth: int = 4) -> None:
        if rods < 1:
            raise ValueError("need at least one rod")
        if heaven not in (1, 2) or earth not in (4, 5):
            raise ValueError("supported frames: soroban (1,4), suanpan (2,5)")
        self.rods = rods
        self.heaven = heaven
        self.earth = earth
        self._rods: List[RodState] = [RodState() for _ in range(rods)]
        self.last_techniques: List[Tuple[int, str]] = []

    @property
    def frame(self) -> str:
        return "suanpan" if (self.heaven, self.earth) == (2, 5) else "soroban"

    def _max_rod_value(self) -> int:
        return 5 * self.heaven + self.earth

    def _check_rod(self, i: int) -> None:
        if not 0 <= i < self.rods:
            raise IndexError(f"rod {i} out of range 0..{self.rods - 1}")

    # -- placing and reading numbers --------------------------------------
    def set_rod(self, i: int, digit: int) -> None:
        """Move a rod's beads to show ``digit`` (0..9)."""
        self._check_rod(i)
        if not 0 <= digit <= 9:
            raise ValueError("a rod shows a single decimal digit")
        self._rods[i] = RodState(heaven=digit // 5, earth=digit % 5)

    def read_rod(self, i: int) -> int:
        self._check_rod(i)
        return self._rods[i].value()

    def set_value(self, n: int) -> None:
        """Show ``n`` on the frame, units on the rightmost rod."""
        if n < 0:
            raise ValueError("the frame shows non-negative integers")
        digits = [int(c) for c in str(n)]
        if len(digits) > self.rods:
            raise OverflowError(f"{n} needs more than {self.rods} rods")
        for i in range(self.rods):
            self.set_rod(i, 0)
        for offset, d in enumerate(reversed(digits)):
            self.set_rod(self.rods - 1 - offset, d)

    def read(self) -> int:
        """Read the frame as an integer (normalizes suanpan spares first)."""
        self.normalize()
        value = 0
        for rod in self._rods:
            value = value * 10 + rod.value()
        return value

    def normalize(self) -> None:
        """Carry spare-bead values (suanpan intermediates) into place."""
        carry = 0
        for i in range(self.rods - 1, -1, -1):
            total = self._rods[i].value() + carry
            carry, digit = divmod(total, 10)
            self._rods[i] = RodState(heaven=digit // 5, earth=digit % 5)
        if carry:
            raise OverflowError("normalization carried past the leftmost rod")

    # -- bead arithmetic with complements ----------------------------------
    def _move_rod(self, i: int, target: int) -> None:
        """Move rod ``i``'s beads to show ``target`` (0..9)."""
        self._rods[i] = RodState(heaven=target // 5, earth=target % 5)

    def _classify_add(self, v: int, d: int, carry_in: int) -> str:
        s = v + d + carry_in
        if d + carry_in == 0:
            return "none"
        heaven_toggles = (v < 5) != (s % 10 < 5)
        if s < 10:
            return "five-complement" if heaven_toggles else "direct"
        return "five-ten-complement" if heaven_toggles else "ten-complement"

    def _classify_sub(self, v: int, d: int, borrow_in: int) -> str:
        s = v - d - borrow_in
        if d + borrow_in == 0:
            return "none"
        target = s % 10
        heaven_toggles = (v < 5) != (target < 5)
        if s >= 0:
            return "five-complement" if heaven_toggles else "direct"
        return "five-ten-complement" if heaven_toggles else "ten-complement"

    def add(self, n: int) -> int:
        """Add ``n`` rod by rod, right to left, using complements."""
        if n < 0:
            raise ValueError("use subtract for negative amounts")
        self.last_techniques = []
        digits = [int(c) for c in str(n)]
        if len(digits) > self.rods:
            raise OverflowError(f"{n} needs more than {self.rods} rods")
        carry = 0
        for offset in range(self.rods):
            rod = self.rods - 1 - offset
            d = digits[-1 - offset] if offset < len(digits) else 0
            v = self._rods[rod].value()
            technique = self._classify_add(v, d, carry)
            s = v + d + carry
            carry, target = divmod(s, 10)
            self._move_rod(rod, target)
            if technique != "none":
                self.last_techniques.append((rod, technique))
        if carry:
            raise OverflowError("addition carried past the leftmost rod")
        return self.read()

    def subtract(self, n: int) -> int:
        """Subtract ``n`` rod by rod, right to left, using complements."""
        if n < 0:
            raise ValueError("use add for negative amounts")
        if n > self.read():
            raise ValueError("the frame cannot show a negative result")
        self.last_techniques = []
        digits = [int(c) for c in str(n)]
        borrow = 0
        for offset in range(self.rods):
            rod = self.rods - 1 - offset
            d = digits[-1 - offset] if offset < len(digits) else 0
            v = self._rods[rod].value()
            technique = self._classify_sub(v, d, borrow)
            s = v - d - borrow
            borrow = 1 if s < 0 else 0
            self._move_rod(rod, s % 10)
            if technique != "none":
                self.last_techniques.append((rod, technique))
        return self.read()

    # -- seeing the frame ----------------------------------------------------
    def bead_diagram(self) -> str:
        """The frame as text: one row per rod, beads toward the bar.

        Heaven beads render above the bar (``#`` engaged, ``-``
        disengaged), earth beads below (``o`` engaged, ``.``
        disengaged). The rightmost rod is the units column.
        """
        lines = []
        for i, rod in enumerate(self._rods):
            heaven = "".join("#" if k < rod.heaven else "-" for k in range(self.heaven))
            earth = "".join("o" if k < rod.earth else "." for k in range(self.earth))
            lines.append(f"rod{i:>2}: {heaven}|{earth} = {rod.value()}")
        return "\n".join(lines)


@dataclass
class AnzanDrill:
    """Mental-arithmetic practice harness (anzan = "seeing with the mind").

    Presents a sequence of addends as data; the trainee visualizes the
    frame and answers. The harness only checks the answer — the mental
    visualization itself is the trainee's, not the machine's.
    """

    addends: List[int]
    expected: int = field(init=False)

    def __post_init__(self) -> None:
        if not self.addends:
            raise ValueError("a drill needs at least one addend")
        self.expected = sum(self.addends)

    def check(self, answer: int) -> bool:
        """True if the trainee's mental sum matches."""
        return answer == self.expected

    def sequence(self) -> List[int]:
        return list(self.addends)
