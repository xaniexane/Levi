"""Sloyd: craft as graded character curriculum.

Origin: Sloyd (Swedish slojd, handicraft) made woodworking, sewing, and
paper-folding a compulsory school subject — not to produce goods but
to form the child. The mechanism was a graded single-new-variable
curriculum: sequenced model exercises of increasing difficulty, each
introducing exactly one new skill, with individualized instruction and
child-sized tools. The goal was decoupled from production — what
mattered was the capacities built during making, not the object.

What it is in LEVI: ``GradedCurriculum`` — an ordered sequence of
exercises, each declaring exactly one new variable (a second new
variable is refused at definition time). ``LearnerProgress`` tracks one
learner's pacing: an exercise may only be attempted once every earlier
exercise is complete, and only completed once attempted. Pacing is
per-learner; the prerequisite chain is not.

Honesty label: LOAD-BEARING — single-new-variable exercises with a
hard prerequisite chain is a concrete, transferable mechanism.

Deny-closed inputs: empty exercise / learner names, exercises declaring
anything other than exactly one new variable, empty variable names,
duplicate exercise ids, unknown exercise ids, attempting an exercise
whose prerequisites are incomplete, attempting an already attempted or
completed exercise, and completing an exercise that was never attempted
or already completed are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Exercise", "GradedCurriculum", "LearnerProgress"]


@dataclass
class Exercise:
    """One model exercise: exactly one new variable, never two."""

    id: str
    name: str
    new_variables: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("exercise name must be a non-empty string")
        self.name = self.name.strip()
        if len(self.new_variables) != 1:
            raise ValueError(
                f"sloyd rule: each exercise introduces exactly one new "
                f"variable, got {len(self.new_variables)}"
            )
        var = self.new_variables[0]
        if not isinstance(var, str) or not var.strip():
            raise ValueError("the new variable must be a non-empty string")
        self.new_variables = (var.strip(),)


class GradedCurriculum:
    """The graded sequence: exercises in increasing difficulty, each
    building on every exercise before it."""

    def __init__(self, title: str):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("curriculum title must be a non-empty string")
        self.title = title.strip()
        self._exercises: list[Exercise] = []

    def add_exercise(
        self, exercise_id: str, name: str, new_variables: tuple[str, ...] | list[str]
    ) -> Exercise:
        """Append the next exercise in the graded sequence."""
        if not isinstance(exercise_id, str) or not exercise_id.strip():
            raise ValueError("exercise id must be a non-empty string")
        exercise_id = exercise_id.strip()
        if any(e.id == exercise_id for e in self._exercises):
            raise ValueError(f"duplicate exercise id: {exercise_id!r}")
        if not isinstance(new_variables, (tuple, list)):
            raise ValueError("new_variables must be a tuple or list of strings")
        exercise = Exercise(
            id=exercise_id, name=name, new_variables=tuple(new_variables)
        )
        self._exercises.append(exercise)
        return exercise

    def exercise(self, exercise_id: str) -> Exercise:
        for e in self._exercises:
            if e.id == exercise_id:
                return e
        raise ValueError(f"unknown exercise: {exercise_id!r}")

    def prerequisites(self, exercise_id: str) -> list[Exercise]:
        """Every exercise before this one in the sequence."""
        idx = next(
            (i for i, e in enumerate(self._exercises) if e.id == exercise_id), None
        )
        if idx is None:
            raise ValueError(f"unknown exercise: {exercise_id!r}")
        return self._exercises[:idx]

    def learner(self, name: str) -> "LearnerProgress":
        return LearnerProgress(curriculum=self, learner=name)


class LearnerProgress:
    """One learner's individualized pacing through the fixed sequence."""

    def __init__(self, curriculum: GradedCurriculum, learner: str):
        if not isinstance(learner, str) or not learner.strip():
            raise ValueError("learner name must be a non-empty string")
        self.curriculum = curriculum
        self.learner = learner.strip()
        self._attempted: set[str] = set()
        self._completed: set[str] = set()

    def attempt(self, exercise_id: str) -> Exercise:
        """Take up an exercise. Refused unless every prerequisite
        exercise is complete — the chain is the curriculum."""
        exercise = self.curriculum.exercise(exercise_id)
        if exercise_id in self._completed:
            raise ValueError(f"exercise {exercise_id!r} already completed")
        if exercise_id in self._attempted:
            raise ValueError(f"exercise {exercise_id!r} already attempted")
        missing = [
            p.id
            for p in self.curriculum.prerequisites(exercise_id)
            if p.id not in self._completed
        ]
        if missing:
            raise ValueError(
                f"prerequisites incomplete for {exercise_id!r}: still missing {missing}"
            )
        self._attempted.add(exercise_id)
        return exercise

    def complete(self, exercise_id: str) -> Exercise:
        """Finish an attempted exercise. The object is not the point —
        the capacity built is; the chain records it either way."""
        exercise = self.curriculum.exercise(exercise_id)
        if exercise_id in self._completed:
            raise ValueError(f"exercise {exercise_id!r} already completed")
        if exercise_id not in self._attempted:
            raise ValueError(f"cannot complete {exercise_id!r}: attempt it first")
        self._completed.add(exercise_id)
        return exercise

    def progress(self) -> dict:
        order = [e.id for e in self.curriculum._exercises]
        return {
            "learner": self.learner,
            "attempted": sorted(self._attempted, key=order.index),
            "completed": sorted(self._completed, key=order.index),
            "remaining": [i for i in order if i not in self._completed],
        }
