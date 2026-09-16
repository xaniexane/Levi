"""Zwicky's morphological analysis: the morphological box with pruning.

Origin: astrophysicist Fritz Zwicky's method for "non-quantifiable"
problems. Define the problem's dimensions (parameters) and list every
possible value for each — the *morphological box*. Enumerate the
combinations, then apply **cross-consistency assessment**: strike every
pair of values that cannot coexist. What survives is the complete space of
viable solutions — including ones nobody would have thought of.

What it is in LEVI: exhaustive option generation with AI-speed pruning.
The box kills availability bias (you *see* that every combination was
considered); pairwise consistency-checking is the tractable substitute for
judging whole configurations. The assistant does the combinatorial
bookkeeping and conducts the consistency interview; you supply the judgment
about which pairs can coexist.

Honesty label: LOAD-BEARING — exhaustion plus pairwise pruning is a
concrete, transferable mechanism.

Deny-closed inputs: empty parameters/values, duplicates, incompatibility
rules referencing unknown parameters or values, and combination spaces
beyond the safety cap are rejected — the box refuses to silently truncate
an "exhaustive" enumeration.
"""

from __future__ import annotations

from itertools import product
from math import prod
from typing import Iterator

__all__ = ["MorphologicalBox", "MAX_COMBINATIONS"]

# Fail-closed ceiling: beyond this, "exhaustive" enumeration is refused
# rather than silently sampled. Narrow the box or pass allow_large=True
# explicitly (documenting that you accept the cost).
MAX_COMBINATIONS = 200_000


class MorphologicalBox:
    """Parameter x value box with cross-consistency assessment."""

    def __init__(self, problem: str = ""):
        if not isinstance(problem, str):
            raise ValueError("problem must be a string")
        self.problem = problem
        self.parameters: dict[str, list[str]] = {}  # name -> values (ordered)
        self._forbidden: list[tuple[str, str, str, str, str]] = []
        # (param_a, value_a, param_b, value_b, reason)

    # -- building the box ------------------------------------------------------
    @staticmethod
    def _clean(value: str, kind: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{kind} must be a non-empty string")
        return value.strip()

    def add_parameter(self, name: str, values: list[str]) -> None:
        """Add a dimension and its possible values (at least 2)."""
        name = self._clean(name, "parameter name")
        if name in self.parameters:
            raise ValueError(f"duplicate parameter: {name!r}")
        cleaned = [self._clean(v, "parameter value") for v in values]
        if len(cleaned) < 2:
            raise ValueError(f"parameter {name!r} needs at least 2 values")
        if len({v.lower() for v in cleaned}) != len(cleaned):
            raise ValueError(f"parameter {name!r} has duplicate values")
        self.parameters[name] = cleaned

    def forbid(
        self,
        param_a: str,
        value_a: str,
        param_b: str,
        value_b: str,
        reason: str = "",
    ) -> None:
        """Cross-consistency assessment: these two values cannot coexist.

        The rule is symmetric and applies to every combination containing
        the pair. Judgment call — record the reason.
        """
        for p, v in ((param_a, value_a), (param_b, value_b)):
            if p not in self.parameters:
                raise ValueError(f"unknown parameter: {p!r}")
            if v not in self.parameters[p]:
                raise ValueError(f"unknown value {v!r} for parameter {p!r}")
        if param_a == param_b:
            raise ValueError("a consistency rule needs two different parameters")
        pair = tuple(sorted([(param_a, value_a), (param_b, value_b)]))
        for r in self._forbidden:
            existing = tuple(sorted([(r[0], r[1]), (r[2], r[3])]))
            if existing == pair:
                raise ValueError("duplicate consistency rule")
        self._forbidden.append((param_a, value_a, param_b, value_b, reason or ""))

    # -- enumeration & pruning ---------------------------------------------------
    def count(self) -> int:
        """Size of the full combinatorial space."""
        if not self.parameters:
            return 0
        return prod(len(v) for v in self.parameters.values())

    def _check_size(self, allow_large: bool) -> None:
        n = self.count()
        if n == 0:
            raise ValueError("the box is empty: add parameters first")
        if n > MAX_COMBINATIONS and not allow_large:
            raise ValueError(
                f"combination space is {n:,} (cap {MAX_COMBINATIONS:,}); "
                "narrow the box, add consistency rules first, or pass "
                "allow_large=True to accept the cost explicitly"
            )

    def _consistent(self, combo: dict[str, str]) -> bool:
        for pa, va, pb, vb, _ in self._forbidden:
            if combo.get(pa) == va and combo.get(pb) == vb:
                return False
        return True

    def enumerate(self, allow_large: bool = False) -> Iterator[dict[str, str]]:
        """Lazily yield every combination (fails closed past the cap)."""
        self._check_size(allow_large)
        names = list(self.parameters)
        for values in product(*(self.parameters[n] for n in names)):
            yield dict(zip(names, values))

    def survivors(self, allow_large: bool = False) -> list[dict[str, str]]:
        """Every combination that passes cross-consistency assessment."""
        return [
            c for c in self.enumerate(allow_large=allow_large) if self._consistent(c)
        ]

    def prune_report(self, allow_large: bool = False) -> dict:
        """The method's honesty made visible: what was considered, struck, kept."""
        total = self.count()
        self._check_size(allow_large)
        kept = self.survivors(allow_large=allow_large)
        struck_by_rule: dict[str, int] = {}
        names = list(self.parameters)
        for values in product(*(self.parameters[n] for n in names)):
            combo = dict(zip(names, values))
            for pa, va, pb, vb, reason in self._forbidden:
                if combo.get(pa) == va and combo.get(pb) == vb:
                    key = f"{pa}={va} x {pb}={vb}" + (f" ({reason})" if reason else "")
                    struck_by_rule[key] = struck_by_rule.get(key, 0) + 1
                    break
        return {
            "problem": self.problem,
            "parameters": len(self.parameters),
            "total_combinations": total,
            "consistency_rules": len(self._forbidden),
            "struck": total - len(kept),
            "survivors": len(kept),
            "struck_by_rule": struck_by_rule,
        }
