"""Synectics: Gordon's excursion engine — make the familiar strange, then
force-fit it back.

Origin: W.J.J. Gordon, "Synectics: The Development of Creative Capacity"
(Harper & Row, 1961). From Greek syn (together) + ektos (outside): the
joining of diverse elements. Gordon's team studied working inventors,
found recurring psychological states, and built the procedure around them.

The protocol: state the problem, then LEAVE it. An "excursion" journeys
through four operational mechanisms of analogy — direct (the problem is
like what known thing?), personal (be the thing), symbolic / compressed
conflict (a two-word paradox, e.g. "jumbo shrimp"), and fantasy (how would
it work in a dream?). Only after the excursion does the group "force-fit"
the strange material back onto the problem and restate the problem in new
terms. The departure is the mechanism: brainstorming stays inside the
problem and dries up; Synectics leaves it.

What it is in LEVI: the excursion discipline, enforced in code. An
Excursion is a deny-closed state machine: GATHER (analogies recorded,
never judged) → FORCE_FIT (each insight must cite a gathered analogy) →
CLOSED (the problem is restated once, from the force-fits).

LAWS (declared here, enforced below):
  L1. The excursion gathers; it never judges. There is no scoring or
      ranking during GATHER — evaluation is structurally impossible.
  L2. Force-fit requires gathered material. A force-fit must cite an
      analogy that was actually gathered in this excursion.
  L3. The restatement comes last. The problem may be restated only after
      at least one force-fit, and only once.

Honesty label: LOAD-BEARING — the excursion + force-fit loop is a
concrete, transferable mechanism. The skepticism stays in the docstring:
the evidence base is practitioner literature, not controlled trials, and
a bad excursion led by an unskilled hand is just a tangent. Synectics
professionalized into expensive consulting; this module takes the
protocol, not the price tag.

Deny-closed inputs: empty problem, unknown analogy kind, blank analogy
text, force-fit before any analogy is gathered, force-fit citing an
analogy not in this excursion, restatement before any force-fit,
anything after close — all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "ANALOGY_KINDS",
    "Analogy",
    "ForceFit",
    "Excursion",
    "ST_NEW",
    "ST_GATHER",
    "ST_FORCE_FIT",
    "ST_CLOSED",
]

ANALOGY_KINDS = ("direct", "personal", "symbolic", "fantasy")

ST_NEW = "new"
ST_GATHER = "gather"
ST_FORCE_FIT = "force_fit"
ST_CLOSED = "closed"


@dataclass(frozen=True)
class Analogy:
    kind: str
    text: str

    def __post_init__(self) -> None:
        if self.kind not in ANALOGY_KINDS:
            raise ValueError("unknown analogy kind: %r (kinds: %s)" % (self.kind, ", ".join(ANALOGY_KINDS)))
        if not self.text or not self.text.strip():
            raise ValueError("analogy text must not be blank")


@dataclass(frozen=True)
class ForceFit:
    analogy: Analogy
    insight: str

    def __post_init__(self) -> None:
        if not self.insight or not self.insight.strip():
            raise ValueError("force-fit insight must not be blank")


class Excursion:
    """A single Synectics excursion over one problem."""

    def __init__(self, problem: str) -> None:
        if not problem or not problem.strip():
            raise ValueError("problem must not be blank")
        self._problem = problem.strip()
        self._state = ST_NEW
        self._analogies: List[Analogy] = []
        self._fits: List[ForceFit] = []
        self._restatement: Optional[str] = None

    @property
    def problem(self) -> str:
        return self._problem

    @property
    def state(self) -> str:
        return self._state

    def begin(self) -> "Excursion":
        """Leave the problem: open the excursion for gathering."""
        if self._state != ST_NEW:
            raise ValueError("excursion already begun")
        self._state = ST_GATHER
        return self

    def add_analogy(self, kind: str, text: str) -> Analogy:
        """Record one analogy from the excursion. Never judged here (L1)."""
        if self._state != ST_GATHER:
            raise ValueError("analogies are gathered only during the excursion")
        analogy = Analogy(kind=kind, text=text.strip())
        self._analogies.append(analogy)
        return analogy

    def force_fit(self, analogy_text: str, insight: str) -> ForceFit:
        """Map gathered strange material back onto the problem (L2)."""
        if self._state == ST_GATHER:
            if not self._analogies:
                raise ValueError("cannot force-fit: the excursion gathered nothing")
            self._state = ST_FORCE_FIT
        if self._state != ST_FORCE_FIT:
            raise ValueError("force-fit is allowed only after the excursion")
        match = next((a for a in self._analogies if a.text == analogy_text.strip()), None)
        if match is None:
            raise ValueError("force-fit must cite an analogy gathered in this excursion")
        fit = ForceFit(analogy=match, insight=insight.strip())
        self._fits.append(fit)
        return fit

    def restate_problem(self, restatement: str) -> str:
        """Restate the problem from the force-fits, exactly once (L3)."""
        if self._state != ST_FORCE_FIT or not self._fits:
            raise ValueError("restatement requires at least one force-fit")
        if self._restatement is not None:
            raise ValueError("the problem is restated once")
        if not restatement or not restatement.strip():
            raise ValueError("restatement must not be blank")
        self._restatement = restatement.strip()
        self._state = ST_CLOSED
        return self._restatement

    def analogies(self) -> List[Analogy]:
        return list(self._analogies)

    def force_fits(self) -> List[ForceFit]:
        return list(self._fits)

    def restatement(self) -> Optional[str]:
        return self._restatement
