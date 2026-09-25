"""Trivium pipeline — a sequenced abstraction ladder for learning.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #26).

The mechanism under study: mastery is built in ordered stages — the
*trivium* (grammar: vocabulary and facts; logic: argument structure;
rhetoric: teach it back) followed by the *quadrivium* (quantification
and measurement). Each stage gates the next: you cannot argue without
vocabulary, cannot teach what you have not structured, cannot measure
what you cannot articulate.

This is an original, from-scratch implementation for LEVI. A learning
artifact carries its own captured vocabulary, constructed arguments,
teach-back transcripts, and measurements. Stage transitions are guarded:
advancing requires the stage's completion criteria to be met, and the
system refuses to let you skip ahead — the pipeline enforces the order
grammar -> logic -> rhetoric -> measure.

Public surface:
- ``Stage``: GRAMMAR, LOGIC, RHETORIC, MEASURE — the ordered stages.
- ``Artifact``: the learning record; ``capture_term``,
  ``add_premise``, ``build_argument``, ``teach_back``, ``record_measure``.
- ``GateError``: raised when a stage's gate is closed (skipped or
  incomplete).

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

ORIGIN = "levi-revival/trivium"


class GateError(Exception):
    """A stage gate refused the transition: earlier work is incomplete."""


class Stage(Enum):
    """The ordered abstraction ladder."""

    GRAMMAR = auto()  # vocabulary and facts
    LOGIC = auto()  # argument construction
    RHETORIC = auto()  # teach-back
    MEASURE = auto()  # quantification
    COMPLETE = auto()  # pipeline finished


@dataclass
class Term:
    word: str
    definition: str


@dataclass
class Argument:
    conclusion: str
    premises: List[str] = field(default_factory=list)


@dataclass
class TeachBack:
    text: str
    terms_used: List[str] = field(default_factory=list)
    conclusion_covered: bool = False


@dataclass
class Measure:
    name: str
    value: float
    unit: str = ""


@dataclass
class Artifact:
    """A learning artifact moving through the trivium pipeline."""

    topic: str
    stage: Stage = Stage.GRAMMAR
    vocabulary: Dict[str, Term] = field(default_factory=dict)
    argument: Optional[Argument] = None
    teachback: Optional[TeachBack] = None
    measures: List[Measure] = field(default_factory=list)
    log: List[str] = field(default_factory=list)

    # -- grammar ------------------------------------------------------
    def capture_term(self, word: str, definition: str) -> None:
        """Grammar: capture one vocabulary term (vocabulary capture)."""
        if self.stage is not Stage.GRAMMAR:
            raise GateError(
                f"capture_term belongs to GRAMMAR; artifact is at {self.stage.name}"
            )
        word = word.strip()
        if not word or not definition.strip():
            raise GateError("grammar requires a non-empty word and definition")
        self.vocabulary[word] = Term(word, definition.strip())
        self.log.append(f"grammar: captured term '{word}'")

    def complete_grammar(self, min_terms: int = 3) -> None:
        """Advance past grammar when enough vocabulary is captured."""
        if self.stage is not Stage.GRAMMAR:
            raise GateError(f"artifact is at {self.stage.name}, not GRAMMAR")
        if len(self.vocabulary) < min_terms:
            raise GateError(
                f"grammar gate closed: {len(self.vocabulary)} terms captured, "
                f"{min_terms} required before logic"
            )
        self.stage = Stage.LOGIC
        self.log.append(f"grammar complete ({len(self.vocabulary)} terms) -> LOGIC")

    # -- logic --------------------------------------------------------
    def add_premise(self, premise: str) -> None:
        """Logic: add a premise built from captured vocabulary."""
        if self.stage is not Stage.LOGIC:
            raise GateError(
                f"add_premise belongs to LOGIC; artifact is at {self.stage.name}"
            )
        premise = premise.strip()
        if not premise:
            raise GateError("logic requires a non-empty premise")
        if self.argument is None:
            self.argument = Argument(conclusion="")
        self.argument.premises.append(premise)
        self.log.append("logic: added premise")

    def build_argument(self, conclusion: str, min_premises: int = 2) -> Argument:
        """Logic: lock the argument once enough premises are assembled."""
        if self.stage is not Stage.LOGIC:
            raise GateError(
                f"build_argument belongs to LOGIC; artifact is at {self.stage.name}"
            )
        if self.argument is None or len(self.argument.premises) < min_premises:
            got = len(self.argument.premises) if self.argument else 0
            raise GateError(
                f"logic gate closed: {got} premises assembled, "
                f"{min_premises} required before rhetoric"
            )
        if not conclusion.strip():
            raise GateError("logic requires a conclusion")
        self.argument.conclusion = conclusion.strip()
        self.stage = Stage.RHETORIC
        self.log.append(
            f"logic complete ({len(self.argument.premises)} premises) -> RHETORIC"
        )
        return self.argument

    # -- rhetoric -----------------------------------------------------
    def teach_back(self, text: str) -> TeachBack:
        """Rhetoric: teach the topic back; the pipeline cross-examines."""
        if self.stage is not Stage.RHETORIC:
            raise GateError(
                f"teach_back belongs to RHETORIC; artifact is at {self.stage.name}"
            )
        if not text.strip():
            raise GateError("rhetoric requires a teach-back transcript")
        lowered = text.lower()
        terms_used = [w for w in self.vocabulary if w.lower() in lowered]
        conclusion_covered = bool(
            self.argument
            and self.argument.conclusion
            and any(
                tok in lowered
                for tok in self.argument.conclusion.lower().split()
                if len(tok) > 3
            )
        )
        self.teachback = TeachBack(text.strip(), terms_used, conclusion_covered)
        self.log.append(
            f"rhetoric: teach-back used {len(terms_used)}/{len(self.vocabulary)} terms, "
            f"conclusion covered: {conclusion_covered}"
        )
        return self.teachback

    def complete_rhetoric(self, min_term_coverage: float = 0.5) -> None:
        """Advance past rhetoric when the teach-back demonstrates ownership."""
        if self.stage is not Stage.RHETORIC:
            raise GateError(f"artifact is at {self.stage.name}, not RHETORIC")
        if self.teachback is None:
            raise GateError("rhetoric gate closed: no teach-back attempted")
        coverage = len(self.teachback.terms_used) / max(1, len(self.vocabulary))
        if coverage < min_term_coverage:
            raise GateError(
                f"rhetoric gate closed: term coverage {coverage:.0%}, "
                f"{min_term_coverage:.0%} required before measure"
            )
        if not self.teachback.conclusion_covered:
            raise GateError(
                "rhetoric gate closed: teach-back never touched the argument's conclusion"
            )
        self.stage = Stage.MEASURE
        self.log.append("rhetoric complete (teach-back held) -> MEASURE")

    # -- measure (quadrivium) -----------------------------------------
    def record_measure(self, name: str, value: float, unit: str = "") -> Measure:
        """Quantification: measure something about the topic."""
        if self.stage is not Stage.MEASURE:
            raise GateError(
                f"record_measure belongs to MEASURE; artifact is at {self.stage.name}"
            )
        if not name.strip():
            raise GateError("measure requires a name")
        measure = Measure(name.strip(), float(value), unit)
        self.measures.append(measure)
        self.log.append(f"measure: {name} = {value}{unit}")
        return measure

    def complete(self, min_measures: int = 1) -> None:
        """Finish the pipeline once quantification exists."""
        if self.stage is not Stage.MEASURE:
            raise GateError(f"artifact is at {self.stage.name}, not MEASURE")
        if len(self.measures) < min_measures:
            raise GateError(
                f"measure gate closed: {len(self.measures)} measures, "
                f"{min_measures} required to complete"
            )
        self.stage = Stage.COMPLETE
        self.log.append("measure complete -> COMPLETE")

    # -- status -------------------------------------------------------
    def status(self) -> Dict[str, object]:
        """Snapshot of where the artifact stands in the pipeline."""
        return {
            "topic": self.topic,
            "stage": self.stage.name,
            "terms": len(self.vocabulary),
            "premises": len(self.argument.premises) if self.argument else 0,
            "conclusion": bool(self.argument and self.argument.conclusion),
            "teachback": self.teachback is not None,
            "measures": [f"{m.name}={m.value}{m.unit}" for m in self.measures],
        }
