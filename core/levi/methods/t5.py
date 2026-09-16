"""Los Alamos T-5 hand-computing pipeline.

History: Los Alamos's T-Division hand-computing group (formalized as T-5
in early 1944): complex implosion simulations were decomposed so finely
that each human computer — mostly scientists' wives recruited from the
townsite — did *one operation*: one multiplied, one added, one cubed,
passing index cards down the line. Hand computing stayed essential at Los
Alamos into the mid-1950s.

In LEVI: decompose complex cognitive work the Los Alamos way — a messy
analysis becomes a pipeline of micro-steps, each too small to botch, with
the assistant executing the mechanical steps and surfacing only the
judgment steps. Every stage's input, operation, and output is inspectable,
like the cards moving down the T-5 line. Each stage may declare an input
*check*; a failed check or a stage error stops the line with full card
history and stage attribution — the pipeline never silently continues
past a bad card.

Honesty: LOAD-BEARING — but note the skepticism from the record: Feynman's
race anecdote (humans keeping pace with IBM punched-card machines for a
day) is told for romance; the machines won on endurance, which is the
point. The transferable method is *decomposition*, not hand computing.

Ephemeral by design: a pipeline run is a session artifact. Use
:meth:`RunReport.to_dict` if you need to persist it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PipelineError(Exception):
    """Base class for pipeline failures."""


class StageCheckError(PipelineError):
    """A stage's input check failed. ``.cards`` holds the history so far."""

    def __init__(self, message: str, cards: list["Card"]):
        super().__init__(message)
        self.cards = cards


class StageRunError(PipelineError):
    """A stage's function raised. ``.stage`` names it; ``.cards`` so far."""

    def __init__(self, message: str, stage: str, cards: list["Card"]):
        super().__init__(message)
        self.stage = stage
        self.cards = cards


# ---------------------------------------------------------------------------
# Cards and stages
# ---------------------------------------------------------------------------


def _short(value: Any, limit: int = 300) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Card:
    """One index card: a stage's input, operation, output, and verdict."""

    stage: str
    input_repr: str
    output_repr: str
    ok: bool
    error: str = ""
    elapsed: float = 0.0


@dataclass
class Stage:
    """One operation on the line: a name, a function, an optional input check."""

    name: str
    func: Callable[[Any], Any]
    check: Callable[[Any], bool] | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("stage name must be non-empty")
        if not callable(self.func):
            raise ValueError(f"stage {self.name!r}: func must be callable")
        if self.check is not None and not callable(self.check):
            raise ValueError(f"stage {self.name!r}: check must be callable")


@dataclass
class RunReport:
    """The completed run: final value plus every intermediate card."""

    pipeline: str
    final: Any
    cards: list[Card] = field(default_factory=list)
    ok: bool = True

    def to_dict(self) -> dict:
        return {
            "pipeline": self.pipeline,
            "ok": self.ok,
            "final_repr": _short(self.final),
            "cards": [vars(c) for c in self.cards],
        }

    def inspect(self) -> list[str]:
        """Human-readable card trace, stage by stage."""
        lines = [f"pipeline: {self.pipeline}"]
        for i, card in enumerate(self.cards, 1):
            status = "ok" if card.ok else f"FAILED: {card.error}"
            lines.append(f"  [{i}] {card.stage}: {status}")
            lines.append(f"      in:  {card.input_repr}")
            lines.append(f"      out: {card.output_repr}")
        return lines


class Pipeline:
    """An assembly line of micro-steps."""

    def __init__(self, name: str, stages: list[Stage]):
        if not name or not name.strip():
            raise ValueError("pipeline name must be non-empty")
        if not stages:
            raise ValueError("pipeline needs at least one stage")
        self.name = name.strip()
        self.stages = list(stages)

    def run(self, initial: Any) -> RunReport:
        """Feed the initial value down the line; return the report."""
        cards: list[Card] = []
        value = initial
        for stage in self.stages:
            if stage.check is not None:
                try:
                    passed = stage.check(value)
                except Exception as exc:  # noqa: BLE001 — check errors are verdicts
                    passed = False
                    check_error = f"{type(exc).__name__}: {exc}"
                else:
                    check_error = "check returned False"
                if not passed:
                    cards.append(
                        Card(stage=stage.name, input_repr=_short(value),
                             output_repr="", ok=False, error=check_error)
                    )
                    raise StageCheckError(
                        f"pipeline {self.name!r}: stage {stage.name!r} rejected "
                        f"its input card ({check_error})",
                        cards,
                    )
            started = time.monotonic()
            try:
                out = stage.func(value)
            except Exception as exc:  # noqa: BLE001 — stage errors get attribution
                elapsed = time.monotonic() - started
                cards.append(
                    Card(stage=stage.name, input_repr=_short(value),
                         output_repr="", ok=False,
                         error=f"{type(exc).__name__}: {exc}", elapsed=elapsed)
                )
                raise StageRunError(
                    f"pipeline {self.name!r}: stage {stage.name!r} failed: {exc}",
                    stage.name,
                    cards,
                ) from exc
            elapsed = time.monotonic() - started
            cards.append(
                Card(stage=stage.name, input_repr=_short(value),
                     output_repr=_short(out), ok=True, elapsed=elapsed)
            )
            value = out
        return RunReport(pipeline=self.name, final=value, cards=cards, ok=True)


def microbatch(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    """Split work into micro-batches — the decomposition aid.

    Each yielded batch is one "card" for one "computer": small enough to
    be too small to get wrong.
    """
    if size < 1:
        raise ValueError("batch size must be >= 1")
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


__all__ = [
    "PipelineError",
    "StageCheckError",
    "StageRunError",
    "Card",
    "Stage",
    "RunReport",
    "Pipeline",
    "microbatch",
]
