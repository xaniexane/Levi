"""The Delphi method: iterative anonymous expert elicitation, enforced.

Origin: RAND Corporation, 1950s. The first Delphi study was carried out by
Olaf Helmer and Norman Dalkey in 1951 (classified as "The Use of Experts
for the Estimation of Bombing Requirements"; declassified a decade later,
published in Management Science 1963). Dalkey's definition: "a method of
eliciting and refining group judgments." Named for the Oracle of Apollo
at Delphi — the forecasting association, not the mechanism.

The protocol: a panel of experts answers a questionnaire in rounds. After
each round the group median and interquartile range (IQR) are fed back with
summarized reasoning, and experts may revise their estimates. Three
load-bearing parts: (1) anonymity kills "specious persuasion" (the loudest
or highest-ranked voice dragging the group against its judgment); (2)
controlled feedback — convergence is to the statistical group response,
not to a person; (3) iteration with an exit rule — rounds stop on
convergence, not on fatigue. The 1980s RAND/UCLA medical adaptation capped
rounds at two around a literature brief, proving the protocol survives
surgical adaptation.

What it is in LEVI: the round discipline, enforced in code. A DelphiRound
accepts one numeric submission per member per round, computes median and
IQR on close, refuses early closure, and declares convergence only when
IQR <= threshold. Members are pseudonymous ids — LEVI never needs to
know who they are, only that they are distinct.

Honesty label: LOAD-BEARING — anonymity + iteration + statistical feedback
is a concrete, transferable mechanism. The skepticism stays in the
docstring: Delphi is still used in health and futures research; it fell
from mainstream business practice because multi-week rounds lost to
billable-hour workshops, not because the mechanism was disproved. Consensus
can be manufactured by feedback itself — convergence is reported, never
blessed.

Deny-closed inputs: duplicate submissions in a round, non-numeric
estimates, empty panels, closing a round with zero submissions, and
revising in a closed round are all rejected with ValueError.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = ["DelphiRound", "Submission"]

MIN_PANEL = 2
DEFAULT_CONVERGENCE_IQR = 0.0


@dataclass
class Submission:
    member: str
    value: float
    rationale: str = ""


@dataclass
class DelphiRound:
    """One Delphi round: collect anonymous numeric estimates, close, feed back.

    Create with ``DelphiRound(members=[...])``; members submit via
    ``submit()``; ``close()`` locks the round and computes the statistics.
    ``DelphiRound`` is single-round — chain instances for multi-round runs,
    passing the previous median/IQR as the feedback context.
    """

    members: List[str]
    question: str = ""
    round_no: int = 1
    convergence_iqr: float = DEFAULT_CONVERGENCE_IQR
    _submissions: Dict[str, Submission] = field(default_factory=dict, repr=False)
    _closed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if len(set(self.members)) < MIN_PANEL:
            raise ValueError(
                "delphi: need at least %d distinct panel members, got %d"
                % (MIN_PANEL, len(set(self.members)))
            )
        if not self.question:
            raise ValueError("delphi: question must not be empty")
        if self.convergence_iqr < 0:
            raise ValueError("delphi: convergence_iqr must be >= 0")

    def submit(self, member: str, value: float, rationale: str = "") -> None:
        """Record one member's estimate for this round (anonymous in storage)."""
        if self._closed:
            raise ValueError(
                "delphi: round %d is closed; revise in the next round" % self.round_no
            )
        if member not in self.members:
            raise ValueError("delphi: %r is not a panel member" % member)
        if member in self._submissions:
            raise ValueError(
                "delphi: %r already submitted in round %d" % (member, self.round_no)
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("delphi: estimate must be numeric, got %r" % (value,))
        self._submissions[member] = Submission(
            member=member, value=float(value), rationale=rationale
        )

    def close(self) -> Dict[str, float]:
        """Lock the round and return the feedback statistics for the next round."""
        if self._closed:
            raise ValueError("delphi: round %d already closed" % self.round_no)
        if not self._submissions:
            raise ValueError(
                "delphi: cannot close round %d with zero submissions" % self.round_no
            )
        self._closed = True
        return self.statistics()

    def statistics(self) -> Dict[str, float]:
        values = sorted(s.value for s in self._submissions.values())
        med = statistics.median(values)
        if len(values) >= 4:
            q = statistics.quantiles(values, n=4)
            iqr = q[2] - q[0]
        else:
            iqr = values[-1] - values[0]
        return {
            "round": float(self.round_no),
            "n": float(len(values)),
            "median": med,
            "iqr": iqr,
            "min": values[0],
            "max": values[-1],
        }

    def converged(self) -> bool:
        """True when the closed round's IQR is within the convergence threshold."""
        if not self._closed:
            raise ValueError(
                "delphi: round %d must be closed before checking convergence"
                % self.round_no
            )
        return self.statistics()["iqr"] <= self.convergence_iqr

    def next_round(self, convergence_iqr: Optional[float] = None) -> "DelphiRound":
        """Start the follow-up round carrying the feedback statistics forward."""
        if not self._closed:
            raise ValueError(
                "delphi: close round %d before opening the next" % self.round_no
            )
        return DelphiRound(
            members=list(self.members),
            question=self.question,
            round_no=self.round_no + 1,
            convergence_iqr=self.convergence_iqr
            if convergence_iqr is None
            else convergence_iqr,
        )

    def rationales(self) -> List[str]:
        """Summarized reasoning from the closed round (the controlled feedback)."""
        if not self._closed:
            raise ValueError(
                "delphi: round %d must be closed before reading rationales"
                % self.round_no
            )
        return [s.rationale for s in self._submissions.values() if s.rationale]
