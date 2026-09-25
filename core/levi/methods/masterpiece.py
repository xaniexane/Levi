"""The Chef-d'oeuvre: masterpiece as master-craft gate.

Origin: a journeyman seeking master status had to produce a qualifying
masterpiece demonstrating the full abilities of an aspiring master —
material choice, technique, finishing — judged by the guild's own
masters (often with a cash donation attached), and the piece was
usually retained by the guild. The credential was a public,
peer-judged performance: evaluated by practitioners of the craft
rather than by credential-issuers.

What it is in LEVI: ``MasterpieceGate`` — submit work to a jury of
practitioners who score it against a rubric. A unanimous-threshold
verdict (every rubric criterion at or above its bar, scored by the
full jury) admits the piece to the corpus; the retained corpus becomes
the reference standard against which future submissions are judged.

Honesty label: LOAD-BEARING — peer-jury verdict + accumulating
reference corpus is a concrete, transferable mechanism.

Deny-closed inputs: empty author/title/juror names, duplicate jurors,
duplicate submissions, scoring before a rubric is set, unknown juror /
submission / criterion ids, scores outside 0..10, a juror scoring the
same criterion twice, rubric thresholds outside 0..10, a verdict before
the full jury has scored every criterion, and a second verdict on the
same submission are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Submission", "MasterpieceGate", "MIN_SCORE", "MAX_SCORE"]

MIN_SCORE = 0.0
MAX_SCORE = 10.0


@dataclass
class Submission:
    id: str
    author: str
    title: str
    verdict: str = "pending"  # pending | admitted | rejected


class MasterpieceGate:
    """A peer-judged credential gate with an accumulating reference corpus."""

    def __init__(self, min_jurors: int = 3):
        if not isinstance(min_jurors, int) or min_jurors < 1:
            raise ValueError("min_jurors must be a positive integer")
        self.min_jurors = min_jurors
        self._jurors: dict[str, str] = {}  # juror id -> name
        self._rubric: dict[str, float] = {}  # criterion -> pass threshold
        self._submissions: dict[str, Submission] = {}
        # (submission id, juror id, criterion) -> score
        self._scores: dict[tuple[str, str, str], float] = {}
        self._counter = 0

    # -- the guild assembles ------------------------------------------------
    def set_rubric(self, thresholds: dict[str, float]) -> None:
        """Fix the scoring rubric: criterion -> minimum mean score (0..10)."""
        if not thresholds:
            raise ValueError("rubric must define at least one criterion")
        for criterion, bar in thresholds.items():
            if not isinstance(criterion, str) or not criterion.strip():
                raise ValueError("rubric criteria must be non-empty strings")
            if (
                not isinstance(bar, (int, float))
                or isinstance(bar, bool)
                or not MIN_SCORE <= bar <= MAX_SCORE
            ):
                raise ValueError(
                    f"rubric threshold for {criterion!r} must be within "
                    f"{MIN_SCORE}..{MAX_SCORE}"
                )
        self._rubric = {c.strip(): float(b) for c, b in thresholds.items()}

    def register_juror(self, name: str) -> str:
        """Seat a practitioner on the jury. Practitioners, not issuers."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("juror name must be a non-empty string")
        name = name.strip()
        if any(n.lower() == name.lower() for n in self._jurors.values()):
            raise ValueError(f"duplicate juror: {name!r}")
        self._counter += 1
        juror_id = f"juror-{self._counter}"
        self._jurors[juror_id] = name
        return juror_id

    def submit(self, author: str, title: str) -> Submission:
        """Offer a candidate masterpiece to the gate."""
        if not self._rubric:
            raise ValueError("cannot submit before a rubric is set")
        if not isinstance(author, str) or not author.strip():
            raise ValueError("author must be a non-empty string")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        author, title = author.strip(), title.strip()
        if any(
            s.author.lower() == author.lower() and s.title.lower() == title.lower()
            for s in self._submissions.values()
        ):
            raise ValueError(f"duplicate submission: {title!r} by {author!r}")
        self._counter += 1
        sub = Submission(id=f"sub-{self._counter}", author=author, title=title)
        self._submissions[sub.id] = sub
        return sub

    # -- the judgment --------------------------------------------------------
    def score(
        self, juror_id: str, submission_id: str, criterion: str, value: float
    ) -> None:
        """One practitioner's score for one criterion of one submission."""
        if juror_id not in self._jurors:
            raise ValueError(f"unknown juror: {juror_id!r}")
        if submission_id not in self._submissions:
            raise ValueError(f"unknown submission: {submission_id!r}")
        if criterion not in self._rubric:
            raise ValueError(f"unknown criterion: {criterion!r}")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not MIN_SCORE <= value <= MAX_SCORE
        ):
            raise ValueError(f"score must be within {MIN_SCORE}..{MAX_SCORE}")
        key = (submission_id, juror_id, criterion)
        if key in self._scores:
            raise ValueError(
                f"juror {juror_id!r} already scored {criterion!r} for {submission_id!r}"
            )
        self._scores[key] = float(value)

    def _require_complete_jury(self, submission_id: str) -> None:
        if len(self._jurors) < self.min_jurors:
            raise ValueError(
                f"verdict needs at least {self.min_jurors} jurors; "
                f"seated={len(self._jurors)}"
            )
        missing = [
            (j, c)
            for j in self._jurors
            for c in self._rubric
            if (submission_id, j, c) not in self._scores
        ]
        if missing:
            raise ValueError(
                f"verdict refused: {len(missing)} juror/criterion scores still missing"
            )

    def verdict(self, submission_id: str) -> dict:
        """Render the jury's verdict. Every criterion's mean must clear its
        rubric bar; admitted pieces join the reference corpus."""
        sub = self._submissions.get(submission_id)
        if sub is None:
            raise ValueError(f"unknown submission: {submission_id!r}")
        if sub.verdict != "pending":
            raise ValueError(f"submission {submission_id!r} already judged")
        self._require_complete_jury(submission_id)
        means = {}
        for criterion in self._rubric:
            vals = [self._scores[(submission_id, j, criterion)] for j in self._jurors]
            means[criterion] = sum(vals) / len(vals)
        passed = all(means[criterion] >= bar for criterion, bar in self._rubric.items())
        sub.verdict = "admitted" if passed else "rejected"
        return {"submission": submission_id, "verdict": sub.verdict, "means": means}

    # -- the accumulating corpus ----------------------------------------------
    def corpus(self) -> list[Submission]:
        """Retained masterpieces: the guild's quality reference."""
        return [s for s in self._submissions.values() if s.verdict == "admitted"]

    def reference_standard(self) -> dict:
        """Mean score per criterion across the admitted corpus — the bar
        future submissions are measured against."""
        admitted = self.corpus()
        if not admitted:
            raise ValueError("no admitted masterpieces yet; corpus is empty")
        standard = {}
        for criterion in self._rubric:
            vals = [
                self._scores[(s.id, j, criterion)]
                for s in admitted
                for j in self._jurors
            ]
            standard[criterion] = sum(vals) / len(vals)
        return standard
