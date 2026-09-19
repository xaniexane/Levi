"""Future Search: the whole system in the room, past to future, enforced.

Origin: developed by Marvin Weisbord and Sandra Janoff, building on six
decades of social science research (book "Future Search," fully revised
third edition). The design: get the whole system in the room — typically
60 to 80 people from eight stakeholder groups — for two and a half days
following a fixed arc: Day 1 past (shared timeline) → Day 2 present
(trends, pride and regret) → ideal future scenarios → common ground →
Day 3 action plans. Cases: IKEA's product pipeline redesign in Sweden, an
integrated economic development plan in Northern Ireland, demobilizing
child soldiers in Southern Sudan.

The load-bearing parts: (1) the AREIN gate — the right people ARE IN the
room: people with Authority, Resources, Expertise, Information, and Need.
A search that proceeds without all five is refused; (2) no problem-solving
until the future arc — the past and present must be digested first, and
rushing to solutions is the failure mode the protocol exists to prevent;
(3) common ground, not consensus — the group seeks what it already shares
and treats conflicts as information, never as action items; nobody is
asked to surrender a position.

What killed it in mainstream practice: too slow for quarterly capitalism
(a 2.5-day cross-system retreat cannot be a SaaS feature) and too cheap
to sell (facilitators charge thousands; corporate strategy collapsed into
one-hour offsites and slideware). The practitioner network keeps it
alive; organizational planning largely forgot it.

What it is in LEVI: a compressed, local-first Future Search kit. The five
stages are ordered phases with artifacts (timeline, trend map, scenario
sketches, common-ground statements, action plans), the no-problem-solving-
before-future rule is enforced by the state machine, and the AREIN gate
forces the question engagement groupware never asks: who is missing from
this decision. A small team can run the compressed arc in a day; the
structure, not the headcount, is the point. LEVI uses it for its own
strategic deliberations (e.g., planning a build wave across subsystems).

Honesty label: USEFUL PATTERN — genuine large-scale case evidence, but
the successes came from skilled facilitators. This module encodes the
protocol, not the facilitator; the boundary is stated, not hidden.

Deny-closed inputs: opening without all five AREIN categories, recording
a stage out of order, recording future scenarios before the present arc,
recording common ground before future scenarios, and action plans before
common ground are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["FutureSearch", "AREIN"]

AREIN = ("authority", "resources", "expertise", "information", "need")

STAGES = ("past", "present", "future", "common_ground", "action")


@dataclass
class FutureSearch:
    """A Future Search run as ordered, gated stages.

    ``stakeholders`` maps each AREIN category to the stakeholder groups
    present for it. ``record(stage, items)`` advances the arc in order.
    """

    topic: str
    stakeholders: Dict[str, List[str]] = field(default_factory=dict)
    _stage_idx: int = field(default=0, init=False, repr=False)
    _artifacts: Dict[str, List[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.topic.strip():
            raise ValueError("futuresearch: topic must not be empty")
        missing = [c for c in AREIN if not self.stakeholders.get(c)]
        if missing:
            raise ValueError(
                "futuresearch: AREIN gate failed — missing: %s" % ", ".join(missing)
            )

    @property
    def stage(self) -> str:
        return STAGES[self._stage_idx]

    def record(self, stage: str, items: List[str]) -> List[str]:
        """Record artifacts for a stage; stages must be taken in order.

        The no-problem-solving rule is structural: ``action`` cannot be
        recorded before ``common_ground``, and ``common_ground`` cannot be
        recorded before ``future`` — the past and present arcs must be
        digested first.
        """
        if stage not in STAGES:
            raise ValueError("futuresearch: unknown stage %r" % stage)
        expected = STAGES[self._stage_idx]
        if stage != expected:
            raise ValueError(
                "futuresearch: stage %r recorded out of order; expected %r "
                "(no problem-solving before the future arc)" % (stage, expected)
            )
        clean = [i.strip() for i in items if i and i.strip()]
        if not clean:
            raise ValueError(
                "futuresearch: stage %r needs at least one artifact" % stage
            )
        self._artifacts[stage] = clean
        if self._stage_idx < len(STAGES) - 1:
            self._stage_idx += 1
        return list(clean)

    def artifacts(self, stage: str) -> List[str]:
        if stage not in STAGES:
            raise ValueError("futuresearch: unknown stage %r" % stage)
        return list(self._artifacts.get(stage, []))

    def common_ground(self) -> List[str]:
        """The shared statements everything downstream must honor."""
        if "common_ground" not in self._artifacts:
            raise ValueError("futuresearch: common ground not yet established")
        return list(self._artifacts["common_ground"])

    def complete(self) -> bool:
        return "action" in self._artifacts

    def summary(self) -> Dict[str, object]:
        return {
            "topic": self.topic,
            "stage": self.stage,
            "arein": {c: list(self.stakeholders[c]) for c in AREIN},
            "artifacts": {s: list(self._artifacts.get(s, [])) for s in STAGES},
            "complete": self.complete(),
        }
