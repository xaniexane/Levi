"""CloudCounsel — the base every CI counsel stands on.

A counsel is a superior advisory/judging intelligence for its class. It is
NEVER a commander: it proposes, it is challenged, it renders a verdict —
and the verdict is advice the operator/minion weighs, never an order it
must obey. Separation of counsel and command is the design law.

Deliberation protocol (every counsel, every case):
    propose   — each seat issues a proposed judgment on the case
    challenge — seats challenge each other's proposals (the inverse-twin
                canon: alternates, champions, phantoms red-team the take)
    verdict   — quorum renders the verdict; dissent is recorded, never
                erased

Substrate honesty: until the keeper's own cloud exists, every counsel runs
on local substrate and says so. ``substrate_report()`` is part of every
verdict. Third-party teachers are never consulted — a counsel that cannot
deliberate locally stands down rather than borrowing a teacher's mind.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from levi.ci import canon

#: Advisory rulings only — a counsel advises, it never commands.
RULINGS: Tuple[str, ...] = (
    "proceed",
    "proceed-with-conditions",
    "hold-for-human",
    "refuse",
)

_RULING_WEIGHT = {
    "refuse": 3,
    "hold-for-human": 2,
    "proceed-with-conditions": 1,
    "proceed": 0,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class Seat:
    """One seat on the counsel. Seats deliberate; none command."""

    seat_id: str
    role: str  # proponent | challenger | arbiter
    counsel: str


@dataclass(frozen=True)
class Case:
    """A hard case escalated to counsel."""

    minion_id: str
    minion_class: str
    question: str
    context: Dict[str, Any] = field(default_factory=dict)
    stakes: str = "routine"  # routine | elevated | critical

    def fingerprint(self) -> str:
        body = {
            "minion_id": self.minion_id,
            "minion_class": self.minion_class,
            "question": self.question,
            "context": self.context,
            "stakes": self.stakes,
        }
        return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


@dataclass
class Proposal:
    seat_id: str
    ruling: str
    rationale: str


@dataclass
class Challenge:
    challenger_id: str
    target_seat_id: str
    objection: str


@dataclass
class Verdict:
    """The counsel's verdict — advisory, receipted, honest about substrate.

    Verdicts are per-agent and hemisphere-aware: one ruling delivered to
    both hemispheres of the agent-twin pair, each in its mind's own
    legibility. When the pair diverged, the divergence and its resolution
    ride along; when counsel hits its ceiling, ``escalate_to_keeper``
    hands the hard case up. Counsel advises; the keeper decides.
    """

    verdict_id: str
    counsel: str
    minion_id: str
    minion_class: str
    case_fingerprint: str
    ruling: str
    rationale: str
    conditions: List[str]
    proposals: List[Dict[str, str]]
    challenges: List[Dict[str, str]]
    dissent: List[Dict[str, str]]
    substrate: Dict[str, Any]
    ts: str
    # Agent-twin fields (keeper canon 2026-09-18): the living entity is the
    # agent; verdicts address the pair, both hemispheres.
    agent_id: str = ""
    hemispheres: Tuple[str, ...] = ("left", "right")
    delivery: Dict[str, Dict[str, str]] = field(default_factory=dict)
    divergence: Optional[Dict[str, Any]] = None
    escalate_to_keeper: bool = False

    def __post_init__(self) -> None:
        # The intake record id doubles as the agent id; keep them in sync
        # when only one was supplied.
        if self.agent_id and not self.minion_id:
            self.minion_id = self.agent_id
        elif self.minion_id and not self.agent_id:
            self.agent_id = self.minion_id

    def advisory_note(self) -> str:
        return (
            f"{self.counsel} advises '{self.ruling}' for {self.minion_id}; "
            "counsel advises, the operator decides."
        )


class CloudCounsel:
    """Base counsel. Subclasses give each class its character."""

    #: Counsel name, e.g. "AICI".
    name: str = "CI"
    #: Class served, e.g. "AI".
    class_tag: str = ""
    #: Seats on the counsel.
    n_seats: int = 3
    #: Quorum needed to render a verdict (<= n_seats).
    quorum: int = 2
    #: Character line for the verdict rationale.
    character: str = "advisory intelligence"

    def __init__(self, n_seats: Optional[int] = None):
        if n_seats is not None:
            self.n_seats = n_seats
        roles = ["proponent", "challenger", "arbiter"]
        self.seats: List[Seat] = [
            Seat(
                seat_id=f"{self.name.lower()}-seat-{i + 1}",
                role=roles[i % len(roles)],
                counsel=self.name,
            )
            for i in range(self.n_seats)
        ]

    # -- substrate honesty ------------------------------------------------

    def substrate_report(self) -> Dict[str, Any]:
        """Where this counsel actually runs. Honest until the cloud is real."""
        return {
            "counsel": self.name,
            "substrate": "local",
            "cloud_attached": False,
            "cloud_note": (
                "The keeper's own cloud is the long-term direction "
                "(practical path through the native brain first). Until it "
                "exists, this counsel deliberates on local substrate and "
                "reports that plainly."
            ),
            "teachers_consulted": [],
            "teacher_note": (
                "Third-party teachers are backups/user preference only — "
                "never the counsel's mind."
            ),
        }

    # -- deliberation: propose -> challenge -> verdict -------------------

    def propose(self, case: Case) -> List[Proposal]:
        """Each seat issues a proposed judgment. Subclasses give character."""
        return [
            Proposal(
                seat_id=seat.seat_id,
                ruling=self._seat_ruling(seat, case),
                rationale=self._seat_rationale(seat, case),
            )
            for seat in self.seats
        ]

    def _seat_ruling(self, seat: Seat, case: Case) -> str:
        # Base counsel: stakes drive the proposal; subclasses refine.
        if case.stakes == "critical":
            return "hold-for-human"
        if case.stakes == "elevated":
            return "proceed-with-conditions"
        return "proceed"

    def _seat_rationale(self, seat: Seat, case: Case) -> str:
        return (
            f"{seat.role} {seat.seat_id} ({self.character}): "
            f"stakes={case.stakes} on '{case.question}'."
        )

    def challenge_round(self, case: Case, proposals: List[Proposal]) -> List[Challenge]:
        """Seats red-team each other's proposals. Dissent is fuel, not noise."""
        challenges: List[Challenge] = []
        for i, prop in enumerate(proposals):
            challenger = self.seats[(i + 1) % len(self.seats)]
            if challenger.seat_id == prop.seat_id:
                continue
            challenges.append(
                Challenge(
                    challenger_id=challenger.seat_id,
                    target_seat_id=prop.seat_id,
                    objection=self._challenge_objection(challenger, prop, case),
                )
            )
        return challenges

    def _challenge_objection(
        self, challenger: Seat, proposal: Proposal, case: Case
    ) -> str:
        return (
            f"{challenger.seat_id} presses {proposal.seat_id}: "
            f"defend '{proposal.ruling}' against the worst case for "
            f"{case.minion_id} — what breaks if this advice is wrong?"
        )

    def arbitrate(
        self, case: Case, proposals: List[Proposal], challenges: List[Challenge]
    ) -> Verdict:
        """Quorum renders the verdict; minority proposals become dissent."""
        if len(proposals) < self.quorum:
            raise ValueError(
                f"{self.name}: quorum not met "
                f"({len(proposals)} proposals, need {self.quorum})"
            )
        # Strictest ruling among quorum carries — fail toward caution.
        ranked = sorted(proposals, key=lambda p: _RULING_WEIGHT[p.ruling], reverse=True)
        winner = ranked[0]
        dissent = [
            {"seat_id": p.seat_id, "ruling": p.ruling, "rationale": p.rationale}
            for p in ranked[1:]
            if p.ruling != winner.ruling
        ]
        first_press = challenges[0] if challenges else None
        conditions = (
            [
                f"condition from {first_press.challenger_id}: "
                "answer the objection before acting"
            ]
            if winner.ruling == "proceed-with-conditions" and first_press
            else []
        )
        return Verdict(
            verdict_id=f"{self.name.lower()}-v-{case.fingerprint()[:12]}",
            counsel=self.name,
            minion_id=case.minion_id,
            minion_class=case.minion_class,
            case_fingerprint=case.fingerprint(),
            ruling=winner.ruling,
            rationale=(
                f"{self.character} quorum ({len(proposals)} seats, "
                f"{len(challenges)} challenges): {winner.rationale}"
            ),
            conditions=conditions,
            proposals=[
                {"seat_id": p.seat_id, "ruling": p.ruling, "rationale": p.rationale}
                for p in proposals
            ],
            challenges=[
                {
                    "challenger_id": c.challenger_id,
                    "target_seat_id": c.target_seat_id,
                    "objection": c.objection,
                }
                for c in challenges
            ],
            dissent=dissent,
            substrate=self.substrate_report(),
            ts=_utcnow(),
        )

    def deliberate(self, case: Case) -> Verdict:
        """Full protocol: propose → challenge → verdict."""
        proposals = self.propose(case)
        challenges = self.challenge_round(case, proposals)
        return self.arbitrate(case, proposals, challenges)
