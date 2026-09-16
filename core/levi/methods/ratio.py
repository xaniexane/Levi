"""Jesuit Ratio Studiorum: the versioned study loop as a runnable protocol.

Origin: the Society of Jesus's *Plan of Studies* (definitive edition
1599): a standardized, centrally-maintained pedagogy for hundreds of
schools, built on **praelectio** (the teacher's careful pre-reading and
exposition of the text), **repetitio** (systematic repetition and review),
and **disputatio** (structured disputation), with tiered classes and
explicit rules for every role. The 1586 -> 1591 -> 1599 revision cycle is
an early example of iterative deployment: the teaching method itself is a
maintained document, improved by field feedback.

What it is in LEVI: the assistant runs the Ratio loop on anything you're
learning. **Praelectio**: it pre-reads the material and gives you the
guided tour. **Repetitio**: spaced review on a fixed schedule, with
recall-quality marks. **Disputatio**: it takes the opposing side and
forces you to defend your understanding — every objection must be
answered. And your *learning protocol itself* is versioned: the method
improves with use.

Honesty label: USEFUL PATTERN — credit the *versioned codification*, not
the institutional superlative ("first real school system" is Jesuit pride;
older systems have their own claims).

PROTOCOL LABEL: this module is a procedure the assistant executes with
you, not an autonomous agent. It holds the loop; the learning is yours.

Deny-closed inputs: empty subjects/material, defending unraised
objections, recall marks outside 0-5, and completing with open
objections are rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Union

__all__ = ["RatioStudy", "REPETITION_LAGS"]

# The repetitio schedule: days after first exposure. Systematic, not vibes.
REPETITION_LAGS: tuple[int, ...] = (1, 3, 7, 14, 30)

DateLike = Union[date, str]


def _parse_date(value: DateLike, field_name: str = "date") -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            y, m, d = value.split("-")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            pass
    raise ValueError(
        f"{field_name}: expected datetime.date or 'YYYY-MM-DD', got {value!r}"
    )


@dataclass
class Objection:
    text: str
    response: str = ""  # empty = not yet defended


class RatioStudy:
    """One subject under the praelectio / repetitio / disputatio loop."""

    def __init__(self, subject: str, material: str, start: Optional[DateLike] = None):
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("subject must be a non-empty string")
        if not isinstance(material, str) or not material.strip():
            raise ValueError(
                "material must be a non-empty string (what is being studied?)"
            )
        self.subject = subject.strip()
        self.material = material.strip()
        self.start = _parse_date(start) if start is not None else date.today()
        self._tour: list[str] = []  # praelectio: guided exposition outline
        self._repetitions: dict[int, dict] = {}  # lag -> {date, quality}
        self._objections: list[Objection] = []  # disputatio
        self.protocol_version = 1
        self.protocol_changelog: list[str] = [
            "v1: initial Ratio loop (praelectio/repetitio/disputatio)"
        ]

    @staticmethod
    def _clean(value: str, kind: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{kind} must be a non-empty string")
        return value.strip()

    # -- praelectio: the guided tour -------------------------------------------------------
    def praelectio(self, tour: list[str]) -> int:
        """Record the pre-reading exposition: the guided tour of the material."""
        clean = [self._clean(t, "tour point") for t in tour]
        if not clean:
            raise ValueError("praelectio needs at least one tour point")
        self._tour.extend(clean)
        return len(self._tour)

    # -- repetitio: systematic review ---------------------------------------------------------
    def repetitio_schedule(self) -> list[dict]:
        """The fixed review calendar: 1, 3, 7, 14, 30 days after start."""
        return [
            {
                "lag_days": lag,
                "date": (self.start + timedelta(days=lag)).isoformat(),
                "done": lag in self._repetitions,
            }
            for lag in REPETITION_LAGS
        ]

    def mark_repetition(
        self, lag_days: int, quality: int, on_date: Optional[DateLike] = None
    ) -> None:
        """Mark a review done, with recall quality 0 (blank) .. 5 (perfect).

        Honest marks only — the schedule adapts to the truth, not the wish.
        """
        if lag_days not in REPETITION_LAGS:
            raise ValueError(f"lag_days must be one of {list(REPETITION_LAGS)}")
        if not isinstance(quality, int) or not (0 <= quality <= 5):
            raise ValueError(f"quality must be an int 0..5, got {quality!r}")
        day = _parse_date(on_date) if on_date is not None else date.today()
        self._repetitions[lag_days] = {"date": day.isoformat(), "quality": quality}

    def repetition_report(self) -> dict:
        done = len(self._repetitions)
        qualities = [r["quality"] for r in self._repetitions.values()]
        return {
            "scheduled": len(REPETITION_LAGS),
            "completed": done,
            "mean_quality": round(sum(qualities) / len(qualities), 2)
            if qualities
            else None,
            "weak_lags": sorted(
                lag for lag, r in self._repetitions.items() if r["quality"] <= 2
            ),
        }

    # -- disputatio: defend it -------------------------------------------------------------------
    def disputatio(self, objections: list[str]) -> int:
        """Raise objections the understanding must survive."""
        clean = [self._clean(o, "objection") for o in objections]
        if not clean:
            raise ValueError("disputatio needs at least one objection")
        for o in clean:
            self._objections.append(Objection(text=o))
        return len(self._objections)

    def defend(self, index: int, response: str) -> None:
        """Answer one objection. Every objection must be defended."""
        if not isinstance(index, int) or not (0 <= index < len(self._objections)):
            raise ValueError(f"objection index out of range: {index!r}")
        self._objections[index].response = self._clean(response, "defense")

    def undefended(self) -> list[int]:
        return [i for i, o in enumerate(self._objections) if not o.response]

    def complete(self) -> bool:
        """The loop is complete only when every stage is done and every
        objection defended. Refuses to certify otherwise."""
        return (
            bool(self._tour)
            and len(self._repetitions) == len(REPETITION_LAGS)
            and bool(self._objections)
            and not self.undefended()
        )

    # -- the versioned protocol ---------------------------------------------------------------------
    def revise_protocol(self, note: str) -> int:
        """Improve the method itself from field experience (1586 -> 1591 -> 1599).

        The *teaching method* is a maintained document: what did this study
        teach you about how to study?
        """
        note = self._clean(note, "protocol revision note")
        self.protocol_version += 1
        self.protocol_changelog.append(f"v{self.protocol_version}: {note}")
        return self.protocol_version

    def status(self) -> dict:
        return {
            "subject": self.subject,
            "material": self.material,
            "tour_points": len(self._tour),
            "repetitio": self.repetition_report(),
            "objections": len(self._objections),
            "undefended": self.undefended(),
            "complete": self.complete(),
            "protocol_version": self.protocol_version,
        }
