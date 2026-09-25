"""Graded single-new-variable curriculum; learning decoupled from production.

Studied from: lost-crafts-20260916/report.md [Batch 1] (Sloyd: a graded
curriculum where each exercise introduces exactly one new variable — one new
tool, material, or technique — so difficulty is isolated and diagnosable, and
learning is decoupled from production work).

This is an original, from-scratch implementation for LEVI. A ``Curriculum``
is an ordered sequence of ``Exercise``s, each naming the set of
variables (tools, materials, techniques) it uses. The builder enforces the
single-new-variable rule: the first exercise establishes the baseline set,
and every later exercise may introduce at most one variable not seen in any
earlier exercise, using only variables already introduced (plus its one new
one). A learner ``Progress`` log records
attempts per exercise with an outcome; the curriculum can report the next
exercise, diagnose which variable a repeated failure implicates (the newest
variable of the failing exercise), and certify completion only when every
exercise is passed. Production work is explicitly out of scope — attempts are
recorded as *practice*, never as output.

Public surface:
- ``Curriculum``: ``add_exercise(name, variables)``, ``exercises``,
  ``validate()``, ``diagnose(progress)``.
- ``Progress``: ``attempt(exercise, passed, note)``, ``next_up()``,
  ``complete()``, ``mastery(variable)``.
- ``CurriculumError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence, Set

ORIGIN = "levi-revival/sloyd-curriculum"


class CurriculumError(ValueError):
    """Raised when the single-new-variable rule is broken."""


@dataclass(frozen=True)
class Exercise:
    name: str
    variables: FrozenSet[str]
    new_variable: Optional[str]

    def __post_init__(self) -> None:
        if not self.name:
            raise CurriculumError("exercise name must be non-empty")


@dataclass
class Attempt:
    exercise: str
    passed: bool
    note: str = ""


class Curriculum:
    """An ordered, validated single-new-variable exercise sequence."""

    def __init__(self, title: str) -> None:
        if not title:
            raise CurriculumError("curriculum title must be non-empty")
        self.title = title
        self._exercises: List[Exercise] = []

    def add_exercise(self, name: str, variables: Sequence[str]) -> Exercise:
        """Add an exercise; enforces the single-new-variable rule against
        everything added so far. The first exercise establishes the baseline
        set (it may name several variables); every later exercise may
        introduce at most one new variable."""
        varset = frozenset(variables)
        if not varset:
            raise CurriculumError("an exercise must use at least one variable")
        if any(ex.name == name for ex in self._exercises):
            raise CurriculumError(f"duplicate exercise name {name!r}")
        seen: Set[str] = set()
        for ex in self._exercises:
            seen |= set(ex.variables)
        new_vars = varset - seen
        if self._exercises and len(new_vars) > 1:
            raise CurriculumError(
                f"exercise {name!r} introduces {len(new_vars)} new variables "
                f"{sorted(new_vars)}; at most one is allowed"
            )
        exercise = Exercise(
            name=name,
            variables=varset,
            new_variable=next(iter(new_vars)) if new_vars else None,
        )
        self._exercises.append(exercise)
        return exercise

    @property
    def exercises(self) -> List[Exercise]:
        return list(self._exercises)

    def introduced(self) -> List[str]:
        """The new variable of each exercise, in order (None = pure review)."""
        return [ex.new_variable for ex in self._exercises]

    def validate(self) -> List[str]:
        """Re-check the whole sequence; returns a list of violations (empty = valid).
        The first exercise sets the baseline; later ones may add at most one."""
        problems: List[str] = []
        seen: Set[str] = set()
        first = True
        for ex in self._exercises:
            new_vars = set(ex.variables) - seen
            if not first and len(new_vars) > 1:
                problems.append(f"{ex.name!r}: introduces {sorted(new_vars)} at once")
            first = False
            seen |= set(ex.variables)
        return problems


class Progress:
    """A learner's practice log against a curriculum. Practice, not production."""

    def __init__(self, learner: str, curriculum: Curriculum) -> None:
        if not learner:
            raise CurriculumError("learner must be named")
        self.learner = learner
        self.curriculum = curriculum
        self._attempts: List[Attempt] = []
        self._passed: Set[str] = set()

    def attempt(self, exercise_name: str, passed: bool, note: str = "") -> Attempt:
        names = [ex.name for ex in self.curriculum.exercises]
        if exercise_name not in names:
            raise CurriculumError(f"no such exercise {exercise_name!r}")
        attempt = Attempt(exercise=exercise_name, passed=passed, note=note)
        self._attempts.append(attempt)
        if passed:
            self._passed.add(exercise_name)
        return attempt

    def next_up(self) -> Optional[Exercise]:
        """The first exercise not yet passed, in curriculum order."""
        for ex in self.curriculum.exercises:
            if ex.name not in self._passed:
                return ex
        return None

    def complete(self) -> bool:
        return self.next_up() is None

    def failures_on(self, exercise_name: str) -> int:
        return sum(
            1 for a in self._attempts if a.exercise == exercise_name and not a.passed
        )

    def diagnose(self, exercise_name: str) -> str:
        """Which variable a repeated failure implicates: the exercise's newest
        variable, or a prerequisite if the new variable is already mastered."""
        exercise = next(
            (ex for ex in self.curriculum.exercises if ex.name == exercise_name), None
        )
        if exercise is None:
            raise CurriculumError(f"no such exercise {exercise_name!r}")
        fails = self.failures_on(exercise_name)
        if fails == 0:
            return f"{exercise_name!r}: no failures recorded"
        new_var = exercise.new_variable
        if new_var is not None:
            return (
                f"{exercise_name!r}: {fails} failure(s); suspect the new variable "
                f"{new_var!r} — isolate and drill it before retrying"
            )
        return (
            f"{exercise_name!r}: {fails} failure(s) on a review exercise; "
            "suspect a prerequisite variable — walk back to the exercise that "
            "introduced each variable and re-check"
        )

    def mastery(self, variable: str) -> float:
        """Fraction of passed exercises that use this variable (0.0..1.0)."""
        relevant = [ex for ex in self.curriculum.exercises if variable in ex.variables]
        if not relevant:
            return 0.0
        passed = sum(1 for ex in relevant if ex.name in self._passed)
        return passed / len(relevant)

    def attempts(self) -> List[Attempt]:
        return list(self._attempts)
