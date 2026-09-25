"""mixplan — small-model data-mix planner + curation loop.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.3, §2.8).

The published small-model lesson, stated plainly: at small scale the
data mix *is* the model quality — architecture is ~10%, data plumbing
and eval-driven iteration ~90%. The recipe this module encodes:

* **Multi-stage mixing**: training runs in stages (general web →
  math/code → instruction), each stage with its own mixing rates over
  data slices. Never one undifferentiated pile.
* **Per-stage eval hooks**: after each stage, cheap proxy evals score
  what the stage bought. The hooks are injected callables — this module
  plans; it never trains.
* **Ablate-and-refine**: mixing rates are adjusted from eval scores —
  slices whose presence correlates with better evals get more weight,
  the rest get less. Iterate until the rates settle or the iteration
  budget runs out.
* **Aggressive dedup**: exact and near-duplicate removal before any
  mixing decision, because duplicated data silently eats the token
  budget and biases the mix.
* **Targeted-dataset gap detector**: slices that are low-quality or
  thin get flagged as needing purpose-built data — the published move
  is to *create* the dataset you wish existed rather than drown the mix
  in more of the same.

This is a planning tool. It is runnable: give it slices, stages, and
eval hooks, and it returns a refined plan plus the reasoning. It never
touches a real training run.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

ORIGIN = "levi-revival/mixplan"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DataSlice:
    """One named slice of the training corpus."""

    name: str
    tokens: int  # token count in this slice
    quality: float  # 0..1 prior quality score
    tags: List[str] = field(default_factory=list)


@dataclass
class Stage:
    """One curriculum stage: name, mixing rates, eval hooks."""

    name: str
    mix: Dict[str, float]  # slice name -> rate (need not sum to 1)
    eval_hooks: List[Callable[[Dict[str, float]], float]] = field(default_factory=list)

    def normalized(self) -> Dict[str, float]:
        total = sum(self.mix.values()) or 1.0
        return {k: v / total for k, v in self.mix.items()}


@dataclass
class StageReport:
    stage: str
    mix: Dict[str, float]
    eval_scores: List[float]
    mean_score: float
    token_budget: int


# ---------------------------------------------------------------------------
# The planner
# ---------------------------------------------------------------------------


class MixPlanner:
    """Multi-stage data-mix planner with an ablate-and-refine loop."""

    def __init__(
        self,
        slices: List[DataSlice],
        stages: List[Stage],
        learning_rate: float = 0.25,
        max_iters: int = 12,
        tolerance: float = 1e-3,
    ) -> None:
        self.slices = {s.name: s for s in slices}
        self.stages = stages
        self.lr = learning_rate
        self.max_iters = max_iters
        self.tolerance = tolerance
        self.history: List[StageReport] = []

    # -- evaluation ---------------------------------------------------------

    def evaluate(self, stage: Stage) -> StageReport:
        """Run a stage's eval hooks against its current mix."""
        mix = stage.normalized()
        scores = [hook(mix) for hook in stage.eval_hooks]
        mean = sum(scores) / len(scores) if scores else 0.0
        budget = sum(self.slices[name].tokens for name in mix if name in self.slices)
        report = StageReport(
            stage=stage.name,
            mix=dict(mix),
            eval_scores=scores,
            mean_score=mean,
            token_budget=budget,
        )
        self.history.append(report)
        return report

    # -- ablate-and-refine ----------------------------------------------------

    def _slice_marginal(self, stage: Stage, slice_name: str) -> float:
        """Ablation: how much does the stage's eval suffer without this slice?

        Positive = the slice earns its place. Computed by zeroing the
        slice's rate and re-running the hooks — cheap, because hooks are
        proxies, not training runs.
        """
        base = self.evaluate_quiet(stage)
        ablated_mix = {k: (0.0 if k == slice_name else v) for k, v in stage.mix.items()}
        probe = Stage(name=stage.name, mix=ablated_mix, eval_hooks=stage.eval_hooks)
        ablated = self.evaluate_quiet(probe)
        return base - ablated

    def evaluate_quiet(self, stage: Stage) -> float:
        mix = stage.normalized()
        scores = [hook(mix) for hook in stage.eval_hooks]
        return sum(scores) / len(scores) if scores else 0.0

    def refine_stage(self, stage: Stage) -> Stage:
        """Adjust one stage's mixing rates from ablation marginals.

        Slices with positive marginal gain weight; slices that hurt get
        cut. Multiplicative update, then renormalize implicitly at use.
        """
        marginals = {name: self._slice_marginal(stage, name) for name in stage.mix}
        mean = sum(marginals.values()) / len(marginals) if marginals else 0.0
        new_mix = {}
        for name, rate in stage.mix.items():
            new_mix[name] = max(0.0, rate * (1.0 + self.lr * (marginals[name] - mean)))
        # Keep at least a trickle so no slice is ever fully starved.
        floor = 0.01
        new_mix = {k: max(floor, v) for k, v in new_mix.items()}
        return Stage(name=stage.name, mix=new_mix, eval_hooks=stage.eval_hooks)

    def run(self) -> List[Stage]:
        """Refine every stage until rates settle or the budget runs out."""
        refined: List[Stage] = []
        for stage in self.stages:
            current = stage
            for _ in range(self.max_iters):
                nxt = self.refine_stage(current)
                shift = max(abs(nxt.mix[k] - current.mix.get(k, 0.0)) for k in nxt.mix)
                current = nxt
                if shift < self.tolerance:
                    break
            self.evaluate(current)
            refined.append(current)
        return refined

    def plan_summary(self) -> List[Dict[str, object]]:
        """Human-readable plan: stage -> top slices by rate."""
        out = []
        for stage in self.stages:
            ranked = sorted(
                stage.normalized().items(), key=lambda kv: kv[1], reverse=True
            )
            out.append({"stage": stage.name, "mix": ranked})
        return out


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def aggressive_dedup(
    documents: List[str], near_dup_threshold: float = 0.9
) -> Tuple[List[str], Dict[str, int]]:
    """Exact + near-duplicate removal. Returns (kept, stats).

    Near-dup: Jaccard similarity over word shingles above the threshold
    counts as a duplicate of the earlier document. Aggressive on
    purpose — duplicated data silently eats the token budget.
    """
    kept: List[str] = []
    kept_shingles: List[frozenset] = []
    exact_dups = 0
    near_dups = 0
    seen_exact = set()
    for doc in documents:
        norm = _normalize(doc)
        if norm in seen_exact:
            exact_dups += 1
            continue
        words = norm.split()
        shingles = frozenset(
            tuple(words[i : i + 5]) for i in range(max(1, len(words) - 4))
        )
        is_near = False
        for prev in kept_shingles:
            union = shingles | prev
            if not union:
                continue
            jaccard = len(shingles & prev) / len(union)
            if jaccard >= near_dup_threshold:
                is_near = True
                break
        if is_near:
            near_dups += 1
            continue
        seen_exact.add(norm)
        kept.append(doc)
        kept_shingles.append(shingles)
    return kept, {"kept": len(kept), "exact_dups": exact_dups, "near_dups": near_dups}


# ---------------------------------------------------------------------------
# Gap detector: where to build targeted datasets
# ---------------------------------------------------------------------------


@dataclass
class DataGap:
    slice_name: str
    reason: str
    quality: float
    tokens: int


def find_gaps(
    slices: List[DataSlice],
    quality_floor: float = 0.5,
    token_floor: int = 10_000,
) -> List[DataGap]:
    """Flag slices needing purpose-built targeted datasets.

    A slice is a gap when it is low-quality (needs curation/replacement)
    or thin (needs *creation* — the published move is to build the
    dataset you wish existed rather than dilute the mix further).
    """
    gaps: List[DataGap] = []
    for s in slices:
        if s.quality < quality_floor:
            gaps.append(
                DataGap(
                    slice_name=s.name,
                    reason="low-quality: curate or replace with a purpose-built set",
                    quality=s.quality,
                    tokens=s.tokens,
                )
            )
        elif s.tokens < token_floor:
            gaps.append(
                DataGap(
                    slice_name=s.name,
                    reason="thin: create a targeted dataset; do not dilute the mix",
                    quality=s.quality,
                    tokens=s.tokens,
                )
            )
    return sorted(gaps, key=lambda g: (g.quality, g.tokens))


# ---------------------------------------------------------------------------
# Demo eval hook: quality-weighted coverage proxy
# ---------------------------------------------------------------------------


def quality_coverage_hook(
    slices: Dict[str, DataSlice],
) -> Callable[[Dict[str, float]], float]:
    """Build a proxy eval: expected quality under the mix.

    A stand-in for real evals — the planner only needs *a* score that
    moves when the mix moves. Real deployments wire in benchmark hooks.
    """

    def hook(mix: Dict[str, float]) -> float:
        total = sum(mix.values()) or 1.0
        return sum(
            (rate / total) * slices[name].quality
            for name, rate in mix.items()
            if name in slices
        )

    return hook
