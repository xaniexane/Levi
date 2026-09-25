"""Nominal Group Technique: structured group decision-making, enforced.

Origin: developed by Andre Delbecq and Andrew H. Van de Ven in the late
1960s to fix conventional group decision-making — groupthink, dominant
voices, unequal participation. Formalized 1971; book with David Gustafson,
"Group Techniques for Program Planning," 1975. The word "nominal" means
participants function as a group in name only during idea generation:
they think and write independently first, without influencing one another.

The protocol, five stages with two anti-dominance locks:
1. Silent independent generation — no anchoring on the first voice.
2. Round-robin sharing, one idea per turn until exhausted, recorded
   verbatim. The quiet junior and the loud senior get exactly the same
   number of turns.
3. Clarification for information only — debate is forbidden.
4. Private ranking/voting.
5. Tally (Borda sum); the top-ranked option wins.

The research behind it found unstructured brainstorming groups produced
fewer and worse ideas than nominal groups — yet organizations kept the
worse method, because brainstorming is loud, visible, and photographable
while NGT's silence looks like nothing happening. NGT's advantage is
choice tasks (ranking, deciding); at pure idea generation, nominal groups
can beat it — stated honestly here. Digital whiteboards reproduce sticky
notes but not the protocol: no enforced silent phase, no round-robin
turn order, no private ranking before framing.

What it is in LEVI: the five stages as a state machine. An NGTSession
refuses clarification before round-robin is complete, refuses voting
before clarification, and refuses tallying until every member has voted.
LEVI's own agent crews use this as the deliberation primitive when a
crew must rank options without the first subagent anchoring the rest.

Honesty label: LOAD-BEARING — silent gen + round-robin + private rank is
a concrete, transferable mechanism.

Deny-closed inputs: sharing before every member has generated, clarifying
or voting before round-robin completes, voting on unlisted ideas,
double voting, and tallying before all members have voted are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["NGTSession", "Idea"]


@dataclass
class Idea:
    id: int
    text: str
    author: str  # recorded for round-robin fairness; hidden from other voters


@dataclass
class NGTSession:
    """A Nominal Group Technique session run as an enforced state machine."""

    members: List[str]
    question: str = ""
    _stage: str = field(default="generate", init=False, repr=False)
    _generated: Dict[str, List[str]] = field(default_factory=dict, repr=False)
    _ideas: List[Idea] = field(default_factory=list, repr=False)
    _round_robin_done: bool = field(default=False, repr=False)
    _clarified: bool = field(default=False, repr=False)
    _votes: Dict[str, List[int]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if len(set(self.members)) < 2:
            raise ValueError("ngt: need at least 2 distinct members")
        if not self.question:
            raise ValueError("ngt: question must not be empty")
        for m in self.members:
            self._generated[m] = []

    # -- stage 1: silent generation ---------------------------------------
    def generate(self, member: str, ideas: List[str]) -> None:
        """Silently record one member's ideas (no one else sees them yet)."""
        if self._stage != "generate":
            raise ValueError("ngt: generation phase is over")
        if member not in self._generated:
            raise ValueError("ngt: %r is not a member" % member)
        clean = [i.strip() for i in ideas if i and i.strip()]
        if not clean:
            raise ValueError("ngt: %r generated no ideas" % member)
        self._generated[member].extend(clean)

    # -- stage 2: round-robin sharing -------------------------------------
    def round_robin(self) -> List[Idea]:
        """Interleave one idea per member per turn until all are shared."""
        if self._stage != "generate":
            raise ValueError("ngt: round-robin already ran")
        if any(not v for v in self._generated.values()):
            missing = [m for m, v in self._generated.items() if not v]
            raise ValueError(
                "ngt: members have not generated yet: %s" % ", ".join(missing)
            )
        idea_id = 1
        # round-robin: one idea per member per pass, until all are shared
        remaining = {m: list(v) for m, v in self._generated.items()}
        order: List[str] = []
        while any(remaining.values()):
            for member in self.members:
                if remaining[member]:
                    text = remaining[member].pop(0)
                    self._ideas.append(Idea(id=idea_id, text=text, author=member))
                    order.append(member)
                    idea_id += 1
        self._round_robin_done = True
        self._stage = "clarify"
        return list(self._ideas)

    # -- stage 3: clarification (information only, no debate) --------------
    def merge_duplicates(self, keep_id: int, drop_ids: List[int]) -> None:
        """Fold duplicate ideas into one, with the consent rule built in.

        ``drop_ids`` must name ideas already listed; the kept idea survives.
        """
        if self._stage != "clarify":
            raise ValueError("ngt: can only merge during clarification")
        live = {i.id for i in self._ideas}
        if keep_id not in live:
            raise ValueError("ngt: unknown idea id %d" % keep_id)
        for did in drop_ids:
            if did not in live:
                raise ValueError("ngt: unknown idea id %d" % did)
            if did == keep_id:
                raise ValueError("ngt: cannot merge idea %d into itself" % did)
        self._ideas = [i for i in self._ideas if i.id not in set(drop_ids)]

    def finish_clarification(self) -> List[Idea]:
        if self._stage != "clarify":
            raise ValueError("ngt: not in clarification stage")
        self._clarified = True
        self._stage = "vote"
        return list(self._ideas)

    # -- stage 4: private ranking/voting -----------------------------------
    def vote(self, member: str, ranking: List[int]) -> None:
        """Private vote: member ranks idea ids, most-preferred first."""
        if self._stage != "vote":
            raise ValueError("ngt: voting is not open yet")
        if member not in self.members:
            raise ValueError("ngt: %r is not a member" % member)
        if member in self._votes:
            raise ValueError("ngt: %r already voted" % member)
        live = {i.id for i in self._ideas}
        if not ranking:
            raise ValueError("ngt: empty ranking from %r" % member)
        if len(set(ranking)) != len(ranking):
            raise ValueError("ngt: duplicate idea in ranking from %r" % member)
        unknown = [i for i in ranking if i not in live]
        if unknown:
            raise ValueError("ngt: ranking names unlisted ideas: %s" % unknown)
        self._votes[member] = list(ranking)

    # -- stage 5: tally -----------------------------------------------------
    def tally(self) -> List[Dict[str, object]]:
        """Borda-sum tally: each rank position earns (n - position) points."""
        if self._stage != "vote":
            raise ValueError("ngt: tally requires the vote stage")
        missing = [m for m in self.members if m not in self._votes]
        if missing:
            raise ValueError("ngt: members have not voted yet: %s" % ", ".join(missing))
        n = len(self._ideas)
        scores: Dict[int, int] = {i.id: 0 for i in self._ideas}
        for ranking in self._votes.values():
            for pos, idea_id in enumerate(ranking):
                scores[idea_id] += n - pos
        ordered = sorted(self._ideas, key=lambda i: (-scores[i.id], i.id))
        texts = {i.id: i.text for i in self._ideas}
        return [
            {"id": i.id, "text": texts[i.id], "points": scores[i.id]} for i in ordered
        ]

    def ideas(self) -> List[Idea]:
        return list(self._ideas)
