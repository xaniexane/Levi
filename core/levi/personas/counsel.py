"""Board counsel — LEVI-native review stances for Chauncey's board and admin team.

LAW (law-guard-prove):
A stance modulates the CRITIQUE ANGLE only — what questions get asked, what
red flags get raised. It never overrides safety, permissions, factual
integrity, or privacy, never claims another identity, and never borrows
provider branding. Every text field in every stance must pass
``check_no_mask`` (see core/levi/bot/persona.py) — the tests enforce this.
LEVI stays LEVI; the counselors are lenses, not masks.

The three stances are original LEVI inventions, named for what they do:
* ``keeper``     — guards the canon and provenance: is it archived, is the
  original preserved, does it obey standing law?
* ``contrarian`` — attacks the weakest point: what breaks, what's the
  honest failure mode, what would the red team say?
* ``builder``    — shippable-first: what's the smallest real thing that
  lands, what's the proof, what's still missing?

``review(stance_id, proposal)`` is deterministic: the same stance on the
same proposal always returns the same report. Reviews are keyword-and-
structure driven — an honest checklist, not a verdict machine. A stance
that finds no triggers still returns its full required sections.

Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from levi.bot.persona import check_no_mask

COUNSEL_LAW = (
    "A stance modulates the critique angle only — questions, red flags, "
    "next steps. It never overrides safety, permissions, factual integrity, "
    "or privacy, never claims another identity, and never borrows provider "
    "branding. LEVI stays LEVI."
)


@dataclass(frozen=True)
class Check:
    """One triggered check: a keyword hit turned into a question."""

    trigger: str
    question: str


@dataclass(frozen=True)
class Stance:
    id: str
    name: str
    stake: str  # what this stance exists to protect
    doctrine: str  # the one-line doctrine it never drops
    triggers: Dict[str, str]  # keyword -> question to ask when the keyword appears
    standing_flags: List[str]  # red flags raised regardless of the proposal
    next_step_hint: str

    def text_fields(self) -> List[str]:
        return [
            self.id,
            self.name,
            self.stake,
            self.doctrine,
            *self.triggers.values(),
            *self.standing_flags,
            self.next_step_hint,
        ]


STANCES: Dict[str, Stance] = {
    "keeper": Stance(
        id="keeper",
        name="The Keeper",
        stake="canon, provenance, and standing law",
        doctrine="Archive faithfully, build natively; nothing is thrown away.",
        triggers={
            "delete": "Where does the deleted thing live now — archive or stored/, and what note says why?",
            "remove": "What replaces it, and who ruled on the removal?",
            "free": "The no-free-core law: is any 'free' language landing in product text?",
            "rewrite": "Is the original preserved untouched before the rewrite begins?",
            "clone": "Is this an addition or a rebuild of a giant's feature?",
        },
        standing_flags=[
            "Verify the original exists in the corpus before any build is briefed (originals-first rule).",
            "Every change lands with a glyph-attributed commit; unlabeled work gets flagged, never auto-resolved.",
        ],
        next_step_hint="Name the provenance: source, ruling, and where the original is kept.",
    ),
    "contrarian": Stance(
        id="contrarian",
        name="The Contrarian",
        stake="honest failure modes",
        doctrine="A success report that hides a caveat is a lie with good lighting.",
        triggers={
            "always": "What breaks the 'always'? Name the concrete counterexample.",
            "never": "What makes the 'never' false? Name the edge case.",
            "guarantee": "What does it cost when the guarantee fails — who pays?",
            "simple": "What's the hidden complexity being hand-waved past?",
            "trust": "Trust on what evidence? Quote the receipt, not the claim.",
        },
        standing_flags=[
            "Every claim gets the honest-limits pass: what does this NOT do yet?",
            "If the numbers aren't real (measured, not vibe), the claim isn't either.",
        ],
        next_step_hint="Write the failure paragraph first — what breaks, who feels it, what the receipt says.",
    ),
    "builder": Stance(
        id="builder",
        name="The Builder",
        stake="shippable reality",
        doctrine="Ship the smallest real thing; queue the rest, don't half-build it.",
        triggers={
            "eventually": "What ships THIS run, and what goes into the build queue instead?",
            "framework": "Is this a framework waiting for content, or content that landed?",
            "integrat": "What's wired end to end right now — name the working path.",
            "someday": "Someday is a queue entry with a name on it, or it doesn't exist.",
            "plan": "The plan is a test that passes, a file that exists, or it's a wish.",
        },
        standing_flags=[
            "Law-guard-prove: the invariant is stated, the guard exists, the proof ran — or the build isn't done.",
            "Tests green from zero, ruff clean on touched files, committed locally — the everything standard.",
        ],
        next_step_hint="State the deliverable in one line: what file, what test, what proof.",
    ),
}


@dataclass
class CounselReport:
    stance_id: str
    stance_name: str
    doctrine: str
    triggered: List[Check] = field(default_factory=list)
    standing_flags: List[str] = field(default_factory=list)
    next_step: str = ""

    def render(self) -> str:
        lines = [
            f"[{self.stance_name}] {self.doctrine}",
            "",
            "Triggered checks:",
        ]
        for check in self.triggered:
            lines.append(f"  • ({check.trigger}) {check.question}")
        if not self.triggered:
            lines.append("  • none — no trigger keywords in the proposal.")
        lines += ["", "Standing flags:"]
        for flag in self.standing_flags:
            lines.append(f"  • {flag}")
        lines += ["", f"Next step: {self.next_step}"]
        return "\n".join(lines)


class UnknownStance(Exception):
    """No such counsel stance — refused, never guessed."""


def list_stances() -> List[str]:
    return sorted(STANCES.keys())


def get_stance(stance_id: str) -> Stance:
    try:
        return STANCES[stance_id]
    except KeyError:
        raise UnknownStance(f"no counsel stance {stance_id!r}") from None


def review(stance_id: str, proposal: str) -> CounselReport:
    """Run one stance's review over a proposal — deterministic.

    Raises UnknownStance for an unknown stance. An empty proposal still
    gets the standing flags and next step (never an empty report).
    """
    stance = get_stance(stance_id)
    lowered = proposal.lower()
    triggered = [
        Check(trigger=keyword, question=question)
        for keyword, question in stance.triggers.items()
        if re.search(r"\b" + re.escape(keyword), lowered)
    ]
    return CounselReport(
        stance_id=stance.id,
        stance_name=stance.name,
        doctrine=stance.doctrine,
        triggered=triggered,
        standing_flags=list(stance.standing_flags),
        next_step=stance.next_step_hint,
    )


def verify_no_mask() -> List[str]:
    """Run check_no_mask over every text field of every stance.

    Returns violations (empty = clean). The tests assert this.
    """
    violations: List[str] = []
    for stance in STANCES.values():
        for text in stance.text_fields():
            for violation in check_no_mask(text):
                violations.append(f"{stance.id}: {violation}")
    return violations
