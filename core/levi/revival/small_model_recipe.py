"""small_model_recipe — the overtrain-small playbook, as a planning tool.

Studied from: ai-si-software-internals-20260916-0005/report.md (Part 2) [S2.3].

The studied shape: small models win through *data*, not scale —
training past the compute-optimal token count ("overtraining") on
carefully curated, multi-stage data mixes, refining the mixture rates
per stage. LEVI's version is a recipe planner, not a trainer:

* **Stages.** A ``Stage`` names a training phase with a token budget
  and a data mix: ``{dataset: rate}``. Rates normalize to 1; a stage
  validates (non-negative rates, at least one positive rate).
* **Overtrain factor.** ``Recipe.overtrain_factor()`` compares the
  recipe's total tokens against a reference compute-optimal budget —
  the "how far past optimal" number, reported as a plain ratio with the
  reference stated explicitly so the comparison is honest.
* **Mix refinement.** ``refine_mix(stage, adjustments)`` returns a new
  stage with rates nudged (e.g. up-weighting high-quality data late in
  training) — recipes are immutable; refinement produces a new recipe.
* **Schedule.** ``learning_rate_schedule`` emits a per-stage LR plan
  (warmup then cosine decay to a floor), a common heuristic, labeled as
  such.
* **Sanity checks.** ``validate()`` catches empty mixes, rate sums of
  zero, stages with zero tokens, and LR schedules that rise after decay.

Honest limits: every number here is arithmetic over the recipe the user
declares — nothing is learned, fitted, or guaranteed. The Chinchilla
reference used for the overtrain ratio is a fixed, documented constant
in this module, not a measurement of any real model.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/small_model_recipe"

# Reference constant for the overtrain ratio: tokens per parameter at the
# compute-optimal point per the published Chinchilla analysis. This is a
# documented literature constant, not a measurement made by this module.
CHINCHILLA_TOKENS_PER_PARAM = 20.0


# ---------------------------------------------------------------------------
# Stages and recipes (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """One training phase: token budget + data mix + learning-rate window."""

    name: str
    tokens: int
    mix: Tuple[Tuple[str, float], ...]  # (dataset, rate)
    lr_start: float
    lr_end: float

    def normalized_mix(self) -> Dict[str, float]:
        total = sum(r for _, r in self.mix)
        if total <= 0:
            raise ValueError(f"stage {self.name!r}: mix rates sum to {total}")
        return {d: r / total for d, r in self.mix}

    def tokens_per_dataset(self) -> Dict[str, int]:
        mix = self.normalized_mix()
        return {d: int(round(r * self.tokens)) for d, r in mix.items()}

    def with_adjustments(self, adjustments: Dict[str, float]) -> "Stage":
        """New stage with mix rates nudged by ``adjustments`` (multipliers)."""
        new_mix = tuple((d, max(0.0, r * adjustments.get(d, 1.0))) for d, r in self.mix)
        return Stage(self.name, self.tokens, new_mix, self.lr_start, self.lr_end)


@dataclass(frozen=True)
class Recipe:
    """A full small-model training recipe: ordered stages."""

    name: str
    params: int  # model parameter count, for the overtrain ratio
    stages: Tuple[Stage, ...] = ()

    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.stages)

    def overtrain_factor(self) -> float:
        """Total tokens / reference compute-optimal budget (documented const)."""
        optimal = self.params * CHINCHILLA_TOKENS_PER_PARAM
        return self.total_tokens() / optimal if optimal else 0.0

    def combined_mix(self) -> Dict[str, float]:
        """Token-weighted mix across all stages."""
        totals: Dict[str, int] = {}
        for stage in self.stages:
            for d, t in stage.tokens_per_dataset().items():
                totals[d] = totals.get(d, 0) + t
        grand = sum(totals.values())
        return {d: t / grand for d, t in totals.items()} if grand else {}

    def refine(self, stage_name: str, adjustments: Dict[str, float]) -> "Recipe":
        """New recipe with one stage's mix refined."""
        stages = tuple(
            s.with_adjustments(adjustments) if s.name == stage_name else s
            for s in self.stages
        )
        return Recipe(self.name, self.params, stages)

    def validate(self) -> List[str]:
        """Return a list of problems; empty means the recipe is sane."""
        problems = []
        if self.params <= 0:
            problems.append("params must be positive")
        if not self.stages:
            problems.append("recipe has no stages")
        for s in self.stages:
            if s.tokens <= 0:
                problems.append(f"stage {s.name!r}: tokens must be positive")
            try:
                s.normalized_mix()
            except ValueError as exc:
                problems.append(str(exc))
            if s.lr_start < 0 or s.lr_end < 0:
                problems.append(
                    f"stage {s.name!r}: learning rates must be non-negative"
                )
            if s.lr_end > s.lr_start:
                problems.append(
                    f"stage {s.name!r}: lr_end above lr_start (rises after decay)"
                )
        return problems


# ---------------------------------------------------------------------------
# Learning-rate schedule (heuristic, labeled as such)
# ---------------------------------------------------------------------------


def learning_rate_schedule(
    recipe: Recipe, warmup_tokens: int = 0, steps_per_stage: int = 100
) -> List[Tuple[str, int, float]]:
    """Per-stage LR plan: linear warmup (first stage only), then cosine
    decay from lr_start to lr_end within each stage.

    This is a common heuristic emitted as a plan, not a fitted schedule.
    Returns (stage_name, step_index, lr) rows.
    """
    rows: List[Tuple[str, int, float]] = []
    for si, stage in enumerate(recipe.stages):
        for i in range(steps_per_stage):
            frac = i / max(1, steps_per_stage - 1)
            decayed = stage.lr_end + 0.5 * (stage.lr_start - stage.lr_end) * (
                1 + math.cos(math.pi * frac)
            )
            if si == 0 and warmup_tokens > 0 and i < warmup_tokens:
                lr = stage.lr_start * (i + 1) / warmup_tokens
            else:
                lr = decayed
            rows.append((stage.name, i, lr))
    return rows


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def brief(recipe: Recipe) -> str:
    """One-page human summary of the recipe."""
    lines = [
        f"recipe: {recipe.name}",
        f"params: {recipe.params:,}",
        f"total tokens: {recipe.total_tokens():,}",
        f"overtrain factor: {recipe.overtrain_factor():.2f}x "
        f"(vs {CHINCHILLA_TOKENS_PER_PARAM:.0f} tok/param reference)",
    ]
    for s in recipe.stages:
        mix = ", ".join(f"{d} {r:.0%}" for d, r in s.normalized_mix().items())
        lines.append(
            f"  stage {s.name}: {s.tokens:,} tok | {mix} | "
            f"lr {s.lr_start:g}->{s.lr_end:g}"
        )
    return "\n".join(lines)
