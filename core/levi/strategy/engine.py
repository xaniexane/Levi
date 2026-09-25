"""The compressed super-engine: one interface over all 48 laws.

THE LIFE FORMULA (deterministic, repeatable — situation in, projection out):

    Projection = 5-3-5( consult( Situation ) )

- The 48 laws are the CONSTANTS.
- Return-to-sender is the OPERATOR (applied when the situation is an attack).
- 5-3-5 is the COMPUTATION: think 5 steps ahead, lock the first 3, map the
  next 5 from there — inside-out, every angle, optimized for the best
  EFFICIENT outcome (best at lowest cost).

Doctrine (binding): defense never manipulates; attack = going and getting
the goal. The engine advises; you project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Law:
    """One compressed law: forward play and reverse play in a single object."""

    id: int
    name: str
    doctrine: str
    forward: str
    reverse: str
    constraints: Tuple[str, ...] = ()
    signals: Tuple[str, ...] = ()
    domains: Tuple[str, ...] = ()

    def brief(self) -> str:
        return f"Law {self.id:02d} — {self.name}: {self.doctrine}"


@dataclass
class Reading:
    """One law as it bears on a consulted situation."""

    law: Law
    score: float
    matched_signals: Tuple[str, ...]
    stance: str  # "forward" | "reverse" | "both"

    def guidance(self) -> str:
        if self.stance == "forward":
            return self.law.forward
        if self.stance == "reverse":
            return self.law.reverse
        return f"FORWARD: {self.law.forward}\nREVERSE: {self.law.reverse}"


@dataclass(frozen=True)
class Step:
    """One projected move in the 5-3-5 lookahead."""

    n: int
    move: str
    law_id: int
    law_name: str
    stance: str
    price: str  # what it costs, in the law's own constraints
    cost_tier: str  # low | medium | high (documented heuristic)
    outcome: str  # structural projection, not a prediction


@dataclass
class Projection:
    """The 5-3-5 computation: 5 ahead, 3 locked, next 5 mapped."""

    situation: str
    steps5: Tuple[Step, ...]
    locked3: Tuple[Step, ...]
    next5: Tuple[Step, ...]
    efficient_pick: str


@dataclass(frozen=True)
class Reflection:
    """Return-to-sender: the signature defensive move, as an operator."""

    attack: str
    reflected: str
    your_move: str
    not_this: Tuple[str, ...]


@dataclass
class FormulaResult:
    """Situation in, projection out — the whole formula applied."""

    situation: str
    readings: List[Reading]
    reflection: Optional[Reflection]
    projection: Projection


def _tok(text: str) -> List[str]:
    return [w.strip(".,;:!?()\"'").lower() for w in text.split() if len(w) > 2]


_REV_MARKERS = {"reverse", "invert", "blocked", "failing", "hostile", "watched",
                "crowded", "losing", "stuck"}
_FWD_MARKERS = {"start", "begin", "open", "new", "first", "launch"}
_ATTACK_MARKERS = {"attack", "attacked", "attacking", "undermine", "undermined",
                   "undermining", "provoke", "provoked", "provoking", "provocation",
                   "insult", "insulted", "blame", "blamed", "sabotage", "sabotaged",
                   "gaslight", "gaslit", "threat", "threatened", "smear", "smeared",
                   "bully", "bullied", "bullying", "backstab", "backstabbed",
                   "betray", "betrayed", "accuse", "accused", "belittle",
                   "belittled", "humiliate", "humiliated"}

# Cost heuristic (documented): what a move typically demands of you.
_LOW_COST = {"wait", "patience", "listen", "observe", "preparation", "prepare",
             "verify", "measure", "audit", "define", "name", "silence"}
_HIGH_COST = {"all in", "burn", "oath", "abandon", "break", "strike", "launch",
              "declare"}
_COST_WEIGHT = {"low": 3.0, "medium": 2.0, "high": 1.0}


def _cost_tier(law: Law) -> str:
    text = f"{law.name} {law.doctrine} {law.forward}".lower()
    if any(k in text for k in _HIGH_COST):
        return "high"
    if any(k in text for k in _LOW_COST):
        return "low"
    return "medium"


class Engine:
    """The compressed super-engine: one interface over all 48 laws."""

    def __init__(self, laws: Sequence[Law]) -> None:
        self._laws: Tuple[Law, ...] = tuple(laws)
        self._by_id: Dict[int, Law] = {law.id: law for law in laws}
        self._index: Dict[int, Dict[str, int]] = {}
        for law in laws:
            bag: Dict[str, int] = {}
            for w in _tok(law.name):
                bag[w] = bag.get(w, 0) + 3
            for w in _tok(law.doctrine):
                bag[w] = bag.get(w, 0) + 2
            for sig in law.signals:
                for w in _tok(sig):
                    bag[w] = bag.get(w, 0) + 4
            for w in _tok(law.forward) + _tok(law.reverse):
                bag[w] = bag.get(w, 0) + 1
            self._index[law.id] = bag

    @property
    def laws(self) -> Tuple[Law, ...]:
        return self._laws

    def get(self, law_id: int) -> Law:
        return self._by_id[law_id]

    def domains(self) -> Tuple[str, ...]:
        seen: List[str] = []
        for law in self._laws:
            for d in law.domains:
                if d not in seen:
                    seen.append(d)
        return tuple(seen)

    def consult(self, situation: str, top: int = 5,
                domain: Optional[str] = None) -> List[Reading]:
        """Rank the laws that bear on a situation, forward+reverse together.

        Domain-universal: any life area in, ranked laws out. Pass ``domain``
        (e.g. "money", "health") to boost laws proven in that arena.
        """
        words = _tok(situation)
        if not words:
            return []
        readings: List[Reading] = []
        for law in self._laws:
            bag = self._index[law.id]
            score = 0.0
            matched: List[str] = []
            for w in sorted(set(words)):
                hit = bag.get(w, 0)
                if hit:
                    score += hit
                    if w in {s.lower() for s in law.signals} or hit >= 3:
                        matched.append(w)
            if domain and domain.lower() in {d.lower() for d in law.domains}:
                score += 6.0
                matched.append(f"domain:{domain.lower()}")
            if score <= 0:
                continue
            wl = set(words)
            rev = len(wl & _REV_MARKERS)
            fwd = len(wl & _FWD_MARKERS)
            stance = "reverse" if rev > fwd else ("forward" if fwd > rev else "both")
            readings.append(
                Reading(law=law, score=score,
                        matched_signals=tuple(sorted(set(matched))), stance=stance)
            )
        readings.sort(key=lambda r: (-r.score, r.law.id))
        return readings[: max(1, top)]

    # -- Return-to-sender: the signature defensive operator -----------------

    def detect_attack(self, situation: str) -> bool:
        return bool(set(_tok(situation)) & _ATTACK_MARKERS)

    def return_to_sender(self, attack: str) -> Reflection:
        """Reflect an attack back to its sender — cleanly.

        No escalation, no manipulation, no absorption. The attack returns to
        its source; you stay on your aim.
        """
        return Reflection(
            attack=attack,
            reflected=("Name the behavior once, plainly, without heat — then let "
                       "the consequences belong to the one who sent it. What was "
                       "thrown returns to the thrower; you never pick it up."),
            your_move=("Stay on your aim. Answer the substance if there is any; "
                       "ignore the provocation. Document, don't dramatize. "
                       "One clean response, then back to the goal."),
            not_this=(
                "No escalation — you don't raise the stakes.",
                "No manipulation — you don't play their game back at them.",
                "No absorption — you don't carry what isn't yours.",
            ),
        )

    # -- 5-3-5: the projection computation ----------------------------------

    def _make_step(self, n: int, reading: Reading) -> Step:
        law = reading.law
        return Step(
            n=n,
            move=reading.guidance(),
            law_id=law.id,
            law_name=law.name,
            stance=reading.stance,
            price="; ".join(law.constraints),
            cost_tier=_cost_tier(law),
            outcome=(f"If Law {law.id:02d} holds: {law.doctrine} "
                     f"Watch the price: {law.constraints[0]}"),
        )

    def project(self, situation: str, depth: int = 5,
                domain: Optional[str] = None) -> Projection:
        """The 5-3-5 lookahead: think `depth` ahead, lock 3, map next `depth`.

        Inside-out: every angle via the ranked laws, every outcome via
        forward+reverse, optimized for the best EFFICIENT outcome — the best
        result at the lowest cost. Deterministic: same situation, same
        projection.
        """
        depth = max(3, min(7, depth))
        readings = self.consult(situation, top=depth * 2, domain=domain)
        return self._project_from(situation, readings, depth=depth)

    def _project_from(self, situation: str, readings: List[Reading],
                      depth: int = 5) -> Projection:
        steps = tuple(self._make_step(i + 1, r) for i, r in enumerate(readings[:depth]))
        locked = steps[:3]
        pool = readings[depth: depth * 2] or readings[:depth]
        next_steps = tuple(self._make_step(depth + i + 1, r)
                           for i, r in enumerate(pool[:depth]))
        # Efficient pick: best score per unit cost among the locked three.
        scored = [(r.score * _COST_WEIGHT[self._make_step(0, r).cost_tier], r)
                  for r in readings[:3]]
        best = max(scored, key=lambda p: (p[0], -p[1].law.id))[1] if scored else None
        if best is not None:
            pick = (f"Lock Law {best.law.id:02d} ({best.law.name}), {best.stance}: "
                    f"highest return per cost among the locked three. "
                    f"{best.guidance()}")
        else:
            pick = "No law bears on this situation — say more before moving."
        return Projection(situation=situation, steps5=steps, locked3=locked,
                          next5=next_steps, efficient_pick=pick)

    # -- The formula: situation in, projection out ---------------------------

    def apply(self, situation: str, domain: Optional[str] = None) -> FormulaResult:
        """Apply the life formula: RTS operator ? 48 laws ? 5-3-5."""
        attacked = self.detect_attack(situation)
        readings = self.consult(situation, top=10, domain=domain)
        if attacked and not readings:
            # An attack always bears on the laws: consult the attack itself.
            readings = self.consult(situation + " attack provocation undermined",
                                    top=10, domain=domain)
        reflection = self.return_to_sender(situation) if attacked else None
        projection = self.project(situation, domain=domain)
        if attacked and not projection.steps5 and readings:
            projection = self._project_from(situation, readings)
        return FormulaResult(situation=situation, readings=readings,
                             reflection=reflection, projection=projection)
