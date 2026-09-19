"""Deming's system of profound knowledge: diagnose through four lenses.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #25)

The mechanism is a diagnostic lattice, not a checklist. An issue must be
examined through four interacting lenses before any verdict is produced:

1. **system** — how the parts interact; an issue is usually a property
   of the system, not of a person or a part in isolation.
2. **variation** — whether what you see is signal or noise; common-cause
   variation needs a system change, special-cause variation needs
   intervention at the cause.
3. **theory of knowledge** — what you actually know vs. assume: the
   evidence, its limits, and what would change the conclusion.
4. **psychology** — the human layer: motivation, fear, pride, and how the
   people in the system actually experience the issue.

Two hard rules make the module honest:

* **All four lenses required.** ``diagnose()`` refuses to produce a
  verdict unless every lens has a finding. A three-lens diagnosis is a
  draft, and the module says so.
* **No single-data-point verdicts.** Celebrating or mourning one data
  point — treating a single observation as proof of improvement or
  failure — is flagged explicitly: the module names it as
  ``single_point_fallacy`` and withholds the verdict until more
  evidence arrives.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/deming"

LENSES = ("system", "variation", "theory_of_knowledge", "psychology")

LENS_QUESTIONS = {
    "system": "How do the parts interact here — is this a property of "
    "the system or of a person/part in isolation?",
    "variation": "Is this signal or noise — common-cause variation "
    "(needs a system change) or special-cause (needs "
    "targeted intervention)?",
    "theory_of_knowledge": "What do you actually know vs. assume — what "
    "is the evidence, its limits, and what would "
    "change the conclusion?",
    "psychology": "What is the human layer — motivation, fear, pride — "
    "and how do the people in the system experience this?",
}


@dataclass
class Finding:
    """What one lens sees. ``data_points`` counts the evidence behind it."""

    lens: str
    observation: str
    data_points: int = 1
    limits: str = ""

    def __post_init__(self) -> None:
        if self.lens not in LENSES:
            raise ValueError(f"unknown lens: {self.lens!r}. Use one of {LENSES}")
        if not self.observation.strip():
            raise ValueError("a finding needs an observation")
        if not isinstance(self.data_points, int) or self.data_points < 1:
            raise ValueError("data_points must be a positive int")


@dataclass
class Diagnosis:
    """An issue under examination through the four-lens lattice."""

    issue: str
    findings: Dict[str, Finding] = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings[finding.lens] = finding

    def covered_lenses(self) -> List[str]:
        return [lens for lens in LENSES if lens in self.findings]

    def missing_lenses(self) -> List[str]:
        return [lens for lens in LENSES if lens not in self.findings]

    def is_ready(self) -> bool:
        return not self.missing_lenses()


def diagnose(
    diagnosis: Diagnosis, allow_single_point: bool = False
) -> Dict[str, object]:
    """Produce the verdict — only when the lattice is complete.

    Returns a verdict dict with per-lens observations, the interaction
    read (how the lenses combine), and the verdict. Refuses in two
    cases:

    * **incomplete lattice** — any lens missing: returns
      ``{"verdict": None, "refusal": "incomplete_lattice", ...}`` and
      names the missing lenses.
    * **single-data-point verdict** — every finding rests on exactly
      one data point: returns ``{"verdict": None,
      "refusal": "single_point_fallacy", ...}`` explaining why a single
      observation cannot carry a celebration or a mourning. Pass
      ``allow_single_point=True`` only to get the provisional read with
      the fallacy explicitly flagged on it.
    """
    missing = diagnosis.missing_lenses()
    if missing:
        return {
            "issue": diagnosis.issue,
            "verdict": None,
            "refusal": "incomplete_lattice",
            "missing_lenses": missing,
            "missing_questions": [LENS_QUESTIONS[lens] for lens in missing],
            "note": (
                "A verdict needs all four lenses. "
                f"Missing: {', '.join(missing)}. "
                "What you have so far is a draft, not a diagnosis."
            ),
        }

    thin = [lens for lens in LENSES if diagnosis.findings[lens].data_points == 1]
    if thin and not allow_single_point:
        return {
            "issue": diagnosis.issue,
            "verdict": None,
            "refusal": "single_point_fallacy",
            "thin_lenses": thin,
            "note": (
                "Every lens rests on a single data point. One observation "
                "is not evidence of improvement or failure — celebrating "
                "or mourning it would be reacting to noise. Bring more "
                "data points, or pass allow_single_point=True for a "
                "provisional read with this fallacy flagged."
            ),
        }

    lenses_read = {
        lens: {
            "observation": diagnosis.findings[lens].observation,
            "data_points": diagnosis.findings[lens].data_points,
            "limits": diagnosis.findings[lens].limits,
        }
        for lens in LENSES
    }
    interaction = _interaction_read(diagnosis)
    verdict = {
        "issue": diagnosis.issue,
        "verdict": "diagnosed",
        "lenses": lenses_read,
        "interaction": interaction,
        "single_point_flagged": bool(thin),
    }
    if thin:
        verdict["fallacy_flag"] = (
            "provisional: some lenses rest on a single data point; "
            "treat this read as a hypothesis, not a conclusion."
        )
    return verdict


def _interaction_read(diagnosis: Diagnosis) -> str:
    """How the four lenses combine — the lattice is the point."""
    sys = diagnosis.findings["system"].observation
    var = diagnosis.findings["variation"].observation
    tok = diagnosis.findings["theory_of_knowledge"].observation
    psy = diagnosis.findings["psychology"].observation
    return (
        f"System: {sys} Variation: {var} "
        f"Theory of knowledge: {tok} Psychology: {psy} "
        "The verdict must hold all four at once: a system-level fix "
        "that ignores the variation type misfires, a fix without "
        "evidence discipline is superstition, and a fix that ignores "
        "the human layer gets quietly sabotaged."
    )


def lens_prompts() -> Dict[str, str]:
    """The four diagnostic questions, for driving an interview."""
    return dict(LENS_QUESTIONS)
