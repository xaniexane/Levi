"""The Gordon Technique: the group never hears the real problem.

Origin: W.J.J. Gordon's group method of the 1960s, the quiet sibling of
Synectics. Only the leader knows the exact problem under consideration.
The leader opens the session with a generalized FUNCTIONAL topic — not
"design a better window-cleaning procedure" but "remove dirt" — and the
group generates freely around the abstraction. Only at harvest time does
the leader reveal the real problem and map the ideas onto it.

The mechanism is a defense against two specific killers: premature
closure (someone proposes a plausible answer in minute two and the
session ends) and egocentric involvement (a participant locks onto
defending their own idea instead of generating). By withholding the
target, every idea stays a free contribution instead of a bid in a
contest. The leader's craft is the altitude dial: the abstraction must be
a function, never a product — too concrete and the group back-solves, too
abstract and the harvest is noise.

What it is in LEVI: a blind session, enforced in code. The real problem
string is sealed at construction; participants register against the
function abstraction only; contributions are accepted only before reveal;
reveal happens exactly once and returns the real problem plus the idea
harvest mapped onto it. There is no participant-facing path to the sealed
string.

LAWS (declared here, enforced below):
  L1. The real problem is sealed. No participant-facing method ever
      returns it before reveal.
  L2. One reveal. reveal() succeeds exactly once; after it, no
      contributions and no second reveal.
  L3. The abstraction is fixed. Participants cannot be added after the
      first contribution — the group the leader briefed is the group
      that generates.

Honesty label: USEFUL-PATTERN — the anti-anchoring logic is strong but
the evidence is textbook-level, not experimental. The skepticism stays in
the docstring: a bad abstraction from the leader poisons the session
silently, and this module cannot judge abstraction quality — it can only
enforce the blindness. Pairs with synectics (the excursion's
group-management twin) and brainwriting (blind + silent = the ego-free
maximum).

Deny-closed inputs: blank real problem, blank function abstraction,
blank leader or participant ids, leader registering as a participant,
duplicate participants, adding participants after the first
contribution, contributions from unregistered ids, blank ideas,
contributions after reveal, reveal before any contribution, double
reveal — all ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = ["BlindSession", "Contribution"]


@dataclass(frozen=True)
class Contribution:
    participant: str
    idea: str


class BlindSession:
    """One Gordon-Technique blind session."""

    def __init__(self, real_problem: str, function_prompt: str, leader: str) -> None:
        if not real_problem or not real_problem.strip():
            raise ValueError("real_problem must not be blank")
        if not function_prompt or not function_prompt.strip():
            raise ValueError("function_prompt must not be blank")
        if not leader or not leader.strip():
            raise ValueError("leader must not be blank")
        self._real_problem = real_problem.strip()  # L1: sealed
        self._function_prompt = function_prompt.strip()
        self._leader = leader.strip()
        self._participants: List[str] = []
        self._contributions: List[Contribution] = []
        self._revealed = False

    @property
    def function_prompt(self) -> str:
        """The only problem-statement participants ever see (L1)."""
        return self._function_prompt

    @property
    def leader(self) -> str:
        return self._leader

    @property
    def revealed(self) -> bool:
        return self._revealed

    def register(self, participant: str) -> str:
        """Add a participant before generation starts (L3)."""
        if self._revealed:
            raise ValueError("session is closed")
        if self._contributions:
            raise ValueError("cannot add participants after generation has started")
        pid = (participant or "").strip()
        if not pid:
            raise ValueError("participant id must not be blank")
        if pid == self._leader:
            raise ValueError("the leader cannot be a participant")
        if pid in self._participants:
            raise ValueError("duplicate participant: %s" % pid)
        self._participants.append(pid)
        return pid

    def contribute(self, participant: str, idea: str) -> Contribution:
        """Contribute one idea against the function abstraction (L1)."""
        if self._revealed:
            raise ValueError("session is closed: no contributions after reveal")
        if participant not in self._participants:
            raise ValueError("unregistered participant: %s" % (participant,))
        if not idea or not str(idea).strip():
            raise ValueError("idea must not be blank")
        contrib = Contribution(participant=participant, idea=str(idea).strip())
        self._contributions.append(contrib)
        return contrib

    def reveal(self) -> Dict[str, object]:
        """The leader reveals the real problem, exactly once (L2).

        Returns the sealed problem plus the harvest: every contribution
        mapped onto the real target for the first time.
        """
        if self._revealed:
            raise ValueError("the real problem is revealed once")
        if not self._contributions:
            raise ValueError("nothing to harvest: no contributions yet")
        self._revealed = True
        return {
            "real_problem": self._real_problem,
            "function_prompt": self._function_prompt,
            "harvest": list(self._contributions),
        }

    def contributions(self) -> List[Contribution]:
        return list(self._contributions)
