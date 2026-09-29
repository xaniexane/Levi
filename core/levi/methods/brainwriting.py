"""Brainwriting 6-3-5 / Method 635: 108 ideas in 30 minutes, no talking.

Origin: Bernd Rohrbach, "Kreativ nach Regeln — Methode 635", published in
the German sales magazine Absatzwirtschaft in 1968 (later literature cites
Vol. 12, 1969, pp. 73–75 — the date wobbles a year between sources).

The protocol: 6 participants, each writes 3 ideas on a worksheet in 5
minutes; sheets pass to the neighbor; 6 rounds. Result: 6 × 6 × 3 = 108
ideas in 30 minutes. The mechanism is subtraction: silent writing kills
the three documented failure modes of verbal brainstorming — production
blocking (one mouth at a time), evaluation apprehension (fear of sounding
stupid out loud), and social loafing (hiding in the group). Diehl &
Stroebe (1987) and replications find written ideation beating verbal
brainstorming on quantity and quality. Duplicates are expected and cheap;
the good ideas are randomly scattered through the volume.

What it is in LEVI: the round discipline, enforced in code. A Session
runs exactly len(participants) rounds so every sheet is seen by every
mind; each round, each participant fills exactly ideas_per_round slots on
exactly one sheet; sheets rotate deterministically. The slot-count
invariant (participants × rounds × ideas_per_round) is checked at finish.

LAWS (declared here, enforced below):
  L1. Silence. The protocol has no verbal channel; there is no method
      for it, and rounds are driven by submissions alone.
  L2. The slot invariant. Every round, every participant fills exactly
      ideas_per_round slots; each sheet is seen by every participant
      exactly once.
  L3. No skips, no repeats, no early finish. A round closes only when all
      its sheets are submitted; the session finishes only when all rounds
      close.

Honesty label: LOAD-BEARING — silent parallel generation with cyclic
cross-pollination is a concrete, transferable mechanism. The skepticism
stays in the docstring: the 108 includes duplicates and junk — the method
promises volume, not quality. The 1968/1969 publication date differs
between sources. Works with 4–7 participants (48/75/147 slots); solo mode
is one mind running every seat in turn.

Deny-closed inputs: fewer than 2 participants, duplicate or blank
participant ids, blank topic, wrong idea count, wrong author for a
sheet/round, out-of-order rounds, duplicate submission, submission after
finish, finish before every round is closed — all ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["Session", "Submission"]

MIN_PARTICIPANTS = 2
MAX_PARTICIPANTS = 7


@dataclass(frozen=True)
class Submission:
    sheet: int
    author: str
    ideas: List[str]


class Session:
    """One 6-3-5 (generalized) brainwriting session."""

    def __init__(
        self,
        topic: str,
        participants: List[str],
        ideas_per_round: int = 3,
        round_minutes: int = 5,
    ) -> None:
        if not topic or not topic.strip():
            raise ValueError("topic must not be blank")
        if len(participants) < MIN_PARTICIPANTS:
            raise ValueError("need at least %d participants" % MIN_PARTICIPANTS)
        if len(participants) > MAX_PARTICIPANTS:
            raise ValueError("at most %d participants" % MAX_PARTICIPANTS)
        if len(set(participants)) != len(participants):
            raise ValueError("participant ids must be distinct")
        if any(not p or not p.strip() for p in participants):
            raise ValueError("participant ids must not be blank")
        if ideas_per_round < 1:
            raise ValueError("ideas_per_round must be >= 1")
        if round_minutes < 1:
            raise ValueError("round_minutes must be >= 1")
        self._topic = topic.strip()
        self._participants = list(participants)
        self._ideas_per_round = ideas_per_round
        self._round_minutes = round_minutes
        self._rounds = len(participants)  # every sheet seen by every mind
        self._current_round = 0
        self._sheets: Dict[int, List[Submission]] = {i: [] for i in range(len(participants))}
        self._finished = False

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def current_round(self) -> int:
        return self._current_round

    @property
    def total_rounds(self) -> int:
        return self._rounds

    def expected_slots(self) -> int:
        """L2 invariant: participants × rounds × ideas_per_round."""
        return len(self._participants) * self._rounds * self._ideas_per_round

    def _sheet_holder(self, sheet: int, round_no: int) -> str:
        # Sheets rotate right each round: sheet s is held by participant
        # (s - round) mod n in round `round_no` (0-based).
        n = len(self._participants)
        return self._participants[(sheet - round_no) % n]

    def submit(self, sheet: int, author: str, ideas: List[str]) -> Submission:
        """Submit one participant's row for the current round."""
        if self._finished:
            raise ValueError("session is finished")
        if self._current_round >= self._rounds:
            raise ValueError("all rounds are closed")
        if sheet not in self._sheets:
            raise ValueError("unknown sheet: %r" % (sheet,))
        if author != self._sheet_holder(sheet, self._current_round):
            raise ValueError(
                "sheet %d in round %d belongs to %s, not %s"
                % (sheet, self._current_round + 1, self._sheet_holder(sheet, self._current_round), author)
            )
        if len(self._sheets[sheet]) > self._current_round:
            # L3: no repeats — each sheet takes exactly one submission per
            # round; the author check above already pins the submitter to
            # this round's unique holder of the sheet.
            raise ValueError(
                "sheet %d already has its submission for round %d" % (sheet, self._current_round + 1)
            )
        if len(ideas) != self._ideas_per_round:
            raise ValueError(
                "round requires exactly %d ideas, got %d" % (self._ideas_per_round, len(ideas))
            )
        if any(not i or not str(i).strip() for i in ideas):
            raise ValueError("ideas must not be blank")
        sub = Submission(sheet=sheet, author=author, ideas=[str(i).strip() for i in ideas])
        self._sheets[sheet].append(sub)
        if all(len(self._sheets[s]) == self._current_round + 1 for s in self._sheets):
            self._current_round += 1  # L3: a round closes only when all sheets are in
        return sub

    def finish(self) -> List[Submission]:
        """Close the session; verify the slot invariant (L2)."""
        if self._finished:
            raise ValueError("session already finished")
        if self._current_round < self._rounds:
            raise ValueError(
                "cannot finish: round %d of %d is still open" % (self._current_round + 1, self._rounds)
            )
        total = sum(len(s.ideas) for subs in self._sheets.values() for s in subs)
        if total != self.expected_slots():
            raise ValueError(
                "slot invariant broken: expected %d ideas, got %d" % (self.expected_slots(), total)
            )
        self._finished = True
        return [s for sheet in sorted(self._sheets) for s in self._sheets[sheet]]

    def harvest(self) -> List[str]:
        """All ideas, in sheet order. Session must be finished first."""
        if not self._finished:
            raise ValueError("harvest requires a finished session")
        return [idea for subs in (self._sheets[s] for s in sorted(self._sheets)) for s in subs for idea in s.ideas]
