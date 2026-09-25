"""Zwicky's morphological analysis: enumerate the whole box, then prune.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #20)

The mechanism: a "Zwicky box" turns a design problem into a combinatorial
space. Each *dimension* of the problem (power source, housing, control
interface...) gets its possible *values*. The complete solution space is
the cross-product of the dimensions — every full combination is one
candidate solution.

Then cross-consistency assessment (CCA): for each pair of values from
different dimensions, judge whether they can coexist. Impossible pairs
prune every combination containing them, often collapsing millions of
candidates to a handful of genuinely viable ones. The surviving space is
the point: the box forces you to notice solutions hiding between the
obvious ones.

Consistency judgments are simple levels: ``"ok"`` (coexists fine),
``"tension"`` (coexists awkwardly — flagged but kept), ``"no"``
(impossible together — prunes). Unjudged pairs default to ``"ok"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/zwicky"

OK, TENSION, NO = "ok", "tension", "no"
_JUDGMENTS = (OK, TENSION, NO)


def _pair_key(a: Tuple[str, str], b: Tuple[str, str]) -> Tuple[str, str]:
    dim_a, val_a = a
    dim_b, val_b = b
    ka, kb = f"{dim_a}::{val_a}", f"{dim_b}::{val_b}"
    return tuple(sorted((ka, kb)))


@dataclass
class ZwickyBox:
    dimensions: Dict[str, List[str]] = field(default_factory=dict)
    judgments: Dict[Tuple[str, str], str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Building the box
    # ------------------------------------------------------------------
    def add_dimension(self, name: str, values: List[str]) -> None:
        if not name or not name.strip():
            raise ValueError("dimension name must be non-empty")
        if len(values) < 2:
            raise ValueError("a dimension needs at least two values")
        if len(set(values)) != len(values):
            raise ValueError("dimension values must be unique")
        self.dimensions[name] = list(values)

    def judge(
        self, dim_a: str, val_a: str, dim_b: str, val_b: str, judgment: str
    ) -> None:
        """Record a pairwise consistency judgment between two values."""
        if judgment not in _JUDGMENTS:
            raise ValueError(f"judgment must be one of {_JUDGMENTS}")
        if dim_a == dim_b:
            raise ValueError("CCA judges values from different dimensions")
        for dim, val in ((dim_a, val_a), (dim_b, val_b)):
            if dim not in self.dimensions:
                raise ValueError(f"unknown dimension: {dim!r}")
            if val not in self.dimensions[dim]:
                raise ValueError(f"{val!r} is not a value of {dim!r}")
        self.judgments[_pair_key((dim_a, val_a), (dim_b, val_b))] = judgment

    def _judgment(self, combo: Dict[str, str], dim_a: str, dim_b: str) -> str:
        return self.judgments.get(
            _pair_key((dim_a, combo[dim_a]), (dim_b, combo[dim_b])), OK
        )

    # ------------------------------------------------------------------
    # Pruning and enumeration
    # ------------------------------------------------------------------
    def space_size(self) -> int:
        """The raw cross-product size before pruning."""
        size = 1
        for values in self.dimensions.values():
            size *= len(values)
        return size

    def viable(self, drop_tension: bool = False) -> List[Dict[str, str]]:
        """All complete combinations that survive CCA.

        Combinations containing any ``"no"`` pair are pruned. With
        ``drop_tension=True``, combinations containing ``"tension"``
        pairs are also pruned (strict mode).
        """
        if not self.dimensions:
            return []
        dims = list(self.dimensions)
        out = []
        for combo in product(*(self.dimensions[d] for d in dims)):
            solution = dict(zip(dims, combo, strict=True))
            blocked = False
            has_tension = False
            for i, dim_a in enumerate(dims):
                for dim_b in dims[i + 1 :]:
                    j = self._judgment(solution, dim_a, dim_b)
                    if j == NO:
                        blocked = True
                        break
                    if j == TENSION:
                        has_tension = True
                if blocked:
                    break
            if blocked:
                continue
            if drop_tension and has_tension:
                continue
            out.append(solution)
        return out

    def tensions_in(self, solution: Dict[str, str]) -> List[Dict[str, str]]:
        """The awkward pairs inside one surviving solution."""
        dims = list(solution)
        out = []
        for i, dim_a in enumerate(dims):
            for dim_b in dims[i + 1 :]:
                if self._judgment(solution, dim_a, dim_b) == TENSION:
                    out.append(
                        {
                            "dimension_a": dim_a,
                            "value_a": solution[dim_a],
                            "dimension_b": dim_b,
                            "value_b": solution[dim_b],
                        }
                    )
        return out

    def summary(self) -> Dict[str, object]:
        survivors = self.viable()
        return {
            "dimensions": len(self.dimensions),
            "raw_space": self.space_size(),
            "viable": len(survivors),
            "pruned": self.space_size() - len(survivors),
            "judgments_made": len(self.judgments),
        }
