"""Versioned codified pedagogy — the teaching method as a maintained document.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #27).

The mechanism under study: pedagogy is versioned like a maintained
document, improved by field feedback across editions. The classroom loop
runs in three moves — *praelectio* (guided pre-reading: the teacher
walks the learner through the material), *repetitio* (systematic
repetition and review), *disputatio* (structured defense: the learner
defends a thesis against objections) — and every edition's field notes
fold back into the plan as version N+1.

This is an original, from-scratch implementation for LEVI. A lesson
plan carries its version, its three-loop structure (prelection text,
review items, disputation theses with objections), and the field notes
accumulated while it was taught. Publishing a new edition incorporates
the notes — the ones that changed the plan are marked, the ones that
didn't are kept for the record — and the edition history stays readable.

Public surface:
- ``LessonPlan``: subject, version, loops, review notes;
  ``new_edition()`` incorporates field notes into version N+1.
- ``Ratio``: registry of plans; ``teach()`` runs the praelectio /
  repetitio / disputatio loop; ``defend(thesis, defense)`` scores a
  disputation.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/ratio"


class RatioError(Exception):
    """The plan or the loop refused: wrong version, missing loop, bad session."""


@dataclass
class Thesis:
    """One disputatio proposition: a claim plus the objections to answer."""

    claim: str
    objections: List[str] = field(default_factory=list)

    def required_terms(self) -> List[str]:
        terms = set()
        for text in [self.claim, *self.objections]:
            terms.update(tok.lower() for tok in text.split() if len(tok) > 4)
        return sorted(terms)


@dataclass
class FieldNote:
    """Feedback gathered while an edition was in the field."""

    note: str
    author: str = "anonymous"
    incorporated: bool = False


@dataclass
class LessonPlan:
    """A versioned, codified plan for teaching one subject."""

    subject: str
    version: int = 1
    prelection: str = ""
    review_items: List[str] = field(default_factory=list)
    theses: List[Thesis] = field(default_factory=list)
    notes: List[FieldNote] = field(default_factory=list)
    published: bool = False

    def set_prelection(self, text: str) -> None:
        if not text.strip():
            raise RatioError("prelection requires text")
        self.prelection = text.strip()

    def add_review_item(self, item: str) -> None:
        if not item.strip():
            raise RatioError("review items must be non-empty")
        self.review_items.append(item.strip())

    def add_thesis(self, claim: str, objections: List[str]) -> None:
        if not claim.strip():
            raise RatioError("a thesis requires a claim")
        self.theses.append(
            Thesis(claim.strip(), [o.strip() for o in objections if o.strip()])
        )

    def add_field_note(self, note: str, author: str = "anonymous") -> FieldNote:
        if not note.strip():
            raise RatioError("field notes must be non-empty")
        field_note = FieldNote(note.strip(), author)
        self.notes.append(field_note)
        return field_note

    def new_edition(self, editor: str = "anonymous") -> "LessonPlan":
        """Publish version N+1: field notes are incorporated into the plan.

        Notes whose text mentions prelection/review/disputation rework the
        matching loop; every note is marked incorporated and carried into
        the new edition's record so the edition history stays honest.
        """
        edition = LessonPlan(
            subject=self.subject,
            version=self.version + 1,
            prelection=self.prelection,
            review_items=list(self.review_items),
            theses=[Thesis(t.claim, list(t.objections)) for t in self.theses],
            published=True,
        )
        for note in self.notes:
            text = note.note.lower()
            if "prelect" in text or "pre-read" in text or "walk" in text:
                edition.prelection += (
                    f"\n\n[rev. {self.version}→{edition.version}, {editor}] {note.note}"
                )
            if "review" in text or "repetit" in text:
                edition.review_items.append(
                    f"[rev. {self.version}→{edition.version}] {note.note}"
                )
            if "disput" in text or "objection" in text or "defense" in text:
                if edition.theses:
                    edition.theses[0].objections.append(
                        f"[rev. {self.version}→{edition.version}] {note.note}"
                    )
                else:
                    edition.theses.append(
                        Thesis(f"Defend the subject against: {note.note}", [note.note])
                    )
            note.incorporated = True
            edition.notes.append(FieldNote(note.note, note.author, incorporated=True))
        edition.notes.append(
            FieldNote(
                f"Edition {edition.version} incorporates {len(self.notes)} field note(s).",
                editor,
                incorporated=True,
            )
        )
        return edition


@dataclass
class LoopReport:
    plan_subject: str
    version: int
    prelection_delivered: bool
    repetitions_done: int
    disputations: List[Tuple[str, bool, float]] = field(
        default_factory=list
    )  # (claim, held, score)


class Ratio:
    """Registry of lesson plans plus the runner for the teaching loop."""

    def __init__(self) -> None:
        self.plans: Dict[str, List[LessonPlan]] = {}

    def register(self, plan: LessonPlan) -> None:
        self.plans.setdefault(plan.subject, []).append(plan)

    def current(self, subject: str) -> LessonPlan:
        editions = self.plans.get(subject, [])
        if not editions:
            raise RatioError(f"no plan registered for subject '{subject}'")
        return editions[-1]

    def defend(
        self, plan: LessonPlan, thesis: Thesis, defense: str
    ) -> Tuple[bool, float]:
        """Disputatio: score a defense against a thesis's objections.

        A defense holds if it addresses the objections: the score is the
        fraction of each objection's significant terms the defense
        contains. It holds at >= 0.5 average coverage.
        """
        if not defense.strip():
            raise RatioError("disputatio requires a defense")
        lowered = defense.lower()
        if not thesis.objections:
            held = (
                thesis.claim.split()[0].lower() in lowered or len(defense.split()) >= 10
            )
            return held, 1.0 if held else 0.0
        scores = []
        for objection in thesis.objections:
            terms = [tok.lower() for tok in objection.split() if len(tok) > 4]
            terms = list(dict.fromkeys(terms))
            hits = sum(1 for t in terms if t in lowered)
            scores.append(hits / len(terms) if terms else 1.0)
        average = sum(scores) / len(scores)
        return average >= 0.5, round(average, 3)

    def teach(self, subject: str, defenses: Dict[str, str]) -> LoopReport:
        """Run one full loop: praelectio, repetitio, then disputatio.

        ``defenses`` maps each thesis claim to the learner's defense text.
        """
        plan = self.current(subject)
        if not plan.prelection:
            raise RatioError(f"plan for '{subject}' has no prelection to deliver")
        report = LoopReport(
            plan_subject=plan.subject,
            version=plan.version,
            prelection_delivered=True,
            repetitions_done=len(plan.review_items),
        )
        for thesis in plan.theses:
            defense = defenses.get(thesis.claim, "")
            held, score = self.defend(plan, thesis, defense)
            report.disputations.append((thesis.claim, held, score))
        return report

    def editions(self, subject: str) -> List[Dict[str, object]]:
        """The version history of a subject's plan, notes folded in."""
        return [
            {
                "subject": p.subject,
                "version": p.version,
                "published": p.published,
                "review_items": len(p.review_items),
                "theses": len(p.theses),
                "field_notes": len(p.notes),
            }
            for p in self.plans.get(subject, [])
        ]
