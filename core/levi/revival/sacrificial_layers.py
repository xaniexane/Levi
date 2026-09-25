"""sacrificial_layers — spar-coated thatch: renewable sacrificial coats.

Studied from: lost-crafts-20260916 — report.md [Batch 3]
(Thatching — spar coating).

Load-bearing idea: a thatched roof survives weather by *sacrificing* its
surface — hazel spars pin down renewable straw coats; the outer coat
takes the weather and rots so the layers beneath stay seasoned and
dry. New coats are laid over old ones; the coat over the weather-facing
(and highest-churn) slope is replaced most often. LEVI's take: each
domain keeps a stack of ``Coat`` layers. A ``weather()`` pass ages every
coat; ``recoat(domain)`` lays a fresh sacrificial coat pinned over the
seasoned stack. Trimming keeps the stack bounded: the oldest coat is
merged down (its notes fold into the one above) rather than dropped
silently. Read order is always outside-in — the weathered surface first.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/sacrificial-layers"


@dataclass
class Coat:
    """One sacrificial layer. ``age`` counts weather passes survived."""

    label: str
    notes: List[str] = field(default_factory=list)
    laid_at: float = 0.0
    age: int = 0
    sacrificial: bool = True  # the outermost coat is always the sacrifice


class Thatch:
    """Per-domain stacks of sacrificial, renewable coats."""

    def __init__(self, max_coats: int = 5) -> None:
        self.max_coats = max_coats
        self.domains: Dict[str, List[Coat]] = {}  # domain -> coats, outermost first

    # -- laying coats --------------------------------------------------------

    def recoat(self, domain: str, label: str, now: Optional[float] = None) -> Coat:
        """Lay a fresh sacrificial coat over the seasoned stack.

        The previous outer coat stops being sacrificial — it is now
        seasoned fill underneath. Trimming folds the oldest coat's notes
        upward so nothing is dropped silently.
        """
        stack = self.domains.setdefault(domain, [])
        coat = Coat(label=label, laid_at=now if now is not None else time.time())
        for old in stack:
            old.sacrificial = False
        stack.insert(0, coat)
        self._trim(domain)
        return coat

    def write(self, domain: str, note: str) -> Coat:
        """Write a note onto the current sacrificial surface."""
        stack = self.domains.setdefault(domain, [])
        if not stack:
            self.recoat(domain, label="first-coat")
            stack = self.domains[domain]
        stack[0].notes.append(note)
        return stack[0]

    # -- weather ---------------------------------------------------------------

    def weather(self, domain: Optional[str] = None) -> int:
        """One weather pass: every coat ages by one.

        Returns the total coats weathered. The outer coat takes the
        same pass but rots first — modelled by ``erosion``.
        """
        domains = [domain] if domain else list(self.domains)
        count = 0
        for name in domains:
            for coat in self.domains.get(name, []):
                coat.age += 1
                count += 1
        return count

    def erosion(self, domain: str) -> float:
        """0.0 (fresh) to 1.0 (fully rotted) for the sacrificial coat."""
        stack = self.domains.get(domain, [])
        if not stack:
            return 0.0
        outer = stack[0]
        # Heuristic: a coat is spent after max_coats weather passes.
        return min(1.0, outer.age / max(1, self.max_coats))

    # -- reading ----------------------------------------------------------------

    def read(self, domain: str, coats: int = 1) -> List[str]:
        """Read notes outside-in: the weathered surface first."""
        notes: List[str] = []
        for coat in self.domains.get(domain, [])[:coats]:
            notes.extend(coat.notes)
        return notes

    def depth(self, domain: str) -> int:
        return len(self.domains.get(domain, []))

    def seasoned(self, domain: str) -> List[Coat]:
        """The coats beneath the sacrificial surface."""
        return self.domains.get(domain, [])[1:]

    # -- trimming ------------------------------------------------------------------

    def _trim(self, domain: str) -> None:
        stack = self.domains[domain]
        while len(stack) > self.max_coats:
            oldest = stack.pop()
            # Fold the oldest coat's notes into the new oldest so the
            # history compresses instead of vanishing.
            stack[-1].notes.extend(oldest.notes)
